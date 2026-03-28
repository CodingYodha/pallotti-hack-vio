"""
Face Recognition Service.

Primary backend  : InsightFace  (ArcFace + RetinaFace)  — state-of-the-art accuracy
Fallback backend : facenet-pytorch (InceptionResnetV1 + MTCNN)
Final fallback   : disabled (no face recognition)

Embedding format stored in DB:
    {"v": [float, ...], "backend": "insightface" | "facenet_pytorch"}

Background thread execution prevents blocking the YOLO inference pipeline.
"""

import json
import logging
import os
import threading
import uuid
from typing import Optional, Tuple, Dict, List
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

EMPLOYEE_PHOTOS_DIR = "employee_photos"
os.makedirs(EMPLOYEE_PHOTOS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Backend selection — InsightFace preferred, facenet-pytorch as fallback
# ---------------------------------------------------------------------------

FACE_RECOGNITION_AVAILABLE = False
BACKEND = "none"
EMBEDDING_DIM = 512  # both InsightFace ArcFace and FaceNet produce 512-d

# --- InsightFace (ArcFace + RetinaFace) ---
try:
    from insightface.app import FaceAnalysis as InsightFaceApp
    INSIGHTFACE_AVAILABLE = True
    FACE_RECOGNITION_AVAILABLE = True
    BACKEND = "insightface"
    logger.info("InsightFace loaded — using ArcFace + RetinaFace backend (SOTA accuracy)")
except ImportError:
    INSIGHTFACE_AVAILABLE = False
    logger.warning("InsightFace NOT available — trying facenet-pytorch fallback")

# --- facenet-pytorch fallback ---
if not INSIGHTFACE_AVAILABLE:
    try:
        from facenet_pytorch import MTCNN, InceptionResnetV1
        FACENET_AVAILABLE = True
        FACE_RECOGNITION_AVAILABLE = True
        BACKEND = "facenet_pytorch"
        logger.info("facenet-pytorch loaded — using FaceNet VGGFace2 backend")
    except ImportError:
        FACENET_AVAILABLE = False
        logger.warning("facenet-pytorch NOT available — face recognition is disabled")
else:
    FACENET_AVAILABLE = False


class FaceRecognitionService:
    """
    Matches detected persons against the employee database.

    Primary:  InsightFace (ArcFace embeddings, cosine similarity)
    Fallback: facenet-pytorch (FaceNet embeddings, L2 distance)

    - Async thread pool so the video pipeline is never blocked
    - Per-track attempt counting with a quality gate (crop must be ≥60×40 px)
    - Employee encodings cached in-memory; reload triggered after DB changes
    """

    def __init__(self):
        self._known_employees: List[Tuple[int, str, np.ndarray]] = []
        self._lock = threading.Lock()
        self.track_id_to_employee: Dict[int, Tuple[Optional[int], Optional[str]]] = {}
        self.unknown_snapshots: Dict[int, str] = {}
        self._loaded = False
        self._attempt_count: Dict[int, int] = {}
        self._max_attempts = 50

        # Per-track frame-skip gate: only attempt face rec every N frames
        # Avoids flooding the thread pool and wasting CPU on redundant calls
        self._last_attempt_frame: Dict[int, int] = {}
        self._attempt_interval: int = 15  # frames between recognition attempts per track

        import torch
        self.device_str = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        self._use_gpu = torch.cuda.is_available()
        logger.info(f"FaceRecognitionService initializing — device: {self.device_str}, backend: {BACKEND}")

        # --- InsightFace init ---
        # buffalo_sc uses scrfd_500m (det) + MobileFaceNet (rec) — ~16 MB total,
        # ~15 ms/inference on CPU vs ~300 ms for buffalo_l. Accuracy is only
        # marginally lower for real-time use where speed matters most.
        if INSIGHTFACE_AVAILABLE:
            try:
                # Prefer GPU (CUDA), fall back to CPU
                providers = (
                    ['CUDAExecutionProvider', 'CPUExecutionProvider']
                    if self._use_gpu
                    else ['CPUExecutionProvider']
                )
                self._insight = InsightFaceApp(name='buffalo_sc', providers=providers)
                ctx_id = 0 if self._use_gpu else -1
                # 320×320 det_size — much better accuracy than 160x160, still fast enough on GPU
                self._insight.prepare(ctx_id=ctx_id, det_size=(320, 320))
                device_label = 'GPU (CUDA)' if self._use_gpu else 'CPU'
                logger.info(f"InsightFace (buffalo_sc / MobileFaceNet+ArcFace) ready on {device_label}")
            except Exception as exc:
                logger.error(f"InsightFace init failed: {exc}. Face recognition disabled.")

        # --- facenet-pytorch fallback init ---
        if FACENET_AVAILABLE:
            import torch
            _dev = torch.device(self.device_str)
            self.mtcnn = MTCNN(
                image_size=160, margin=0, min_face_size=20,
                thresholds=[0.6, 0.7, 0.7], factor=0.709, post_process=True,
                device=_dev
            )
            self.resnet = InceptionResnetV1(pretrained='vggface2').eval().to(_dev)

        # Thread pool — 4 workers so multiple persons can be embedded in parallel
        # without starving the event loop
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._processing_tracks: set = set()

    # ------------------------------------------------------------------
    # Employee loading
    # ------------------------------------------------------------------

    def load_employees_sync(self):
        """Load (and re-encode if needed) employee face data from the database."""
        try:
            import sqlite3
            from pathlib import Path

            db_path = Path(__file__).parent.parent.parent / "violation_tracking.db"
            if not db_path.exists():
                self._loaded = True
                return

            conn = sqlite3.connect(str(db_path))
            employees = []

            if FACE_RECOGNITION_AVAILABLE:
                cursor = conn.execute(
                    "SELECT id, name, photo_path, face_encoding FROM employees"
                )
                for row in cursor.fetchall():
                    emp_id, name, photo_path, enc_json = row

                    vec = self._try_load_encoding(enc_json)

                    if vec is None and photo_path:
                        # Re-encode: stored encoding is missing, wrong backend, or wrong dim
                        fs_path = photo_path.lstrip("/")
                        if os.path.exists(fs_path):
                            logger.info(f"Re-encoding face for '{name}' using {BACKEND}...")
                            try:
                                new_enc_json = self._encode_from_path(fs_path)
                                if new_enc_json:
                                    vec = self._try_load_encoding(new_enc_json)
                                    conn.execute(
                                        "UPDATE employees SET face_encoding = ? WHERE id = ?",
                                        (new_enc_json, emp_id)
                                    )
                                    conn.commit()
                            except Exception as e:
                                logger.error(f"Re-encode failed for '{name}': {e}")

                    if vec is not None:
                        employees.append((emp_id, name, vec))

            conn.close()

            with self._lock:
                self._known_employees = employees

            self._loaded = True
            logger.info(f"Loaded {len(employees)} employee face profiles (backend: {BACKEND})")

        except Exception as e:
            logger.error(f"Failed to load employee data: {e}")
            self._loaded = True

    def _try_load_encoding(self, enc_json: Optional[str]) -> Optional[np.ndarray]:
        """
        Parse stored encoding JSON and return a numpy vector if it matches the
        currently active backend. Returns None if encoding is missing, wrong
        backend, or wrong dimension (triggers re-encoding).
        """
        if not enc_json:
            return None
        try:
            parsed = json.loads(enc_json)

            if isinstance(parsed, dict):
                # New format: {"v": [...], "backend": "insightface"}
                stored_backend = parsed.get("backend", "unknown")
                vec_list = parsed.get("v", [])
            else:
                # Legacy flat-list format (always facenet_pytorch)
                stored_backend = "facenet_pytorch"
                vec_list = parsed

            if stored_backend != BACKEND:
                return None  # Backend mismatch → re-encode

            if len(vec_list) != EMBEDDING_DIM:
                return None  # Dimension mismatch → re-encode

            vec = np.array(vec_list, dtype=np.float32)
            # InsightFace embeddings should be L2-normalized; ensure that
            if BACKEND == "insightface":
                norm = np.linalg.norm(vec)
                vec = vec / norm if norm > 0 else vec
            return vec

        except Exception:
            return None

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def invalidate_cache(self):
        """Clear all cached data (call load_employees_sync after to refresh)."""
        with self._lock:
            self._known_employees = []
        self._loaded = False
        self.track_id_to_employee = {}
        self.unknown_snapshots = {}
        self._attempt_count = {}

    def reset(self):
        """Reset per-session state (keep employee encodings)."""
        with self._lock:
            self.track_id_to_employee.clear()
            self.unknown_snapshots.clear()
            self._attempt_count.clear()
            self._last_attempt_frame.clear()
            self._processing_tracks.clear()

    # ------------------------------------------------------------------
    # Public API — called per-frame from the pipeline
    # ------------------------------------------------------------------

    def identify_person(
        self,
        frame: np.ndarray,
        person_bbox: Tuple[int, int, int, int],
        track_id: int,
        video_id: str = "unknown",
        frame_num: int = 0,
        tolerance: float = 0.60,  # Strict cosine sim threshold for ArcFace to prevent ID swapping
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Identify a person by face matching — fully asynchronous.
        Returns (employee_id, employee_name) or (None, None) immediately
        while the actual recognition runs in a background thread.

        Continuous verification: to recover from Tracker ID swaps (e.g., two people
        crossing paths and swapping track_ids), we attempt face recognition every
        `_attempt_interval` frames *continuously*, even if the track is already identified.
        """
        with self._lock:
            # Frame-skip gate: don't spam the thread pool every frame.
            # E.g., at 30fps, interval=15 means we check their face twice a second.
            last_frame = self._last_attempt_frame.get(track_id, -9999)
            if frame_num - last_frame < self._attempt_interval:
                # Return whatever is currently cached
                return self.track_id_to_employee.get(track_id, (None, None))

            # Already being resolved in a thread
            if track_id in self._processing_tracks:
                return self.track_id_to_employee.get(track_id, (None, None))

            # Record that we are attempting this frame
            self._last_attempt_frame[track_id] = frame_num

        if not self._loaded:
            self.load_employees_sync()

        face_crop = self._crop_face_region(frame, person_bbox)
        if face_crop is None:
            with self._lock:
                return self.track_id_to_employee.get(track_id, (None, None))

        with self._lock:
            self._processing_tracks.add(track_id)

        self._executor.submit(
            self._process_face_thread,
            track_id, face_crop.copy(), video_id, frame_num, tolerance
        )
        
        # Return whatever is currently known while we compute
        with self._lock:
            return self.track_id_to_employee.get(track_id, (None, None))

    def get_display_name(self, track_id: int) -> str:
        """Get the display label for a track_id."""
        with self._lock:
            if track_id in self.track_id_to_employee:
                emp_id, emp_name = self.track_id_to_employee[track_id]
                if emp_name:
                    return emp_name
        return f"Unknown-{track_id}"

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _process_face_thread(
        self, track_id: int, face_crop: np.ndarray,
        video_id: str, frame_num: int, tolerance: float
    ):
        """Background thread: run face detection + embedding + matching."""
        try:
            embedding = self._extract_embedding(face_crop)

            if embedding is not None:
                with self._lock:
                    known = self._known_employees.copy()
                match = self._match(embedding, known, threshold=tolerance)
            else:
                match = None

            if match:
                emp_id, emp_name = match
                with self._lock:
                    self.track_id_to_employee[track_id] = (emp_id, emp_name)
                    # Reset attempt count so a false-negative sequence doesn't permaban them
                    self._attempt_count[track_id] = 0
                logger.debug(f"Continuous Match verified: Track-{track_id} → '{emp_name}'")
            else:
                # If embedding is None, we didn't see a face (e.g. back of head).
                # Only consume attempts and save snapshots if we actually extracted a face.
                if embedding is not None:
                    with self._lock:
                        # Quality gate: only burn an attempt on a usefully-sized crop
                        h, w = face_crop.shape[:2]
                        if h >= 60 and w >= 40:
                            attempts = self._attempt_count.get(track_id, 0)
                            self._attempt_count[track_id] = attempts + 1
                            
                            # If we hit max attempts AND we don't already know who they are, lock as Unknown
                            if attempts + 1 >= self._max_attempts:
                                if track_id not in self.track_id_to_employee or \
                                   self.track_id_to_employee[track_id] == (None, None):
                                    self.track_id_to_employee[track_id] = (None, None)
                                else:
                                    # If they WERE Shivaprasad, but now failing repeatedly? Tracker ID swap!
                                    # Fall back to Unknown if we exceed threshold, allowing real ID to be reassigned
                                    # but let's give more leeway. 50 bad frames is a lot.
                                    self.track_id_to_employee[track_id] = (None, None)

                        if track_id not in self.unknown_snapshots and \
                           self.track_id_to_employee.get(track_id) == (None, None):
                            snap = self._save_face_snapshot(face_crop, track_id, video_id, frame_num)
                            if snap:
                                self.unknown_snapshots[track_id] = snap
                else:
                    pass # Ignore frames lacking faces

        except Exception as e:
            logger.error(f"Face thread error for track {track_id}: {e}")
        finally:
            with self._lock:
                self._processing_tracks.discard(track_id)

    # ------------------------------------------------------------------
    # Embedding extraction
    # ------------------------------------------------------------------

    def _extract_embedding(self, img_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract a normalised face embedding from a BGR image crop.
        Uses InsightFace (ArcFace) if available, otherwise facenet-pytorch.
        """
        if INSIGHTFACE_AVAILABLE:
            return self._embed_insightface(img_bgr)
        elif FACENET_AVAILABLE:
            return self._embed_facenet(img_bgr)
        return None

    def _embed_insightface(self, img_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        InsightFace path:  RetinaFace detection → ArcFace embedding.
        Takes the highest-confidence detected face in the crop.
        """
        try:
            faces = self._insight.get(img_bgr)
            if not faces:
                return None
            # Use highest detection score face
            face = max(faces, key=lambda f: f.det_score)
            emb = face.embedding.astype(np.float32)
            norm = np.linalg.norm(emb)
            return emb / norm if norm > 0 else emb
        except Exception as e:
            logger.debug(f"InsightFace embed failed: {e}")
            return None

    def _embed_facenet(self, img_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        facenet-pytorch path: MTCNN detection → InceptionResnetV1 embedding.
        """
        import torch
        try:
            from PIL import Image
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            face_tensor = self.mtcnn(pil_img)
            if face_tensor is None:
                return None
            if len(face_tensor.shape) != 3:
                return None
            _dev = torch.device(self.device_str)
            with torch.no_grad():
                emb = self.resnet(face_tensor.unsqueeze(0).to(_dev))[0]
            arr = emb.cpu().numpy().astype(np.float32)
            return arr  # L2 distance used for matching, no normalisation needed
        except Exception as e:
            logger.debug(f"Facenet embed failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _match(
        self,
        embedding: np.ndarray,
        known: List[Tuple[int, str, np.ndarray]],
        threshold: float = 0.5,
    ) -> Optional[Tuple[int, str]]:
        """
        Match embedding against all known employees.

        InsightFace: cosine similarity (higher = more similar, threshold ~0.45-0.6)
        facenet    : L2 distance     (lower  = more similar, threshold ~0.8-1.0)
        """
        if not known:
            return None

        if BACKEND == "insightface":
            best_sim = -1.0
            best_match = None
            for emp_id, name, known_emb in known:
                sim = float(np.dot(embedding, known_emb))  # both normalised → cosine sim
                if sim > best_sim:
                    best_sim = sim
                    best_match = (emp_id, name)
            if best_match and best_sim >= threshold:
                logger.debug(f"ArcFace match: {best_match[1]} cosine={best_sim:.3f}")
                return best_match
            logger.debug(f"ArcFace near miss: {best_match[1] if best_match else 'None'} cosine={best_sim:.3f}")
            return None

        else:  # facenet — L2 distance
            import torch as _torch
            emb_t = _torch.tensor(embedding)
            best_dist = float('inf')
            best_match = None
            for emp_id, name, known_emb in known:
                known_t = _torch.tensor(known_emb)
                dist = _torch.dist(emb_t, known_t).item()
                if dist < best_dist:
                    best_dist = dist
                    best_match = (emp_id, name)
            if best_match and best_dist <= threshold:
                logger.debug(f"FaceNet match: {best_match[1]} L2={best_dist:.3f}")
                return best_match
            return None

    # ------------------------------------------------------------------
    # Cropping — 50% upper body (head + neck + part of torso for context)
    # ------------------------------------------------------------------

    def _crop_face_region(self, frame: np.ndarray, person_bbox) -> Optional[np.ndarray]:
        """
        Crop the upper 50% of the person bounding box.

        Why 50%: YOLO full-body boxes contain head at the very top.
        50% gives RetinaFace / MTCNN plenty of context (head + neck + upper
        chest) while excluding the irrelevant lower body.
        Minimum 80 px height so very small bboxes still produce usable crops.
        """
        h, w = frame.shape[:2]
        px1, py1, px2, py2 = person_bbox
        px1, py1 = max(0, int(px1)), max(0, int(py1))
        px2, py2 = min(w, int(px2)), min(h, int(py2))

        ph = py2 - py1
        pw = px2 - px1
        if ph < 30 or pw < 20:
            return None

        # 90% of box height from the top; captures head, shoulders, and most of torso
        # Prevents cutting off faces and gives max context
        face_bottom = py1 + max(int(ph * 0.90), 80)
        face_bottom = min(face_bottom, py2)
        crop = frame[py1:face_bottom, px1:px2].copy()
        return crop if crop.size > 0 else None

    # ------------------------------------------------------------------
    # Snapshot & encoding utilities
    # ------------------------------------------------------------------

    def _save_face_snapshot(
        self, face_img: np.ndarray, track_id: int, video_id: str, frame_num: int
    ) -> Optional[str]:
        try:
            fname = f"unknown_{track_id}_{video_id}_{frame_num}.jpg"
            path = os.path.join(EMPLOYEE_PHOTOS_DIR, fname)
            cv2.imwrite(path, face_img)
            return f"/employee_photos/{fname}"
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return None

    def _encode_from_path(self, image_path: str) -> Optional[str]:
        """
        Internal helper: encode a face from a file using the active backend.
        Stores result in the unified {"v": [...], "backend": "..."} format.
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            emb = self._extract_embedding(img)
            if emb is not None:
                return json.dumps({"v": emb.tolist(), "backend": BACKEND})
        except Exception as e:
            logger.error(f"_encode_from_path failed for {image_path}: {e}")
        return None

    def encode_face_from_file(self, image_path: str) -> Optional[str]:
        """
        Public API: extract face encoding from an image file.
        Reuses the singleton's already-loaded models (no re-init overhead).
        Returns JSON string or None if no face detected.
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return None
        return self._encode_from_path(image_path)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_face_service: Optional[FaceRecognitionService] = None


def get_face_service() -> FaceRecognitionService:
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service
