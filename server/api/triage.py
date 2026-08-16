import os
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.database import get_db, DetectionLog, DatasetItem

router = APIRouter(prefix="/api/triage", tags=["triage"])


class ClassifyRequest(BaseModel):
    log_id: int
    status: str  # TRUE_POSITIVE, FALSE_POSITIVE, IGNORED
    bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]


class BatchClassifyRequest(BaseModel):
    log_ids: List[int]
    status: str


@router.get("/pending")
def get_pending_items(limit: int = 50, db: Session = Depends(get_db)):
    """Returns list of unreviewed logs awaiting human verification."""
    logs = (
        db.query(DetectionLog)
        .filter(DetectionLog.review_status == "UNREVIEWED")
        .order_by(DetectionLog.id.desc())
        .limit(limit)
        .all()
    )

    items = []
    for l in logs:
        if not l.frame_path:
            continue
        frame_url = f"/storage/uploads/{os.path.basename(l.frame_path)}"
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
            "bbox": json.loads(l.bbox) if l.bbox else None,
            "review_status": l.review_status,
        })
    return {"count": len(items), "items": items}


@router.post("/classify")
def classify_log(req: ClassifyRequest, db: Session = Depends(get_db)):
    """Classifies a detection log as False Positive (Hard Neg), True Positive, or Ignored."""
    log = db.query(DetectionLog).filter(DetectionLog.id == req.log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")

    if req.status not in ["TRUE_POSITIVE", "FALSE_POSITIVE", "IGNORED", "UNREVIEWED"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    log.review_status = req.status
    log.reviewed_at = datetime.utcnow()
    if req.bbox is not None:
        log.bbox = json.dumps(req.bbox)

    # Sync into DatasetItem for training
    existing_item = db.query(DatasetItem).filter(DatasetItem.log_id == log.id).first()
    if req.status in ["TRUE_POSITIVE", "FALSE_POSITIVE"]:
        label_type = "POSITIVE" if req.status == "TRUE_POSITIVE" else "HARD_NEGATIVE"
        if not existing_item:
            new_item = DatasetItem(
                log_id=log.id,
                image_path=log.frame_path,
                label_type=label_type,
                bbox=log.bbox,
                split="train"
            )
            db.add(new_item)
        else:
            existing_item.label_type = label_type
            existing_item.bbox = log.bbox
    elif existing_item and req.status == "IGNORED":
        db.delete(existing_item)

    db.commit()
    return {"status": "ok", "log_id": log.id, "new_status": log.review_status}


@router.post("/batch_classify")
def batch_classify(req: BatchClassifyRequest, db: Session = Depends(get_db)):
    """Classifies multiple items in a single request."""
    logs = db.query(DetectionLog).filter(DetectionLog.id.in_(req.log_ids)).all()
    count = 0
    for l in logs:
        l.review_status = req.status
        l.reviewed_at = datetime.utcnow()
        if req.status in ["TRUE_POSITIVE", "FALSE_POSITIVE"]:
            label_type = "POSITIVE" if req.status == "TRUE_POSITIVE" else "HARD_NEGATIVE"
            existing_item = db.query(DatasetItem).filter(DatasetItem.log_id == l.id).first()
            if not existing_item and l.frame_path:
                db.add(DatasetItem(
                    log_id=l.id,
                    image_path=l.frame_path,
                    label_type=label_type,
                    bbox=l.bbox,
                    split="train"
                ))
            elif existing_item:
                existing_item.label_type = label_type
        count += 1

    db.commit()
    return {"status": "ok", "updated_count": count}


@router.get("/dataset_stats")
def get_dataset_stats(db: Session = Depends(get_db)):
    """Returns verified dataset breakdown for training."""
    pos_count = db.query(DatasetItem).filter(DatasetItem.label_type == "POSITIVE").count()
    neg_count = db.query(DatasetItem).filter(DatasetItem.label_type == "HARD_NEGATIVE").count()
    total_reviewed = pos_count + neg_count

    return {
        "positive_samples": pos_count,
        "hard_negative_samples": neg_count,
        "total_dataset_items": total_reviewed,
        "ready_for_training": total_reviewed >= 2
    }
