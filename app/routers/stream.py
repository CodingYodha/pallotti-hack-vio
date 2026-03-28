"""
Live RTSP / HTTP-MJPEG streaming router — multi-stream edition.

Each caller supplies (or gets auto-assigned) a unique stream_id.
The backend maintains one VideoPipeline + one stop-event per stream_id,
so multiple phones can be analysed simultaneously and independently.
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import cv2
import logging
import asyncio
import time
import uuid
from typing import Dict, Any

from app.ai.pipeline import VideoPipeline
from app.config import settings
from app.utils.email import send_batch_report_email

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-session state
# ---------------------------------------------------------------------------
# _sessions[stream_id] = {"pipeline": VideoPipeline, "stop_event": asyncio.Event}
_sessions: Dict[str, Dict[str, Any]] = {}


def _normalize_stream_url(url: str) -> str:
    """
    Auto-append /video for bare IP Webcam HTTP URLs.
    e.g. http://192.0.0.4:8080  →  http://192.0.0.4:8080/video
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        if not parsed.path or parsed.path == "/":
            url = url.rstrip("/") + "/video"
            logger.info(f"HTTP stream URL normalized to: {url}")
    return url


def _get_or_create_session(stream_id: str) -> Dict[str, Any]:
    """Return an existing session dict or create a fresh one."""
    if stream_id not in _sessions:
        pipeline = VideoPipeline(model_path=settings.WEBCAM_MODEL_PATH)
        logger.info(f"[{stream_id}] Created new pipeline.")
        _sessions[stream_id] = {
            "pipeline": pipeline,
            "stop_event": asyncio.Event(),
        }
    return _sessions[stream_id]


def _teardown_session(stream_id: str):
    """Remove a session from the registry after the stream ends."""
    if stream_id in _sessions:
        del _sessions[stream_id]
        logger.info(f"[{stream_id}] Session removed.")


# ---------------------------------------------------------------------------
# Frame generator
# ---------------------------------------------------------------------------

async def generate_frames(
    rtsp_url: str,
    stream_id: str,
    send_email: bool = False,
    mail_to: str = None,
):
    """
    Per-stream generator: opens the camera, runs AI inference on every Nth
    frame, and yields MJPEG multipart bytes back to the browser.
    """
    session = _get_or_create_session(stream_id)
    stop_event: asyncio.Event = session["stop_event"]
    stop_event.clear()

    rtsp_url = _normalize_stream_url(rtsp_url)

    # Use FFMPEG backend for reliable HTTP MJPEG + RTSP support
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        logger.error(f"[{stream_id}] Failed to open stream: {rtsp_url}")
        _teardown_session(stream_id)
        return

    logger.info(f"[{stream_id}] Connected to: {rtsp_url}")
    start_time = time.time()

    p: VideoPipeline = session["pipeline"]
    p.reset()

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps != fps:  # guard against 0 / NaN
        fps = 30.0
    p.aggregator.fps = fps

    frame_num = 0
    effective_frame_skip = max(p.frame_skip, 3)

    last_annotations = {
        "persons": [],
        "violations": [],
        "ppe_items": [],
        "timestamp": 0.0,
        "total_violations": 0,
    }

    try:
        while True:
            if stop_event.is_set():
                logger.info(f"[{stream_id}] Stop signal received.")
                break

            ret, frame = cap.read()
            if not ret:
                logger.warning(f"[{stream_id}] Stream ended or connection lost.")
                break

            if frame_num % effective_frame_skip != 0:
                frame_num += 1
                continue

            # Downscale for performance
            h, w = frame.shape[:2]
            max_dim = 640
            if w > max_dim or h > max_dim:
                scale = max_dim / max(w, h)
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

            annotated = p._process_frame_with_tracking(
                frame, frame_num, f"live_{stream_id}", fps, last_annotations
            )

            ret2, buffer = cv2.imencode(
                ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 40]
            )
            if not ret2:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )

            frame_num += 1
            await asyncio.sleep(0.001)

    except Exception as e:
        logger.error(f"[{stream_id}] Error during streaming: {e}")
    finally:
        cap.release()
        duration = time.time() - start_time
        logger.info(f"[{stream_id}] Stream closed after {duration:.1f}s.")

        if send_email and mail_to:
            profiles = p.aggregator.get_all_profiles()
            send_batch_report_email(profiles, mail_to, duration)

        _teardown_session(stream_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/live")
async def stream_live(
    rtsp_url: str = Query(..., description="RTSP or HTTP MJPEG URL"),
    stream_id: str = Query(None, description="Unique stream ID (auto-generated if omitted)"),
    send_email: bool = Query(False),
    mail_to: str = Query(None),
):
    """
    Stream live video from one source. Supply a unique stream_id to run
    multiple simultaneous streams.
    """
    if not rtsp_url:
        raise HTTPException(status_code=400, detail="rtsp_url is required")

    # Auto-assign a stable ID for this stream if the caller didn't provide one
    if not stream_id:
        stream_id = str(uuid.uuid4())
        logger.info(f"Auto-assigned stream_id: {stream_id}")

    return StreamingResponse(
        generate_frames(rtsp_url, stream_id, send_email, mail_to),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"X-Stream-Id": stream_id},
    )


@router.post("/stop")
async def stop_stream(
    stream_id: str = Query(None, description="ID of stream to stop. Omit to stop ALL."),
):
    """
    Signal one specific stream (or all streams) to stop gracefully.
    """
    if stream_id:
        session = _sessions.get(stream_id)
        if not session:
            # Session already gone (stream failed or ended) — treat as success
            logger.info(f"Stop requested for '{stream_id}' but session already cleaned up — OK.")
            return {"status": "already_stopped", "stream_id": stream_id}
        session["stop_event"].set()
        logger.info(f"Stop signal sent to stream: {stream_id}")
        return {"status": "stopping", "stream_id": stream_id}
    else:
        # Stop every active session
        for sid, sess in list(_sessions.items()):
            sess["stop_event"].set()
            logger.info(f"Stop signal sent to stream: {sid}")
        return {"status": "stopping_all", "count": len(_sessions)}


@router.get("/sessions")
async def list_sessions():
    """Return the list of currently active stream_ids."""
    return JSONResponse({"active": list(_sessions.keys()), "count": len(_sessions)})


@router.get("/face-data")
async def stream_face_data(
    stream_id: str = Query(..., description="Stream ID returned by the /live endpoint"),
):
    """
    Flaw 8 fix: expose face-recognition results for a live RTSP/HTTP stream session.

    The webcam WebSocket already delivers `employee_names` and `unknown_snapshots` in
    every JSON message. Live streams use a plain MJPEG response so there is no JSON
    side-channel. Clients can poll this endpoint to get the same data.

    Returns:
        employee_names   – {str(track_id): name} for all tracks seen so far
        unknown_snapshots – {str(track_id): snapshot_url} for unrecognised persons
    """
    session = _sessions.get(stream_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"No active session for stream_id '{stream_id}'. "
                   "The stream may have ended or the ID is incorrect.",
        )

    p: VideoPipeline = session["pipeline"]
    employee_names: dict = {}
    unknown_snapshots: dict = {}

    if p.face_service:
        for tid, (eid, ename) in p.face_service.track_id_to_employee.items():
            employee_names[str(tid)] = ename if ename else f"Unknown-{tid}"
        unknown_snapshots = {
            str(k): v for k, v in p.face_service.unknown_snapshots.items()
        }

    return JSONResponse({
        "stream_id": stream_id,
        "employee_names": employee_names,
        "unknown_snapshots": unknown_snapshots,
    })
