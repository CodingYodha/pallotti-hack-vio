"""
Video processing pipeline with YOLO built-in tracking.

Uses YOLO's native tracking (BoTSORT or ByteTrack) for maximum performance:
- GPU-accelerated tracking
- Single pass detection + tracking
- Minimal latency
- Browser-compatible video output
- Face recognition for employee identification
"""

# Face recognition service (lazy import to avoid circular deps)
try:
    from app.services.face_recognition_service import get_face_service, FaceRecognitionService
    FACE_SERVICE_AVAILABLE = True
except ImportError:
    FACE_SERVICE_AVAILABLE = False

import cv2
import numpy as np
from typing import Optional, Callable, Dict, List, Tuple
import os
import uuid
import logging
import subprocess
import shutil
from dataclasses import dataclass

from ultralytics import YOLO

from app.ai.aggregator import ViolationAggregator, ViolationRecord
from app.config import settings

logger = logging.getLogger(__name__)

VIOLATION_CAPTURE_COOLDOWN = 2.0

BODY_PART_TO_VIOLATION = {
    'face': ('No Face Mask', ['face-mask', 'facemask', 'mask', 'face mask']),
    'foot': ('No Safety Boots', ['boots', 'shoes', 'safety-boots', 'safety boots']),
    'feet': ('No Safety Boots', ['boots', 'shoes', 'safety-boots', 'safety boots']),
    'hand': ('No Gloves', ['gloves', 'glove']),
    'hands': ('No Gloves', ['gloves', 'glove']),
}

GOGGLES_DETECTION_BUFFER = 1.0   
HELMET_DETECTION_BUFFER = 1.0   
VEST_DETECTION_BUFFER = 1.0     
MASK_DETECTION_BUFFER = 1.0     
GLOVES_DETECTION_BUFFER = 1.0   
BOOTS_DETECTION_BUFFER = 1.0    

PPE_EQUIPMENT = ['helmet', 'face-mask', 'facemask', 'mask', 'glasses', 'goggles', 
                 'shoes', 'boots', 'safety-glasses', 'safety-vest', 'gloves', 'glove']


class PersonTracker:
    """
    Enhanced person tracker using IOU-based matching with stability improvements.
    
    Features for stable tracking:
    - Exponential Moving Average (EMA) smoothing for bounding boxes
    - Velocity prediction for fast-moving persons
    - Combined scoring (IOU + distance + size similarity)
    - Track history for better predictions
    - Hungarian algorithm for optimal global assignment
    """
    
    def __init__(self, iou_threshold: float = 0.3, max_frames_missing: int = 30):
        self.tracks = {} 
        self.next_id = 1
        self.iou_threshold = iou_threshold
        self.max_frames_missing = max_frames_missing
        
        self.smoothing_factor = 0.3
        
        self.iou_weight = 0.4
        self.distance_weight = 0.35
        self.size_weight = 0.25
    
    def reset(self):
        """Reset tracker for new video."""
        self.tracks = {}
        self.next_id = 1
    
    def _compute_iou(self, box1: tuple, box2: tuple) -> float:
        """Compute Intersection over Union between two boxes."""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y2_1, y2_2)
        
        if xi2 <= xi1 or yi2 <= yi1:
            return 0.0
        
        inter_area = (xi2 - xi1) * (yi2 - yi1)
        
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = area1 + area2 - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def _get_center(self, box: tuple) -> tuple:
        """Get center point of bounding box."""
        x1, y1, x2, y2 = box
        return ((x1 + x2) / 2, (y1 + y2) / 2)
    
    def _get_size(self, box: tuple) -> tuple:
        """Get width and height of bounding box."""
        x1, y1, x2, y2 = box
        return (x2 - x1, y2 - y1)
    
    def _compute_center_distance(self, box1: tuple, box2: tuple) -> float:
        """Compute normalized distance between centers of two boxes."""
        cx1, cy1 = self._get_center(box1)
        cx2, cy2 = self._get_center(box2)
        
        w1, h1 = self._get_size(box1)
        w2, h2 = self._get_size(box2)
        avg_size = max((w1 + w2 + h1 + h2) / 4, 1)
        
        dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
        return dist / avg_size 
    
    def _compute_size_similarity(self, box1: tuple, box2: tuple) -> float:
        """Compute size similarity between two boxes (0-1, 1 = identical size)."""
        w1, h1 = self._get_size(box1)
        w2, h2 = self._get_size(box2)
        
        area1 = w1 * h1
        area2 = w2 * h2
        
        if area1 == 0 or area2 == 0:
            return 0.0
        
        return min(area1, area2) / max(area1, area2)
    
    def _predict_position(self, track_data: dict, frames_ahead: int = 1) -> tuple:
        """
        Predict future position based on velocity history.
        Returns predicted bounding box.
        """
        bbox = track_data['bbox']
        
        if 'velocity' not in track_data or track_data['velocity'] is None:
            return bbox
        
        vx, vy = track_data['velocity']
        x1, y1, x2, y2 = bbox
        
        pred_x1 = x1 + vx * frames_ahead
        pred_y1 = y1 + vy * frames_ahead
        pred_x2 = x2 + vx * frames_ahead
        pred_y2 = y2 + vy * frames_ahead
        
        return (pred_x1, pred_y1, pred_x2, pred_y2)
    
    def _smooth_bbox(self, old_bbox: tuple, new_bbox: tuple) -> tuple:
        """
        Apply Exponential Moving Average smoothing to bounding box.
        Reduces jitter while staying responsive to movement.
        """
        alpha = self.smoothing_factor
        
        x1_old, y1_old, x2_old, y2_old = old_bbox
        x1_new, y1_new, x2_new, y2_new = new_bbox
        
        x1 = alpha * x1_old + (1 - alpha) * x1_new
        y1 = alpha * y1_old + (1 - alpha) * y1_new
        x2 = alpha * x2_old + (1 - alpha) * x2_new
        y2 = alpha * y2_old + (1 - alpha) * y2_new
        
        return (int(x1), int(y1), int(x2), int(y2))
    
    def _update_velocity(self, track_data: dict, new_bbox: tuple, frame_diff: int):
        """Update velocity estimate based on position change."""
        if frame_diff <= 0:
            return
        
        old_cx, old_cy = self._get_center(track_data['bbox'])
        new_cx, new_cy = self._get_center(new_bbox)
        
        vx = (new_cx - old_cx) / frame_diff
        vy = (new_cy - old_cy) / frame_diff
        
        if 'velocity' in track_data and track_data['velocity'] is not None:
            old_vx, old_vy = track_data['velocity']
            vx = 0.5 * old_vx + 0.5 * vx
            vy = 0.5 * old_vy + 0.5 * vy
        
        track_data['velocity'] = (vx, vy)
    
    def _compute_match_score(self, detection_bbox: tuple, track_data: dict, 
                              frame_num: int) -> float:
        """
        Compute combined matching score using multiple features.
        Returns score in range [0, 1], higher is better match.
        """
        frames_since = frame_num - track_data['last_seen']
        predicted_bbox = self._predict_position(track_data, frames_since)
        
        iou = self._compute_iou(detection_bbox, predicted_bbox)
        
        norm_dist = self._compute_center_distance(detection_bbox, predicted_bbox)
        norm_dist = self._compute_center_distance(detection_bbox, predicted_bbox)
        dist_score = max(0, 1 - norm_dist / 2)  
        
        size_score = self._compute_size_similarity(detection_bbox, predicted_bbox)
        
        combined = (self.iou_weight * iou + 
                   self.distance_weight * dist_score + 
                   self.size_weight * size_score)
        
        return combined
    
    def update(self, detections: list, frame_num: int) -> list:
        """
        Update tracks with new detections using improved matching.
        
        Uses combined scoring with Hungarian algorithm for optimal assignment.
        
        Args:
            detections: List of (bbox, conf) tuples for detected persons
            frame_num: Current frame number
            
        Returns:
            List of (bbox, track_id, conf) with assigned track IDs
        """
        stale_ids = [tid for tid, data in self.tracks.items() 
                     if frame_num - data['last_seen'] > self.max_frames_missing]
        for tid in stale_ids:
            del self.tracks[tid]
        
        if len(detections) == 0:
            return []
        
        results = []
        matched_tracks = set()
        matched_detections = set()
        
        track_ids = list(self.tracks.keys())
        
        all_matches = []
        for det_idx, (bbox, conf) in enumerate(detections):
            for track_id in track_ids:
                track_data = self.tracks[track_id]
                score = self._compute_match_score(bbox, track_data, frame_num)
                if score >= 0.15:  
                    all_matches.append((score, det_idx, track_id))
        
        all_matches.sort(reverse=True, key=lambda x: x[0])
        
        for score, det_idx, track_id in all_matches:
            if det_idx in matched_detections or track_id in matched_tracks:
                continue
            
            bbox, conf = detections[det_idx]
            track_data = self.tracks[track_id]
            
            frame_diff = frame_num - track_data['last_seen']
            self._update_velocity(track_data, bbox, frame_diff)
            
            smoothed_bbox = self._smooth_bbox(track_data['bbox'], bbox)
            
            track_data['bbox'] = smoothed_bbox
            track_data['last_seen'] = frame_num
            track_data['confidence'] = conf
            
            matched_tracks.add(track_id)
            matched_detections.add(det_idx)
            results.append((smoothed_bbox, track_id, conf))
        
        for det_idx, (bbox, conf) in enumerate(detections):
            if det_idx in matched_detections:
                continue
            
            new_id = self.next_id
            self.next_id += 1
            self.tracks[new_id] = {
                'bbox': bbox,
                'last_seen': frame_num,
                'velocity': None,
                'confidence': conf
            }
            results.append((bbox, new_id, conf))
        
        return results


