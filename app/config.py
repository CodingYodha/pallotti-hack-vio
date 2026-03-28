"""
Application configuration settings.
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./violation_tracking.db"
    
    UPLOAD_DIR: str = "uploads"
    SNIPPETS_DIR: str = "snippets"
    VIOLATIONS_IMG_DIR: str = "violation_images" 
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024 
    ALLOWED_EXTENSIONS: list = [".mp4", ".avi", ".mov", ".mkv"]
    
    YOLO_MODEL_PATH: str = "ppe_model.pt" 
    WEBCAM_MODEL_PATH: str = "old.pt"       
    CONFIDENCE_THRESHOLD: float = 0.40 
    IOU_THRESHOLD: float = 0.45     
    
    VIOLATION_DISPLAY_THRESHOLD: float = 0.6  
    
    TRACKING_METHOD: Literal["iou", "cosine"] = "iou"
    
    
    IOU_TRACKING_THRESHOLD: float = 0.15 
    IOU_MAX_FRAMES_MISSING: int = 90 
    
    MAX_AGE: int = 150      
    N_INIT: int = 2     
    MAX_COSINE_DISTANCE: float = 0.8 
    
    DETECTION_INTERVAL_SECONDS: float = 0.0 
    
    FRAME_SKIP: int = 3     

    # How many frames to skip between face recognition attempts per-track.
    # 15 = attempt ~once every 0.5 s at 30fps. Lower = more CPU usage.
    FACE_RECOGNITION_INTERVAL: int = 15
    
    SNIPPET_DURATION: int = 5  
    
    VIOLATION_CLASSES: dict = {
        0: "No Helmet",
        1: "No Safety Vest", 
        2: "No Gloves",
        3: "No Safety Boots",
        4: "Restricted Zone Entry"
    }
    
    # SMTP Email configuration
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "codingyodha7706@gmail.com"
    SMTP_PASSWORD: str = "skuxrcgkmresdsmb"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

