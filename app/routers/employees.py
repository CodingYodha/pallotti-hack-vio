"""
Employee management router: CRUD operations for employee profiles.
"""

import os
import uuid
import json
import threading
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse, EmployeeListResponse
from app.services.face_recognition_service import (
    FaceRecognitionService, get_face_service, EMPLOYEE_PHOTOS_DIR, FACE_RECOGNITION_AVAILABLE
)

router = APIRouter()


def _invalidate_and_reload():
    """Flaw 3 fix: invalidate the face service cache and immediately trigger a
    background reload so the cache is never stale between requests."""
    svc = get_face_service()
    svc.invalidate_cache()
    # Reload in a daemon thread so we don't block the API response
    t = threading.Thread(target=svc.load_employees_sync, daemon=True)
    t.start()


@router.get("", response_model=EmployeeListResponse)
async def list_employees(db: AsyncSession = Depends(get_db)):
    """List all employees."""
    result = await db.execute(select(Employee).order_by(Employee.name))
    employees = result.scalars().all()
    return EmployeeListResponse(
        employees=[EmployeeResponse.model_validate(e) for e in employees],
        total=len(employees)
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single employee by ID."""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return EmployeeResponse.model_validate(emp)


@router.post("", response_model=EmployeeResponse)
async def create_employee(
    name: str = Form(...),
    photo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new employee with optional photo upload.
    If a photo is provided, the face encoding is extracted automatically.
    """
    photo_path = None
    face_encoding_json = None

    if photo:
        # Save photo
        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        fname = f"emp_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(EMPLOYEE_PHOTOS_DIR, fname)
        
        contents = await photo.read()
        with open(save_path, "wb") as f:
            f.write(contents)
        
        photo_path = f"/employee_photos/{fname}"
        
        # Flaw 1 fix: use singleton's models (avoids creating new MTCNN/ResNet per upload)
        face_encoding_json = get_face_service().encode_face_from_file(save_path)

    emp = Employee(
        name=name,
        photo_path=photo_path,
        face_encoding=face_encoding_json
    )
    db.add(emp)
    await db.flush()
    await db.refresh(emp)

    # Flaw 3 fix: invalidate + immediately reload in background
    _invalidate_and_reload()

    return EmployeeResponse.model_validate(emp)


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    name: Optional[str] = Form(None),
    photo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db)
):
    """Update an employee's name and/or photo."""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if name:
        emp.name = name

    if photo:
        # Delete old photo if exists
        if emp.photo_path:
            old_path = emp.photo_path.lstrip("/")
            if os.path.exists(old_path):
                os.remove(old_path)

        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        fname = f"emp_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(EMPLOYEE_PHOTOS_DIR, fname)
        
        contents = await photo.read()
        with open(save_path, "wb") as f:
            f.write(contents)
        
        emp.photo_path = f"/employee_photos/{fname}"
        
        # Flaw 1 fix: use singleton's models
        face_encoding_json = get_face_service().encode_face_from_file(save_path)
        emp.face_encoding = face_encoding_json

    await db.flush()
    await db.refresh(emp)

    # Flaw 3 fix: invalidate + immediately reload in background
    _invalidate_and_reload()

    return EmployeeResponse.model_validate(emp)


@router.delete("/{employee_id}")
async def delete_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an employee."""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Delete photo file
    if emp.photo_path:
        file_path = emp.photo_path.lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)

    await db.delete(emp)

    # Flaw 3 fix: invalidate + immediately reload in background
    _invalidate_and_reload()

    return {"detail": "Employee deleted"}


@router.post("/from-snapshot", response_model=EmployeeResponse)
async def create_employee_from_snapshot(
    name: str = Form(...),
    snapshot_path: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new employee from an auto-captured face snapshot.
    Used by the 'Name this person' UI flow.

    Flaw 7 fix: moves (not copies) the snapshot file so the original unknown_
    file is removed, preventing duplicate employee registrations from the same
    snapshot. Also removes the entry from the face service's unknown_snapshots
    cache so the UI no longer surfaces it.

    The snapshot_path is the URL path (e.g., /employee_photos/unknown_1_abc_42.jpg).
    """
    import shutil

    # Convert URL path to filesystem path
    fs_path = snapshot_path.lstrip("/")

    if not os.path.exists(fs_path):
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    # Flaw 1 fix: use singleton's models for encoding
    face_encoding_json = get_face_service().encode_face_from_file(fs_path)

    # Flaw 7 fix: MOVE the snapshot to a permanent employee photo (removes the unknown_ file)
    ext = os.path.splitext(fs_path)[1] or ".jpg"
    new_fname = f"emp_{uuid.uuid4().hex[:8]}{ext}"
    new_path = os.path.join(EMPLOYEE_PHOTOS_DIR, new_fname)
    shutil.move(fs_path, new_path)  # atomic rename — original unknown_ file is gone

    photo_url = f"/employee_photos/{new_fname}"

    emp = Employee(
        name=name,
        photo_path=photo_url,
        face_encoding=face_encoding_json
    )
    db.add(emp)
    await db.flush()
    await db.refresh(emp)

    # Flaw 7 fix: remove the snapshot from the face service cache so the UI won't
    # continue to show a "Name this person" card for someone who is now registered.
    svc = get_face_service()
    to_remove = [tid for tid, path in svc.unknown_snapshots.items() if path == snapshot_path]
    for tid in to_remove:
        svc.unknown_snapshots.pop(tid, None)

    # Flaw 3 fix: invalidate + immediately reload in background
    _invalidate_and_reload()

    return EmployeeResponse.model_validate(emp)