@dataclass
class ProcessingResultSimple:
    """Processing result."""
    success: bool
    total_frames: int
    processed_frames: int
    fps: float
    duration: float
    width: int
    height: int
    individual_profiles: dict
    violations: list
    person_worn_ppe: dict = None  
    annotated_video_path: str = None
    employee_mapping: dict = None  # track_id -> {employee_id, employee_name}
    unknown_snapshots: dict = None  # track_id -> snapshot_path
    error_message: Optional[str] = None


class VideoPipeline:
    """
    Pipeline using YOLO detection with configurable person tracking.
    
    Supports two tracking methods (configurable in config.py):
    - IOU: Position-based overlap matching (robust to appearance changes)
    - Cosine: Appearance-based matching (better re-identification)
    """
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.model = YOLO(self.model_path)
        self.aggregator = ViolationAggregator()
        
        self.tracking_method = settings.TRACKING_METHOD
        
        self.person_tracker = PersonTracker(
            iou_threshold=settings.IOU_TRACKING_THRESHOLD,
            max_frames_missing=settings.IOU_MAX_FRAMES_MISSING
        )
        
        self.detection_interval_seconds = settings.DETECTION_INTERVAL_SECONDS
        self.frame_skip = settings.FRAME_SKIP
        
        self.is_processing = False
        self.progress = 0.0
        
        self.track_first_seen: Dict[int, int] = {}
        
        self.captured_violations: set = set()
        
        self.person_worn_ppe: Dict[int, set] = {}
        
        self.person_goggles_last_seen: Dict[int, float] = {}
        self.person_goggles_last_seen: Dict[int, float] = {}
        
        self.person_helmet_last_seen: Dict[int, float] = {}
        
        self.person_vest_last_seen: Dict[int, float] = {}
        
        self.person_mask_last_seen: Dict[int, float] = {}
        
        self.person_gloves_last_seen: Dict[int, float] = {}
        
        self.person_boots_last_seen: Dict[int, float] = {}
        
        self.detected_equipment: List[dict] = []
        
        self.violation_display_threshold = settings.VIOLATION_DISPLAY_THRESHOLD
        
        self.class_names = self.model.names if hasattr(self.model, 'names') else {}
        
        # Face recognition service
        self.face_service: 'FaceRecognitionService' = None
        if FACE_SERVICE_AVAILABLE:
            self.face_service = get_face_service()
        
        import torch
        self.device = '0' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Pipeline with custom person tracking initialized on device: {self.device}")
        logger.info(f"Model classes: {self.class_names}")
    
    def reset(self):
        """Reset for new video."""
        self.aggregator.reset()
        self.person_tracker.reset()
        self.is_processing = False
        self.progress = 0.0
        self.track_first_seen = {}
        self.captured_violations = set()
        self.person_worn_ppe = {}
        self.person_goggles_last_seen = {}
        self.person_helmet_last_seen = {}
        self.person_vest_last_seen = {}
        self.person_mask_last_seen = {}
        self.person_gloves_last_seen = {}
        self.person_boots_last_seen = {}
        self.detected_equipment = []
        self.model = YOLO(self.model_path)
        # Reset face recognition per-session state (keep employee encodings loaded)
        if self.face_service:
            self.face_service.reset()
            self.face_service.load_employees_sync()
    
    def _is_ppe_equipment(self, class_name: str) -> bool:
        """Check if class is PPE equipment (indicates compliance)."""
        class_lower = class_name.lower()
        return any(ppe in class_lower or class_lower in ppe for ppe in PPE_EQUIPMENT)
    
    def _can_capture(self, track_id: int, vtype: str, ts: float) -> bool:
        """Check if we should capture - only one snapshot per person per violation type."""
        key = (track_id, vtype)
        if key in self.captured_violations:
            return False  
        self.captured_violations.add(key)
        return True
    
    def _should_skip_violation(self, track_id: int, violation_type: str) -> bool:
        """
        Check if violation should be skipped because person has worn corresponding PPE.
        
        If a person is detected wearing PPE at any point, they don't get violations
        for that missing PPE type.
        
        NOTE: 'No Goggles', 'No Gloves', 'No Safety Boots', and 'No Face Mask' are handled 
        dynamically per-frame, not by cumulative tracking, so they're excluded from this skip logic.
        """
        DYNAMIC_VIOLATIONS = ['No Helmet', 'No Goggles', 'No Gloves', 'No Safety Boots', 'No Face Mask', 'No Safety Vest']
        if violation_type in DYNAMIC_VIOLATIONS:
            return False
        
        worn_ppe = self.person_worn_ppe.get(track_id, set())
        required_ppe = VIOLATION_TO_PPE.get(violation_type, [])
        
        for ppe in required_ppe:
            for worn_item in worn_ppe:
                if ppe in worn_item or worn_item in ppe:
                    logger.debug(f"Skipping {violation_type} for Person-{track_id}: detected wearing {worn_item}")
                    return True
        return False
    
    def _record_person_ppe(self, track_id: int, ppe_type: str):
        """Record that a person has been detected wearing a specific PPE item."""
        if track_id not in self.person_worn_ppe:
            self.person_worn_ppe[track_id] = set()
        
        ppe_lower = ppe_type.lower()
        if ppe_lower not in self.person_worn_ppe[track_id]:
            self.person_worn_ppe[track_id].add(ppe_lower)
            logger.info(f"PPE Detected: Person-{track_id} wearing {ppe_type}")
    
    def _convert_to_browser_compatible(self, input_path: str, output_path: str) -> bool:
        """Convert video to browser-compatible format using ffmpeg."""
        try:
            if not shutil.which('ffmpeg'):
                logger.warning("ffmpeg not found, video may not play in browser")
                return False
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                output_path
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except Exception as e:
            logger.error(f"ffmpeg conversion failed: {e}")
            return False
    
    def process_video_sync(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> ProcessingResultSimple:
        """Process video with YOLO native tracking."""
        self.reset()
        self.is_processing = True
        
        logger.info(f"Processing with YOLO native tracking: {video_path}")
        
        video_id = uuid.uuid4().hex[:8]
        temp_output = os.path.join(settings.UPLOAD_DIR, f"temp_{video_id}.mp4")
        final_output = os.path.join(settings.UPLOAD_DIR, f"annotated_{video_id}.mp4")
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Cannot open: {video_path}")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(f"Video: {total_frames} frames, {fps:.1f} FPS, {width}x{height}")
            
            codecs_to_try = [
                ('avc1', '.mp4'),   
                ('H264', '.mp4'),   
                ('X264', '.mp4'),   
                ('mp4v', '.mp4'),   
            ]
            
            out = None
            for codec, ext in codecs_to_try:
                try:
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    test_path = os.path.join(settings.UPLOAD_DIR, f"annotated_{video_id}{ext}")
                    out = cv2.VideoWriter(test_path, fourcc, fps, (width, height))
                    if out.isOpened():
                        final_output = test_path
                        logger.info(f"Using codec: {codec}")
                        break
                    out.release()
                except:
                    continue
            
            if out is None or not out.isOpened():
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                final_output = os.path.join(settings.UPLOAD_DIR, f"annotated_{video_id}.mp4")
                out = cv2.VideoWriter(final_output, fourcc, fps, (width, height))
                logger.warning("Using mp4v codec - video may not play in browser")
            
            self.aggregator.fps = fps
            
            if self.detection_interval_seconds > 0:
                effective_frame_skip = max(1, int(fps * self.detection_interval_seconds))
                logger.info(f"Using time-based detection: every {self.detection_interval_seconds}s = every {effective_frame_skip} frames")
            else:
                effective_frame_skip = self.frame_skip
                logger.info(f"Using frame-based detection: every {effective_frame_skip} frames")
            
            frame_num = 0
            processed = 0
            
            last_annotations = {
                'persons': [],      
                'violations': [],   
                'ppe_items': [],    
                'timestamp': 0.0,
                'total_violations': 0
            }
            
            def draw_annotations_on_frame(frame, annotations, current_timestamp):
                """Re-draw stored annotations on a frame for smooth visualization."""
                annotated = frame.copy()
                
                for person_bbox, track_id in annotations['persons']:
                    px1, py1, px2, py2 = [int(c) for c in person_bbox]
                    cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 0), 2)
                    # Use employee name if available
                    person_label = annotations.get('person_names', {}).get(track_id, f"Unknown-{track_id}")
                    cv2.putText(annotated, person_label, (px1, py1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                for ppe_bbox, cls_name in annotations['ppe_items']:
                    ex1, ey1, ex2, ey2 = [int(c) for c in ppe_bbox]
                    cv2.rectangle(annotated, (ex1, ey1), (ex2, ey2), (255, 0, 0), 2)
                    cv2.putText(annotated, cls_name, (ex1, ey1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                for vbox, vtype, track_id in annotations['violations']:
                    vx1, vy1, vx2, vy2 = [int(c) for c in vbox]
                    cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), (0, 0, 255), 3)
                    person_name = annotations.get('person_names', {}).get(track_id, f"Unknown-{track_id}")
                    label = f"{person_name}: {vtype}"
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                    cv2.rectangle(annotated, (vx1, vy1 - label_size[1] - 10),
                                 (vx1 + label_size[0] + 10, vy1), (0, 0, 255), -1)
                    cv2.putText(annotated, label, (vx1 + 5, vy1 - 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                num_persons = len(set(p[1] for p in annotations['persons']))
                info = f"Time: {current_timestamp:.1f}s | Persons: {num_persons} | Violations: {annotations['total_violations']}"
                cv2.rectangle(annotated, (5, 5), (500, 40), (0, 0, 0), -1)
                cv2.putText(annotated, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                return annotated
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                current_timestamp = frame_num / fps
                
                if frame_num % effective_frame_skip == 0:
                    annotated = self._process_frame_with_tracking(
                        frame, frame_num, video_id, fps, last_annotations
                    )
                    processed += 1
                    self.progress = (frame_num / total_frames) * 100
                    if progress_callback:
                        try:
                            progress_callback(self.progress)
                        except:
                            pass
                else:
                    annotated = draw_annotations_on_frame(frame, last_annotations, current_timestamp)
                
                out.write(annotated)
                frame_num += 1
            
            cap.release()
            out.release()
            
            annotated_path = final_output
            
            profiles = self.aggregator.get_all_profiles()
            
            # Build employee mapping from face service
            employee_mapping = {}  # track_id -> {employee_id, employee_name}
            unknown_snapshots = {}  # track_id -> snapshot_path
            if self.face_service:
                for tid in profiles:
                    emp_id, emp_name = self.face_service.track_id_to_employee.get(tid, (None, None))
                    employee_mapping[tid] = {'employee_id': emp_id, 'employee_name': emp_name}
                unknown_snapshots = self.face_service.unknown_snapshots.copy()
            
            violations = []
            for p in profiles.values():
                emp_info = employee_mapping.get(p.track_id, {})
                display_name = emp_info.get('employee_name') or f"Unknown-{p.track_id}"
                for v in p.violations:
                    violations.append({
                        "track_id": p.track_id,
                        "person_name": display_name,
                        "employee_id": emp_info.get('employee_id'),
                        "type": v.violation_type,
                        "confidence": v.confidence,
                        "frame": v.frame_number,
                        "timestamp": v.timestamp,
                        "bbox": v.bbox,
                        "image_path": v.image_path
                    })
            
            logger.info(f"Complete: {len(violations)} violations, {len(profiles)} persons")
            
            for tid, profile in profiles.items():
                emp_name = employee_mapping.get(tid, {}).get('employee_name') or f"Unknown-{tid}"
                if profile.violation_count > 0:
                    types_str = ', '.join(f'{t}:{c}' for t, c in profile.violation_types.items())
                    logger.info(f"{emp_name}: {profile.violation_count} violations ({types_str})")
            
            return ProcessingResultSimple(
                success=True, total_frames=total_frames, processed_frames=processed,
                fps=fps, duration=duration, width=width, height=height,
                individual_profiles={tid: p for tid, p in profiles.items()},
                violations=violations, 
                person_worn_ppe=self.person_worn_ppe.copy(),
                annotated_video_path=annotated_path,
                employee_mapping=employee_mapping,
                unknown_snapshots=unknown_snapshots
            )
            
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return ProcessingResultSimple(
                success=False, total_frames=0, processed_frames=0,
                fps=0, duration=0, width=0, height=0,
                individual_profiles={}, violations=[], error_message=str(e)
            )
        finally:
            self.is_processing = False
    
    def _process_frame_with_tracking(
        self, frame: np.ndarray, frame_num: int, video_id: str, fps: float,
        last_annotations: dict = None
    ) -> np.ndarray:
        """
        Process frame with custom IOU-based person tracking.
        
        1. Detect all objects using YOLO
        2. Use custom PersonTracker for consistent person IDs
        3. Associate violations with nearest tracked person
        4. Record detected PPE equipment
        5. Store annotation data in last_annotations for smooth skipped-frame rendering
        """
        timestamp = frame_num / fps
        
        results = self.model.predict(
            frame,
            conf=settings.CONFIDENCE_THRESHOLD,
            iou=settings.IOU_THRESHOLD,
            device=self.device,
            verbose=False
        )
        
        annotated = frame.copy()
        
        if not results or len(results) == 0:
            return annotated
        
        result = results[0]
        boxes = result.boxes
        
        if boxes is None or len(boxes) == 0:
            return annotated
        
        person_detections = []  
        violations = [] 
        ppe_items = [] 
        body_parts = [] 
        
        NO_PPE_KEYWORDS = {
            'no-mask': 'No Face Mask', 'no_mask': 'No Face Mask', 'no mask': 'No Face Mask', 'nomask': 'No Face Mask',
            'no-goggles': 'No Goggles', 'no_goggles': 'No Goggles', 'no goggles': 'No Goggles', 'nogoggles': 'No Goggles',
            'no-glasses': 'No Goggles', 'no_glasses': 'No Goggles', 'no glasses': 'No Goggles',
            'no-helmet': 'No Helmet', 'no_helmet': 'No Helmet', 'no helmet': 'No Helmet', 'nohelmet': 'No Helmet',
            'no-boots': 'No Safety Boots', 'no_boots': 'No Safety Boots', 'no boots': 'No Safety Boots',
            'no-gloves': 'No Gloves', 'no_gloves': 'No Gloves', 'no gloves': 'No Gloves',
            'no-vest': 'No Safety Vest', 'no_vest': 'No Safety Vest', 'no vest': 'No Safety Vest',
        }
        
        BODY_PART_TO_VIOLATION = {
            'face': ('No Face Mask', ['face-mask', 'facemask', 'mask', 'face mask']),
            'eyes': ('No Goggles', ['glasses', 'goggles', 'safety-glasses', 'eye protection']),
            'eye': ('No Goggles', ['glasses', 'goggles', 'safety-glasses', 'eye protection']),
            'head': ('No Helmet', ['helmet', 'hard hat', 'hardhat']),
            'hand': ('No Gloves', ['gloves', 'glove']),
            'hands': ('No Gloves', ['gloves', 'glove']),
            'foot': ('No Safety Boots', ['boots', 'shoes', 'safety-boots']),
            'feet': ('No Safety Boots', ['boots', 'shoes', 'safety-boots']),
        }
        
        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy()
            x1, y1, x2, y2 = [int(c) for c in xyxy]
            conf = float(boxes.conf[i].cpu().numpy())
            cls_id = int(boxes.cls[i].cpu().numpy())
            cls_name = self.class_names.get(cls_id, f"class_{cls_id}")
            bbox = (x1, y1, x2, y2)
            cls_lower = cls_name.lower()
            
            if cls_lower == 'person':
                person_detections.append((bbox, conf))
            else:
                violation_type = None
                for keyword, vtype in NO_PPE_KEYWORDS.items():
                    if keyword in cls_lower:
                        violation_type = vtype
                        break
                
                if violation_type:
                    violations.append((bbox, violation_type, conf))
                elif cls_lower in BODY_PART_TO_VIOLATION:
                    body_parts.append((bbox, cls_lower, conf))
                elif self._is_ppe_equipment(cls_name):
                    ppe_items.append((bbox, cls_name, conf))
                    self.detected_equipment.append({
                        'frame': frame_num,
                        'timestamp': timestamp,
                        'type': cls_name,
                        'confidence': conf,
                        'bbox': bbox
                    })
        
        persons = self.person_tracker.update(person_detections, frame_num)
        
        if frame_num % 30 == 0:
            logger.info(f"Frame {frame_num}: {len(persons)} persons (tracked), {len(violations)} violations, {len(ppe_items)} PPE")
        
        def find_closest_person(vbox):
            """Find person whose bbox is closest/overlapping with violation bbox."""
            vx1, vy1, vx2, vy2 = vbox
            vcx, vcy = (vx1 + vx2) / 2, (vy1 + vy2) / 2  
            
            best_person = None
            best_dist = float('inf')
            
            for person_bbox, person_tid, person_conf in persons:
                px1, py1, px2, py2 = person_bbox
                pcx, pcy = (px1 + px2) / 2, (py1 + py2) / 2
                dist = ((vcx - pcx) ** 2 + (vcy - pcy) ** 2) ** 0.5
                
                if vx1 >= px1 - 50 and vx2 <= px2 + 50 and vy1 >= py1 - 50 and vy2 <= py2 + 50:
                    dist = 0  
                
                if dist < best_dist:
                    best_dist = dist
                    best_person = (person_bbox, person_tid)
            
            return best_person
        
        for person_bbox, track_id, person_conf in persons:
            px1, py1, px2, py2 = person_bbox
            
            if track_id not in self.track_first_seen:
                self.track_first_seen[track_id] = frame_num
                logger.info(f"Tracking: New Person track_id={track_id}")
            
            # Try to identify person via face recognition
            display_name = f"Unknown-{track_id}"
            if self.face_service:
                emp_id, emp_name = self.face_service.identify_person(
                    frame, person_bbox, track_id, video_id, frame_num
                )
                if emp_name:
                    display_name = emp_name
            
            cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 0), 2)
            label = display_name
            cv2.putText(annotated, label, (px1, py1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        current_frame_ppe = {}  
        
        for ppe_bbox, cls_name, conf in ppe_items:
            ex1, ey1, ex2, ey2 = ppe_bbox
            cv2.rectangle(annotated, (ex1, ey1), (ex2, ey2), (255, 0, 0), 2)
            cv2.putText(annotated, cls_name, (ex1, ey1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
            ppe_cx, ppe_cy = (ex1 + ex2) / 2, (ey1 + ey2) / 2  
            
            for person_bbox, person_tid, person_conf in persons:
                px1, py1, px2, py2 = person_bbox
                tolerance = 30  
                if (px1 - tolerance <= ppe_cx <= px2 + tolerance and 
                    py1 - tolerance <= ppe_cy <= py2 + tolerance):
                    self._record_person_ppe(person_tid, cls_name)
                    if person_tid not in current_frame_ppe:
                        current_frame_ppe[person_tid] = set()
                    current_frame_ppe[person_tid].add(cls_name.lower())
                    break  
        

        GOGGLES_CLASSES = ['glasses', 'goggles', 'safety-glasses', 'safety glasses', 'eye protection', 'eyeglasses']
        
        
        def is_face_detected_for_person(person_bbox):
            """Check if any 'face' body part is detected near this person."""
            px1, py1, px2, py2 = person_bbox
            for body_bbox, body_part, _ in body_parts:
                if body_part == 'face':
                   
                    bx1, by1, bx2, by2 = body_bbox
                    face_cx, face_cy = (bx1 + bx2) / 2, (by1 + by2) / 2
                   
                    tolerance = 50
                    if (px1 - tolerance <= face_cx <= px2 + tolerance and
                        py1 - tolerance <= face_cy <= py2 + tolerance):
                        return True
            return False
        
        
        def is_hand_detected_for_person(person_bbox):
            """Check if 'hand' or 'hands' body part is detected near this person."""
            px1, py1, px2, py2 = person_bbox
            for body_bbox, body_part, _ in body_parts:
                if body_part in ['hand', 'hands']:
                   
                    bx1, by1, bx2, by2 = body_bbox
                    hand_cx, hand_cy = (bx1 + bx2) / 2, (by1 + by2) / 2
                   
                    tolerance = 50
                    if (px1 - tolerance <= hand_cx <= px2 + tolerance and
                        py1 - tolerance <= hand_cy <= py2 + tolerance):
                        return True
            return False

        
        def is_foot_detected_for_person(person_bbox):
            """Check if 'foot' or 'feet' body part is detected near this person."""
            px1, py1, px2, py2 = person_bbox
            for body_bbox, body_part, _ in body_parts:
                if body_part in ['foot', 'feet', 'shoe', 'shoes']:
                   
                    bx1, by1, bx2, by2 = body_bbox
                    foot_cx, foot_cy = (bx1 + bx2) / 2, (by1 + by2) / 2
                   
                    tolerance = 50
                    if (px1 - tolerance <= foot_cx <= px2 + tolerance and
                        py1 - tolerance <= foot_cy <= py2 + tolerance):
                        return True
            return False
        
        
        def is_head_detected_for_person(person_bbox):
            """Check if 'head' body part is detected near this person."""
            px1, py1, px2, py2 = person_bbox
            for body_bbox, body_part, _ in body_parts:
                if body_part in ['head', 'face']:
                   
                    bx1, by1, bx2, by2 = body_bbox
                    head_cx, head_cy = (bx1 + bx2) / 2, (by1 + by2) / 2
                   
                    tolerance = 50
                    if (px1 - tolerance <= head_cx <= px2 + tolerance and
                        py1 - tolerance <= head_cy <= py2 + tolerance):
                        return True
            return False
        
        for person_bbox, track_id, person_conf in persons:
            
            if not is_face_detected_for_person(person_bbox):
                
                if track_id in self.person_goggles_last_seen:
                    del self.person_goggles_last_seen[track_id]
                continue
            
            
            person_ppe = current_frame_ppe.get(track_id, set())
            
            
            goggles_detected = False
            for ppe_item in person_ppe:
                for goggles_type in GOGGLES_CLASSES:
                    if goggles_type in ppe_item or ppe_item in goggles_type:
                        goggles_detected = True
                        break
                if goggles_detected:
                    break
            
            if goggles_detected:
                
                self.person_goggles_last_seen[track_id] = timestamp
            else:
                
                last_seen = self.person_goggles_last_seen.get(track_id, -999)  
                
                if last_seen == -999:
                    
                    self.person_goggles_last_seen[track_id] = timestamp
                else:
                    time_without_goggles = timestamp - last_seen
                    if time_without_goggles >= GOGGLES_DETECTION_BUFFER:
                        
                        px1, py1, px2, py2 = person_bbox
                        head_height = int((py2 - py1) * 0.3)
                        goggles_bbox = (px1, py1, px2, py1 + head_height)
                        violations.append((goggles_bbox, 'No Goggles', person_conf))
                        if frame_num % 30 == 0:
                            logger.info(f"No Goggles violation for Person-{track_id} (no goggles for {time_without_goggles:.1f}s)")
        
        
        HELMET_CLASSES = ['helmet', 'hard hat', 'hardhat', 'safety helmet']
        
        for person_bbox, track_id, person_conf in persons:
            
            if not is_head_detected_for_person(person_bbox):
                
                if track_id in self.person_helmet_last_seen:
                    del self.person_helmet_last_seen[track_id]
                continue
            person_ppe = current_frame_ppe.get(track_id, set())
            
            helmet_detected = False
            for ppe_item in person_ppe:
                for helmet_type in HELMET_CLASSES:
                    if helmet_type in ppe_item or ppe_item in helmet_type:
                        helmet_detected = True
                        break
                if helmet_detected:
                    break
            
            if helmet_detected:
                
                self.person_helmet_last_seen[track_id] = timestamp
            else:
                
                last_seen = self.person_helmet_last_seen.get(track_id, -999)  
                
                if last_seen == -999:
                    
                    self.person_helmet_last_seen[track_id] = timestamp
                else:
                    time_without_helmet = timestamp - last_seen
                    if time_without_helmet >= HELMET_DETECTION_BUFFER:
                        
                        
                        px1, py1, px2, py2 = person_bbox
                        head_height = int((py2 - py1) * 0.4)
                        helmet_bbox = (px1, py1, px2, py1 + head_height)
                        violations.append((helmet_bbox, 'No Helmet', person_conf))
                        if frame_num % 30 == 0:
                            logger.info(f"No Helmet violation for Person-{track_id} (no helmet for {time_without_helmet:.1f}s)")
        
        
        VEST_CLASSES = ['vest', 'safety-vest', 'safety vest', 'hi-vis', 'high-visibility', 'reflective vest']
        
        for person_bbox, track_id, person_conf in persons:
            person_ppe = current_frame_ppe.get(track_id, set())
            
            vest_detected = False
            for ppe_item in person_ppe:
                for vest_type in VEST_CLASSES:
                    if vest_type in ppe_item or ppe_item in vest_type:
                        vest_detected = True
                        break
                if vest_detected:
                    break
            
            if vest_detected:
                
                self.person_vest_last_seen[track_id] = timestamp
            else:
                
                last_seen = self.person_vest_last_seen.get(track_id, -999)
                
                if last_seen == -999:
                    
                    self.person_vest_last_seen[track_id] = timestamp
                else:
                    time_without_vest = timestamp - last_seen
                    if time_without_vest >= VEST_DETECTION_BUFFER:
                        
                        
                        px1, py1, px2, py2 = person_bbox
                        person_height = py2 - py1
                        torso_top = py1 + int(person_height * 0.2)
                        torso_bottom = py1 + int(person_height * 0.8)
                        vest_bbox = (px1, torso_top, px2, torso_bottom)
                        violations.append((vest_bbox, 'No Safety Vest', person_conf))
                        if frame_num % 30 == 0:
                            logger.info(f"No Safety Vest violation for Person-{track_id} (no vest for {time_without_vest:.1f}s)")
        
        
        MASK_CLASSES = ['mask', 'face-mask', 'facemask', 'face mask', 'surgical mask', 'n95']
        
        for person_bbox, track_id, person_conf in persons:
            if not is_face_detected_for_person(person_bbox):
                
                if track_id in self.person_mask_last_seen:
                    del self.person_mask_last_seen[track_id]
                continue
            
            person_ppe = current_frame_ppe.get(track_id, set())
            
            mask_detected = False
            for ppe_item in person_ppe:
                for mask_type in MASK_CLASSES:
                    if mask_type in ppe_item or ppe_item in mask_type:
                        mask_detected = True
                        break
                if mask_detected:
                    break
            
            if mask_detected:
                
                self.person_mask_last_seen[track_id] = timestamp
            else:
                
                last_seen = self.person_mask_last_seen.get(track_id, -999)
                
                if last_seen == -999:
                    
                    self.person_mask_last_seen[track_id] = timestamp
                else:
                    time_without_mask = timestamp - last_seen
                    if time_without_mask >= MASK_DETECTION_BUFFER:
                        
                        
                        px1, py1, px2, py2 = person_bbox
                        face_height = int((py2 - py1) * 0.35)
                        mask_bbox = (px1, py1, px2, py1 + face_height)
                        violations.append((mask_bbox, 'No Face Mask', person_conf))
                        if frame_num % 30 == 0:
                            logger.info(f"No Face Mask violation for Person-{track_id} (no mask for {time_without_mask:.1f}s)")
        
        
        GLOVES_CLASSES = ['gloves', 'glove', 'hand protection', 'work gloves', 'safety gloves']
        
        for person_bbox, track_id, person_conf in persons:
            if not is_hand_detected_for_person(person_bbox):
                
                if track_id in self.person_gloves_last_seen:
                    del self.person_gloves_last_seen[track_id]
                continue
            person_ppe = current_frame_ppe.get(track_id, set())
            
            gloves_detected = False
            for ppe_item in person_ppe:
                for gloves_type in GLOVES_CLASSES:
                    if gloves_type in ppe_item or ppe_item in gloves_type:
                        gloves_detected = True
                        break
                if gloves_detected:
                    break
            
            if gloves_detected:
                
                self.person_gloves_last_seen[track_id] = timestamp
            else:
                
                last_seen = self.person_gloves_last_seen.get(track_id, -999)
                
                if last_seen == -999:
                    
                    self.person_gloves_last_seen[track_id] = timestamp
                else:
                    time_without_gloves = timestamp - last_seen
                    if time_without_gloves >= GLOVES_DETECTION_BUFFER:
                        
                        
                        px1, py1, px2, py2 = person_bbox
                        person_height = py2 - py1
                        hands_top = py1 + int(person_height * 0.4)
                        hands_bottom = py1 + int(person_height * 0.7)
                        gloves_bbox = (px1, hands_top, px2, hands_bottom)
                        violations.append((gloves_bbox, 'No Gloves', person_conf))
                        if frame_num % 30 == 0:
                            logger.info(f"No Gloves violation for Person-{track_id} (no gloves for {time_without_gloves:.1f}s)")
        
        
        BOOTS_CLASSES = ['boots', 'shoes', 'safety-boots', 'safety boots', 'safety shoes', 'work boots', 'footwear']
        
        for person_bbox, track_id, person_conf in persons:
            if not is_foot_detected_for_person(person_bbox):
                
                if track_id in self.person_boots_last_seen:
                    del self.person_boots_last_seen[track_id]
                continue
            person_ppe = current_frame_ppe.get(track_id, set())
            
            
            boots_detected = False
            for ppe_item in person_ppe:
                for boots_type in BOOTS_CLASSES:
                    if boots_type in ppe_item or ppe_item in boots_type:
                        boots_detected = True
                        break
                if boots_detected:
                    break
            
            if boots_detected:
                # Boots detected - update last seen time, no violation
                self.person_boots_last_seen[track_id] = timestamp
            else:
                # Boots NOT detected - check if 1.0 second buffer has passed
                last_seen = self.person_boots_last_seen.get(track_id, -999)
                
                if last_seen == -999:
                    # First time seeing this person without boots - start the timer
                    self.person_boots_last_seen[track_id] = timestamp
                else:
                    time_without_boots = timestamp - last_seen
                    if time_without_boots >= BOOTS_DETECTION_BUFFER:
                        # 1.0 second has passed without boots - trigger violation
                        # Use lower 30% of person bbox for boots (feet area)
                        px1, py1, px2, py2 = person_bbox
                        person_height = py2 - py1
                        feet_top = py1 + int(person_height * 0.7)
                        boots_bbox = (px1, feet_top, px2, py2)
                        violations.append((boots_bbox, 'No Safety Boots', person_conf))
                        if frame_num % 30 == 0:
                            logger.info(f"No Safety Boots violation for Person-{track_id} (no boots for {time_without_boots:.1f}s)")
        
        # NOTE: Legacy body-part based violation loop removed.
        # We now use the robust, buffered person-based checks above (Helmet, Vest, Mask, Gloves, Boots).
        # Body parts are only used as prerequisites for those checks.
        
        # THEN Process violations - skip if person has worn corresponding PPE
        frame_drawn_violations = []  # Track violations drawn in this frame for smooth skipped-frame rendering
        
        for vbox, vtype, conf in violations:
            vx1, vy1, vx2, vy2 = vbox
            
            # Find which person this violation belongs to
            person_bbox = None
            closest = find_closest_person(vbox)
            if closest:
                person_bbox, track_id = closest
            else:
                # No person found, use fallback ID
                track_id = 1
                if track_id not in self.track_first_seen:
                    self.track_first_seen[track_id] = frame_num
            
            # Check if this violation should be skipped because person has worn corresponding PPE
            if self._should_skip_violation(track_id, vtype):
                continue  # Skip this violation - person has worn the required PPE
            
            # Draw violation box (RED)
            cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), (0, 0, 255), 3)
            if vtype == 'No Goggles':
                logger.info(f"Drawing No Goggles box at ({vx1},{vy1})-({vx2},{vy2}) for Person-{track_id}")
            
            # Track this drawn violation for skipped-frame rendering
            frame_drawn_violations.append((vbox, vtype, track_id))
            
            # Violation label — use employee name if available
            if self.face_service:
                v_display_name = self.face_service.get_display_name(track_id)
            else:
                v_display_name = f"Unknown-{track_id}"
            label = f"{v_display_name}: {vtype}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(annotated, (vx1, vy1 - label_size[1] - 10),
                         (vx1 + label_size[0] + 10, vy1), (0, 0, 255), -1)
            cv2.putText(annotated, label, (vx1 + 5, vy1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Update aggregator with PERSON's track ID
            self.aggregator.update_individual(
                track_id=track_id,
                frame_number=frame_num,
                first_seen_frame=self.track_first_seen.get(track_id, frame_num)
            )
            
            # Capture violation image with cooldown
            # Only capture if confidence meets the display threshold
            if conf >= self.violation_display_threshold and self._can_capture(track_id, vtype, timestamp):
                bbox = (float(vx1), float(vy1), float(vx2), float(vy2))
                img_path = self._save_image(frame, bbox, video_id, frame_num, vtype, track_id, person_bbox)
                
                record = ViolationRecord(
                    violation_type=vtype,
                    confidence=conf,
                    frame_number=frame_num,
                    timestamp=timestamp,
                    bbox=bbox,
                    image_path=img_path
                )
                self.aggregator.profiles[track_id].add_violation(record)
                logger.info(f"VIOLATION: Person-{track_id} - {vtype}")
        
        # Frame info overlay
        active_persons = len([p for p in persons])
        total_violations = sum(p.violation_count for p in self.aggregator.profiles.values())
        info = f"Time: {timestamp:.1f}s | Persons: {len(set(p[1] for p in persons))} | Violations: {total_violations}"
        cv2.rectangle(annotated, (5, 5), (500, 40), (0, 0, 0), -1)
        cv2.putText(annotated, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Store annotation data for smooth skipped-frame rendering
        if last_annotations is not None:
            last_annotations['persons'] = [(p_bbox, p_tid) for p_bbox, p_tid, _ in persons]
            last_annotations['ppe_items'] = [(p_bbox, cls) for p_bbox, cls, _ in ppe_items]
            # Store violations that were drawn (not skipped)
            last_annotations['violations'] = frame_drawn_violations
            last_annotations['timestamp'] = timestamp
            last_annotations['total_violations'] = total_violations
            # Store person names for skipped-frame rendering
            person_names = {}
            for _, tid, _ in persons:
                if self.face_service:
                    person_names[tid] = self.face_service.get_display_name(tid)
                else:
                    person_names[tid] = f"Unknown-{tid}"
            last_annotations['person_names'] = person_names
        
        return annotated
    
    def _save_image(self, frame, bbox, video_id, frame_num, vtype, track_id, person_bbox=None) -> str:
        """Save violation snapshot with highlighting and min size."""
        try:
            h, w = frame.shape[:2]
            img = frame.copy()
            
            vx1, vy1, vx2, vy2 = [int(c) for c in bbox]
            
            # Determine initial crop area
            if person_bbox:
                # Crop the person
                cx1, cy1, cx2, cy2 = [int(c) for c in person_bbox]
                # Add 10% padding around person
                pw, ph = cx2 - cx1, cy2 - cy1
                pad_x, pad_y = int(pw * 0.1), int(ph * 0.1)
                cx1, cy1 = max(0, cx1 - pad_x), max(0, cy1 - pad_y)
                cx2, cy2 = min(w, cx2 + pad_x), min(h, cy2 + pad_y)
            else:
                # Fallback: Crop the violation box with 50% padding
                cx1, cy1, cx2, cy2 = vx1, vy1, vx2, vy2
                pw, ph = cx2 - cx1, cy2 - cy1
                pad_x, pad_y = int(pw * 0.5), int(ph * 0.5)
                cx1, cy1 = max(0, cx1 - pad_x), max(0, cy1 - pad_y)
                cx2, cy2 = min(w, cx2 + pad_x), min(h, cy2 + pad_y)
            
            # Enforce Minimum Size (200x200)
            target_w, target_h = 200, 200
            crop_w, crop_h = cx2 - cx1, cy2 - cy1
            
            if crop_w < target_w:
                diff = target_w - crop_w
                cx1 = max(0, cx1 - diff // 2)
                cx2 = min(w, cx2 + (diff - diff // 2))
                
            if crop_h < target_h:
                diff = target_h - crop_h
                cy1 = max(0, cy1 - diff // 2)
                cy2 = min(h, cy2 + (diff - diff // 2))
                
            # Perform Crop
            crop_img = img[cy1:cy2, cx1:cx2].copy()
            
            safe = vtype.replace(" ", "_").lower()
            fname = f"p{track_id}_{safe}_{video_id}_{frame_num}.jpg"
            path = os.path.join(settings.VIOLATIONS_IMG_DIR, fname)
            cv2.imwrite(path, crop_img)
            
            return f"/violation_images/{fname}"
        except Exception as e:
            logger.error(f"Save failed: {e}")
            return None
    
    def get_progress(self) -> float:
        return self.progress
    
    def is_active(self) -> bool:
        return self.is_processing
