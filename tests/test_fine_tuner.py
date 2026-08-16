import os
import time
import pytest
from server.database import SessionLocal, init_db, DatasetItem
from server.trainer.fine_tuner import FineTuner


def test_fine_tuner_pipeline(tmp_path):
    init_db()
    storage_dir = str(tmp_path / "server_storage")
    os.makedirs(storage_dir, exist_ok=True)

    fine_tuner = FineTuner(storage_dir)
    job_id = f"test_job_{int(time.time())}"

    # Run 1 epoch training worker synchronously for verification
    fine_tuner._run_training_worker(
        job_id=job_id,
        backbone="yolo11n",
        epochs=1,
        batch_size=2,
        device="cpu"
    )

    logs = fine_tuner.get_logs(job_id)
    assert len(logs) > 0

    # Check exported ONNX model
    models_dir = os.path.join(storage_dir, "models")
    exported_files = [f for f in os.listdir(models_dir) if f.endswith(".onnx")]
    assert len(exported_files) >= 1
    onnx_file = os.path.join(models_dir, exported_files[0])
    assert os.path.exists(onnx_file)
    assert os.path.getsize(onnx_file) > 1000000  # ONNX file should be > 1MB
