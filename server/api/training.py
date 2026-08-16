import os
import time
import asyncio
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.database import get_db, TrainingJob, DATABASE_DIR
from server.trainer.fine_tuner import FineTuner

router = APIRouter(prefix="/api/training", tags=["training"])

fine_tuner_instance = FineTuner(DATABASE_DIR)


class StartTrainingRequest(BaseModel):
    backbone: str = "yolov13n"  # yolov13n, yolo12n, yolo11n
    epochs: int = 30
    batch_size: int = 16
    device: str = "cpu"  # cpu, cuda


@router.post("/start")
def start_training_job(req: StartTrainingRequest, db: Session = Depends(get_db)):
    """Triggers an asynchronous fine-tuning job."""
    if req.backbone not in ["yolov13n", "yolo12n", "yolo11n"]:
        raise HTTPException(status_code=400, detail="Unsupported backbone")

    # Check if a training job is already running
    running_job = db.query(TrainingJob).filter(TrainingJob.status == "RUNNING").first()
    if running_job:
        raise HTTPException(
            status_code=409,
            detail=f"A training job is already running ({running_job.job_id} on {running_job.backbone})"
        )

    job_id = f"job_{int(time.time())}_{req.backbone}"
    job = TrainingJob(
        job_id=job_id,
        backbone=req.backbone,
        status="PENDING",
        total_epochs=req.epochs,
        progress=0.0,
        current_epoch=0,
        logs="Job initialized."
    )
    db.add(job)
    db.commit()

    # Start training in background
    fine_tuner_instance.start_training(
        job_id=job_id,
        backbone=req.backbone,
        epochs=req.epochs,
        batch_size=req.batch_size,
        device=req.device,
    )

    return {"status": "started", "job_id": job_id, "backbone": req.backbone}


@router.get("/status/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Fetches status and progress of a training job."""
    job = db.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    live_logs = fine_tuner_instance.get_logs(job_id)
    logs_output = "\n".join(live_logs) if live_logs else (job.logs or "")

    return {
        "job_id": job.job_id,
        "backbone": job.backbone,
        "status": job.status,
        "progress": job.progress,
        "current_epoch": job.current_epoch,
        "total_epochs": job.total_epochs,
        "loss": job.loss,
        "logs": logs_output,
        "created_at": job.created_at.strftime("%Y-%m-%d %H:%M:%S") if job.created_at else "",
        "completed_at": job.completed_at.strftime("%Y-%m-%d %H:%M:%S") if job.completed_at else "",
    }


@router.get("/jobs")
def list_training_jobs(limit: int = 20, db: Session = Depends(get_db)):
    """Lists history of training jobs."""
    jobs = db.query(TrainingJob).order_by(TrainingJob.id.desc()).limit(limit).all()
    res = []
    for j in jobs:
        res.append({
            "job_id": j.job_id,
            "backbone": j.backbone,
            "status": j.status,
            "progress": j.progress,
            "current_epoch": j.current_epoch,
            "total_epochs": j.total_epochs,
            "created_at": j.created_at.strftime("%Y-%m-%d %H:%M:%S") if j.created_at else "",
            "completed_at": j.completed_at.strftime("%Y-%m-%d %H:%M:%S") if j.completed_at else "",
        })
    return res


@router.get("/stream/{job_id}")
async def stream_training_logs(job_id: str, db: Session = Depends(get_db)):
    """SSE endpoint for streaming training log lines to the browser."""
    async def event_generator():
        last_idx = 0
        while True:
            logs = fine_tuner_instance.get_logs(job_id)
            if len(logs) > last_idx:
                for line in logs[last_idx:]:
                    yield f"data: {line}\n\n"
                last_idx = len(logs)

            # Check if job completed or failed
            with db.begin():
                j = db.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
                if j and j.status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    yield f"data: [STATUS] {j.status}\n\n"
                    break

            await asyncio.sleep(0.8)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
