"""
Authentication Pydantic schemas.
"""

from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str


class UserResponse(BaseModel):
    """Schema for user response (no password)."""
    id: int
    username: str
    email: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
