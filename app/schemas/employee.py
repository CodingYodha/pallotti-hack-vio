"""
Pydantic schemas for Employee endpoints.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class EmployeeCreate(BaseModel):
    """Schema for creating a new employee."""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None


class EmployeeUpdate(BaseModel):
    """Schema for updating an employee."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None


class EmployeeResponse(BaseModel):
    """Schema for employee responses."""
    id: int
    name: str
    photo_path: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeListResponse(BaseModel):
    """Schema for list of employees."""
    employees: List[EmployeeResponse]
    total: int
