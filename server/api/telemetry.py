import os
import json
import aiofiles
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Form, File, UploadFile, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.database import get_db, Device, DetectionLog, DATABASE_DIR

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


class DeviceRegisterRequest(BaseModel):
    client_id: str
    hostname: Optional[str] = ""
    username: Optional[str] = ""
    os_info: Optional[str] = ""
    status: Optional[str] = "ONLINE"


@router.post("/register")
def register_device(req: DeviceRegisterRequest, db: Session = Depends(get_db)):
    """Registers or updates device heartbeat."""
    device = db.query(Device).filter(Device.client_id == req.client_id).first()
    now = datetime.utcnow()
    if not device:
        device = Device(
            client_id=req.client_id,
            hostname=req.hostname or "",
            username=req.username or "",
            os_info=req.os_info or "",
            status="ONLINE",
            last_seen=now,
            first_seen=now,
        )
        db.add(device)
    else:
        device.hostname = req.hostname or device.hostname
        device.username = req.username or device.username
        device.os_info = req.os_info or device.os_info
        device.status = "ONLINE"
        device.last_seen = now

    db.commit()
    return {"status": "ok", "client_id": device.client_id}


@router.post("/events")
async def receive_event(
    client_id: str = Form(...),
    timestamp: str = Form(...),
    event: str = Form(...),
    confidence: Optional[str] = Form("[]"),
    active_apps: Optional[str] = Form("[]"),
    username: Optional[str] = Form(""),
    device: Optional[str] = Form(""),
    bbox: Optional[str] = Form("[]"),
    frame_file: Optional[UploadFile] = File(None),
    screen_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """Receives event telemetry and associated image captures."""
    uploads_dir = os.path.join(DATABASE_DIR, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    frame_save_path = None
    if frame_file and frame_file.filename:
        safe_name = f"{timestamp}_{client_id}_frame.jpg"
        frame_save_path = os.path.join(uploads_dir, safe_name)
        async with aiofiles.open(frame_save_path, "wb") as out_f:
            content = await frame_file.read()
            await out_f.write(content)

    screen_save_path = None
    if screen_file and screen_file.filename:
        safe_name = f"{timestamp}_{client_id}_screen.jpg"
        screen_save_path = os.path.join(uploads_dir, safe_name)
        async with aiofiles.open(screen_save_path, "wb") as out_f:
            content = await screen_file.read()
            await out_f.write(content)

    # Initial review status: if phone detected, marked UNREVIEWED; otherwise IGNORED
    initial_status = "UNREVIEWED" if event == "Mobile phone detected" else "IGNORED"

    log_entry = DetectionLog(
        client_id=client_id,
        device=device,
        username=username,
        timestamp=timestamp.replace("_", " "),
        event=event,
        frame_path=frame_save_path,
        screen_path=screen_save_path,
        confidence=confidence,
        active_apps=active_apps,
        bbox=bbox,
        review_status=initial_status,
    )
    db.add(log_entry)

    # Update device last seen
    dev = db.query(Device).filter(Device.client_id == client_id).first()
    if dev:
        dev.last_seen = datetime.utcnow()
        dev.status = "ONLINE"

    db.commit()
    db.refresh(log_entry)
    return {"status": "ok", "log_id": log_entry.id}


@router.get("/logs")
def get_logs(
    client_id: Optional[str] = None,
    event: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Fetches filtered list of detection logs."""
    q = db.query(DetectionLog)

    if client_id and client_id != "all":
        q = q.filter(DetectionLog.client_id == client_id)
    if event and event != "all":
        q = q.filter(DetectionLog.event == event)
    if review_status and review_status != "all":
        q = q.filter(DetectionLog.review_status == review_status)

    total = q.count()
    logs = q.order_by(DetectionLog.id.desc()).offset(offset).limit(limit).all()

    items = []
    for l in logs:
        # Provide web-accessible URL relative to /storage/uploads
        frame_url = f"/storage/uploads/{os.path.basename(l.frame_path)}" if l.frame_path else None
        screen_url = f"/storage/uploads/{os.path.basename(l.screen_path)}" if l.screen_path else None
        items.append({
            "id": l.id,
            "client_id": l.client_id,
            "device": l.device,
            "username": l.username,
            "timestamp": l.timestamp,
            "event": l.event,
            "frame_url": frame_url,
            "screen_url": screen_url,
            "confidence": json.loads(l.confidence) if l.confidence else [],
            "active_apps": json.loads(l.active_apps) if l.active_apps else [],
            "bbox": json.loads(l.bbox) if l.bbox else None,
            "review_status": l.review_status,
        })

    return {"total": total, "items": items}


@router.get("/devices")
def get_devices(db: Session = Depends(get_db)):
    """Fetches list of registered client devices and their active status."""
    devices = db.query(Device).all()
    now = datetime.utcnow()
    res = []
    for d in devices:
        # Mark offline if no heartbeat in last 60 seconds
        is_online = (now - d.last_seen) < timedelta(seconds=60) if d.last_seen else False
        res.append({
            "id": d.id,
            "client_id": d.client_id,
            "hostname": d.hostname,
            "username": d.username,
            "os_info": d.os_info,
            "status": "ONLINE" if is_online else "OFFLINE",
            "last_seen": d.last_seen.strftime("%Y-%m-%d %H:%M:%S") if d.last_seen else "",
        })
    return res


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Summary metrics for the dashboard."""
    total_events = db.query(DetectionLog).count()
    unreviewed = db.query(DetectionLog).filter(DetectionLog.review_status == "UNREVIEWED").count()
    true_pos = db.query(DetectionLog).filter(DetectionLog.review_status == "TRUE_POSITIVE").count()
    false_pos = db.query(DetectionLog).filter(DetectionLog.review_status == "FALSE_POSITIVE").count()

    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=60)
    online_devices = db.query(Device).filter(Device.last_seen >= cutoff).count()
    total_devices = db.query(Device).count()

    return {
        "total_events": total_events,
        "unreviewed_count": unreviewed,
        "true_positives": true_pos,
        "false_positives": false_pos,
        "online_devices": online_devices,
        "total_devices": total_devices,
    }
