import os
import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

DATABASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server_storage"))
os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(os.path.join(DATABASE_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(DATABASE_DIR, "models"), exist_ok=True)
os.makedirs(os.path.join(DATABASE_DIR, "datasets"), exist_ok=True)

DB_PATH = os.path.join(DATABASE_DIR, "central_server.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, unique=True, index=True, nullable=False)
    hostname = Column(String, default="")
    username = Column(String, default="")
    os_info = Column(String, default="")
    status = Column(String, default="ONLINE")  # ONLINE, OFFLINE
    last_seen = Column(DateTime, default=datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.utcnow)


class DetectionLog(Base):
    __tablename__ = "detection_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, index=True, default="")
    device = Column(String, default="")
    username = Column(String, default="")
    timestamp = Column(String, default="")
    event = Column(String, default="")
    frame_path = Column(String, nullable=True)
    screen_path = Column(String, nullable=True)
    confidence = Column(Text, nullable=True)  # JSON string
    active_apps = Column(Text, nullable=True)  # JSON string
    bbox = Column(Text, nullable=True)  # JSON string [x1, y1, x2, y2]
    review_status = Column(String, default="UNREVIEWED", index=True)  # UNREVIEWED, TRUE_POSITIVE, FALSE_POSITIVE, IGNORED
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DatasetItem(Base):
    __tablename__ = "dataset_items"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer, ForeignKey("detection_logs.id"), nullable=True)
    image_path = Column(String, nullable=False)
    label_type = Column(String, nullable=False)  # POSITIVE, HARD_NEGATIVE
    bbox = Column(Text, nullable=True)  # JSON string [x1, y1, x2, y2]
    yolo_txt = Column(Text, default="")  # YOLO normalized box string or empty for neg
    split = Column(String, default="train")  # train, val
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_tag = Column(String, unique=True, index=True, nullable=False)
    backbone = Column(String, nullable=False)  # yolov13n, yolo12n, yolo11n
    onnx_path = Column(String, nullable=False)
    pt_path = Column(String, nullable=True)
    md5_hash = Column(String, default="")
    map50 = Column(Float, default=0.0)
    map50_95 = Column(Float, default=0.0)
    precision = Column(Float, default=0.0)
    recall = Column(Float, default=0.0)
    f1_score = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    file_size_mb = Column(Float, default=0.0)
    is_active = Column(Boolean, default=False, index=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)
    backbone = Column(String, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    progress = Column(Float, default=0.0)
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, default=50)
    loss = Column(Float, default=0.0)
    logs = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Check if initial base model is registered in DB
    existing = db.query(ModelVersion).filter(ModelVersion.is_active == True).first()
    if not existing:
        initial_onnx = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "model.onnx"))
        if os.path.exists(initial_onnx):
            import hashlib
            hasher = hashlib.md5()
            with open(initial_onnx, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            size_mb = os.path.getsize(initial_onnx) / (1024 * 1024)
            base_model = ModelVersion(
                version_tag="v1.0.0-base",
                backbone="yolo12n",
                onnx_path=initial_onnx,
                md5_hash=hasher.hexdigest(),
                map50=0.916,
                precision=0.9348,
                recall=0.8983,
                f1_score=0.9162,
                latency_ms=70.0,
                file_size_mb=round(size_mb, 2),
                is_active=True,
                notes="Initial author paper baseline (exp27 YOLOv12n)"
            )
            db.add(base_model)
            db.commit()
    db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
