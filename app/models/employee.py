"""
Employee model for face recognition and identification.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.database import Base


class Employee(Base):
    """
    Model for registered employees.
    
    Stores profile photo and face encoding for face-recognition-based
    identification during video/webcam/livestream processing.
    """
    
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    photo_path = Column(String(500), nullable=True)  # Path to profile photo
    face_encoding = Column(Text, nullable=True)  # JSON-serialized 128-d face encoding
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    def __repr__(self):
        return f"<Employee {self.id}: {self.name}>"
