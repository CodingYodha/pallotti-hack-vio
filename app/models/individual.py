"""
TrackedIndividual model for temporary person IDs.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class TrackedIndividual(Base):
    """
    Model for tracked individuals within a video.
    
    Each individual gets a temporary, session-specific ID that is:
    - Valid only for the current video
    - Not persistent across videos
    - Not linked to any biometric data
    """
    
    __tablename__ = "tracked_individuals"
    
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(Integer, nullable=False)  # Deep SORT assigned ID
    
    # Tracking metadata
    first_seen_frame = Column(Integer)
    last_seen_frame = Column(Integer)
    first_seen_time = Column(Float)  # Timestamp in seconds
    last_seen_time = Column(Float)
    total_frames_tracked = Column(Integer, default=0)
    
    # Aggregated statistics
    total_violations = Column(Integer, default=0)
    confirmed_violations = Column(Integer, default=0)
    rejected_violations = Column(Integer, default=0)
    
    # Risk assessment
    risk_score = Column(Float, default=0.0)  # Based on violation frequency/severity
    
    # Fine status
    is_fined = Column(Integer, default=0) # SQLite Boolean (0/1)
    fine_amount = Column(Float, default=100.0)
    
    # PPE worn by this individual (comma-separated list)
    worn_equipment = Column(String, default="")  # e.g., "helmet,gloves,boots"
    
    # Linked employee (if face was recognized)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    employee_name = Column(String(100), nullable=True)  # Cached name for quick access
    snapshot_path = Column(String(500), nullable=True)  # Face snapshot for this individual
    
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    video = relationship("Video", back_populates="individuals")
    violations = relationship("Violation", back_populates="individual", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TrackedIndividual video={self.video_id}, track={self.track_id}>"
    
    @property
    def pending_violations(self):
        """Calculate pending violations count."""
        return self.total_violations - self.confirmed_violations - self.rejected_violations
