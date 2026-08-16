import os
import hashlib
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.database import get_db, ModelVersion, DATABASE_DIR

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/latest")
def get_latest_active_model(db: Session = Depends(get_db)):
    """Returns metadata about the currently active model."""
    active = db.query(ModelVersion).filter(ModelVersion.is_active == True).first()
    if not active:
        # Fallback to the latest version registered
        active = db.query(ModelVersion).order_by(ModelVersion.id.desc()).first()

    if not active or not os.path.exists(active.onnx_path):
        return {
            "available": False,
            "version": "none",
            "backbone": "none",
            "md5": "",
        }

    return {
        "available": True,
        "version": active.version_tag,
        "backbone": active.backbone,
        "md5": active.md5_hash,
        "map50": active.map50,
        "precision": active.precision,
        "recall": active.recall,
        "f1_score": active.f1_score,
        "latency_ms": active.latency_ms,
        "file_size_mb": active.file_size_mb,
    }


@router.get("/download")
def download_active_model(db: Session = Depends(get_db)):
    """Streams the active model.onnx binary to the client agent."""
    active = db.query(ModelVersion).filter(ModelVersion.is_active == True).first()
    if not active:
        active = db.query(ModelVersion).order_by(ModelVersion.id.desc()).first()

    if not active or not os.path.exists(active.onnx_path):
        raise HTTPException(status_code=404, detail="Active model binary not found on server")

    return FileResponse(
        path=active.onnx_path,
        filename="model.onnx",
        media_type="application/octet-stream"
    )


@router.get("/versions")
def get_model_versions(db: Session = Depends(get_db)):
    """Lists all benchmarked model versions for side-by-side comparison."""
    versions = db.query(ModelVersion).order_by(ModelVersion.id.desc()).all()
    res = []
    for v in versions:
        res.append({
            "id": v.id,
            "version_tag": v.version_tag,
            "backbone": v.backbone,
            "map50": v.map50,
            "map50_95": v.map50_95,
            "precision": v.precision,
            "recall": v.recall,
            "f1_score": v.f1_score,
            "latency_ms": v.latency_ms,
            "file_size_mb": v.file_size_mb,
            "is_active": v.is_active,
            "notes": v.notes or "",
            "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S") if v.created_at else "",
        })
    return res


@router.post("/deploy/{version_tag}")
def deploy_model_version(version_tag: str, db: Session = Depends(get_db)):
    """Sets a specific model version as the active version deployed to clients."""
    target = db.query(ModelVersion).filter(ModelVersion.version_tag == version_tag).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target model version not found")

    # Deactivate all others
    db.query(ModelVersion).update({ModelVersion.is_active: False})
    target.is_active = True
    db.commit()

    return {
        "status": "deployed",
        "version_tag": target.version_tag,
        "backbone": target.backbone,
        "md5": target.md5_hash,
    }
