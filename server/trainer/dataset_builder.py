import os
import shutil
import random
import cv2
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from server.database import DatasetItem, DetectionLog

logger = logging.getLogger("DatasetBuilder")


class DatasetBuilder:
    """
    Builds YOLO-compatible dataset structure from reviewed detection items.
    Positive items get YOLO class 0 bounding boxes.
    False Positive (Hard Negative) items get empty label text files.
    """

    def __init__(self, base_storage_dir: str):
        self.base_storage_dir = base_storage_dir
        self.datasets_dir = os.path.join(base_storage_dir, "datasets")
        os.makedirs(self.datasets_dir, exist_ok=True)

    def build_from_db(self, db: Session, val_split: float = 0.2) -> str:
        """
        Gathers all reviewed items from DB and exports a YOLO dataset directory.
        Returns: absolute path to data.yaml
        """
        items = db.query(DatasetItem).all()

        # If no explicit DatasetItem yet, collect directly from DetectionLog
        if not items:
            reviewed_logs = db.query(DetectionLog).filter(
                DetectionLog.review_status.in_(["TRUE_POSITIVE", "FALSE_POSITIVE"])
            ).all()

            for log in reviewed_logs:
                if not log.frame_path or not os.path.exists(log.frame_path):
                    continue

                label_type = "POSITIVE" if log.review_status == "TRUE_POSITIVE" else "HARD_NEGATIVE"
                item = DatasetItem(
                    log_id=log.id,
                    image_path=log.frame_path,
                    label_type=label_type,
                    bbox=log.bbox,
                    split="train" if random.random() > val_split else "val"
                )
                db.add(item)
                items.append(item)
            db.commit()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset_path = os.path.join(self.datasets_dir, f"yolo_dataset_{timestamp}")
        train_img_dir = os.path.join(dataset_path, "images", "train")
        val_img_dir = os.path.join(dataset_path, "images", "val")
        train_lbl_dir = os.path.join(dataset_path, "labels", "train")
        val_lbl_dir = os.path.join(dataset_path, "labels", "val")

        for d in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
            os.makedirs(d, exist_ok=True)

        count_pos = 0
        count_neg = 0

        # If total items is very small (e.g. initial demo), create synthetic seed images to prevent train crash
        if len(items) < 4:
            self._create_seed_samples(train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir)

        for idx, item in enumerate(items):
            if not os.path.exists(item.image_path):
                continue

            img = cv2.imread(item.image_path)
            if img is None:
                continue

            h, w = img.shape[:2]
            split = item.split if item.split in ["train", "val"] else ("train" if idx % 5 != 0 else "val")

            target_img_dir = train_img_dir if split == "train" else val_img_dir
            target_lbl_dir = train_lbl_dir if split == "train" else val_lbl_dir

            file_stem = f"sample_{idx}_{item.label_type.lower()}"
            img_dest = os.path.join(target_img_dir, f"{file_stem}.jpg")
            lbl_dest = os.path.join(target_lbl_dir, f"{file_stem}.txt")

            shutil.copy2(item.image_path, img_dest)

            if item.label_type == "POSITIVE" and item.bbox:
                try:
                    bbox = json.loads(item.bbox) if isinstance(item.bbox, str) else item.bbox
                    if isinstance(bbox, list) and len(bbox) == 4:
                        x1, y1, x2, y2 = bbox
                        # Normalize to 0~1
                        x_center = ((x1 + x2) / 2.0) / w
                        y_center = ((y1 + y2) / 2.0) / h
                        box_w = (x2 - x1) / w
                        box_h = (y2 - y1) / h

                        x_center = max(0.0, min(1.0, x_center))
                        y_center = max(0.0, min(1.0, y_center))
                        box_w = max(0.001, min(1.0, box_w))
                        box_h = max(0.001, min(1.0, box_h))

                        with open(lbl_dest, "w", encoding="utf-8") as f:
                            f.write(f"0 {x_center:.6f} {y_center:.6f} {box_w:.6f} {box_h:.6f}\n")
                        count_pos += 1
                    else:
                        with open(lbl_dest, "w", encoding="utf-8") as f:
                            f.write("")
                except Exception as e:
                    logger.warning(f"Error writing label {lbl_dest}: {e}")
                    with open(lbl_dest, "w", encoding="utf-8") as f:
                        f.write("")
            else:
                # HARD_NEGATIVE / FALSE POSITIVE -> Empty label file
                with open(lbl_dest, "w", encoding="utf-8") as f:
                    f.write("")
                count_neg += 1

        # Write data.yaml
        yaml_content = f"""# Auto-generated YOLO Dataset by Phone Detection Central Server
path: {os.path.abspath(dataset_path).replace(chr(92), '/')}
train: images/train
val: images/val
nc: 1
names: ['phone']
"""
        yaml_path = os.path.join(dataset_path, "data.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        logger.info(f"Built dataset at {dataset_path} with {count_pos} positives and {count_neg} hard negatives")
        return yaml_path

    def _create_seed_samples(self, train_img, train_lbl, val_img, val_lbl):
        """Creates dummy baseline samples if no logs reviewed yet to allow dry-run testing."""
        import numpy as np
        for target_i, target_l, prefix in [(train_img, train_lbl, "train"), (val_img, val_lbl, "val")]:
            for i in range(2):
                # Positive mock image with phone rect
                img_pos = np.full((480, 640, 3), 120, dtype=np.uint8)
                cv2.rectangle(img_pos, (200, 150), (320, 380), (30, 30, 30), -1)
                img_pos_path = os.path.join(target_i, f"seed_{prefix}_pos_{i}.jpg")
                cv2.imwrite(img_pos_path, img_pos)
                with open(os.path.join(target_l, f"seed_{prefix}_pos_{i}.txt"), "w") as f:
                    f.write("0 0.406250 0.552083 0.187500 0.479167\n")

                # Hard Negative mock background
                img_neg = np.full((480, 640, 3), 200, dtype=np.uint8)
                cv2.circle(img_neg, (300, 240), 80, (70, 70, 70), -1)
                img_neg_path = os.path.join(target_i, f"seed_{prefix}_neg_{i}.jpg")
                cv2.imwrite(img_neg_path, img_neg)
                with open(os.path.join(target_l, f"seed_{prefix}_neg_{i}.txt"), "w") as f:
                    f.write("")
