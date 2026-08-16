import os
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.database import SessionLocal, init_db, Device, DetectionLog, DatasetItem, ModelVersion
from server.trainer.dataset_builder import DatasetBuilder
from src.core.detector import Detector


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_device_registration_and_stats(client):
    # Register device
    res = client.post("/api/telemetry/register", json={
        "client_id": "test-agent-99",
        "hostname": "TEST-PC",
        "username": "tester",
        "os_info": "Windows 11",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Check devices list
    res_devices = client.get("/api/telemetry/devices")
    assert res_devices.status_code == 200
    devices = res_devices.json()
    assert any(d["client_id"] == "test-agent-99" for d in devices)

    # Check stats
    res_stats = client.get("/api/telemetry/stats")
    assert res_stats.status_code == 200
    assert "total_events" in res_stats.json()


def test_event_upload_and_triage(client, tmp_path):
    # Create mock frame image
    test_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(test_img, (100, 100), (200, 300), (255, 255, 255), -1)
    img_path = str(tmp_path / "test_frame.jpg")
    cv2.imwrite(img_path, test_img)

    with open(img_path, "rb") as f:
        res = client.post(
            "/api/telemetry/events",
            data={
                "client_id": "test-agent-99",
                "timestamp": "2026-08-15_12-00-00",
                "event": "Mobile phone detected",
                "confidence": "[0.88]",
                "active_apps": '["notepad.exe"]',
                "username": "tester",
                "device": "TEST-PC",
                "bbox": "[100, 100, 200, 300]",
            },
            files={"frame_file": ("test_frame.jpg", f, "image/jpeg")}
        )
    assert res.status_code == 200
    log_id = res.json()["log_id"]

    # Classify as False Positive (Hard Negative)
    res_fp = client.post("/api/triage/classify", json={
        "log_id": log_id,
        "status": "FALSE_POSITIVE",
        "bbox": None
    })
    assert res_fp.status_code == 200
    assert res_fp.json()["new_status"] == "FALSE_POSITIVE"

    # Verify dataset stats updated
    res_ds = client.get("/api/triage/dataset_stats")
    assert res_ds.status_code == 200
    assert res_ds.json()["hard_negative_samples"] >= 1


def test_dataset_builder(tmp_path):
    builder = DatasetBuilder(str(tmp_path))
    db = SessionLocal()
    try:
        yaml_path = builder.build_from_db(db)
        assert os.path.exists(yaml_path)
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "nc: 1" in content
            assert "names: ['phone']" in content
    finally:
        db.close()


def test_detector_letterbox_scaleback():
    model_path = "models/model.onnx"
    if not os.path.exists(model_path):
        pytest.skip("Base model.onnx not present")

    detector = Detector(model_path)
    assert detector.session is not None

    # Test dummy frame detection
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    found, bbox, confs = detector.detect_phone(dummy_frame)
    # Output should be boolean and either None or tuple of 4 coords within (0~1280, 0~720)
    assert isinstance(found, bool)
    if found:
        assert len(bbox) == 4
        x1, y1, x2, y2 = bbox
        assert 0 <= x1 <= 1280
        assert 0 <= y1 <= 720
