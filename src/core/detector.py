import os
import threading
import logging
import onnxruntime as ort
import cv2
import numpy as np

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)


class Detector:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._lock = threading.Lock()
        self.session = None
        self.input_name = None
        self.load_model(model_path)

    def load_model(self, model_path: str) -> None:
        """Loads or reloads the ONNX model session thread-safely."""
        with self._lock:
            try:
                if not os.path.exists(model_path):
                    raise FileNotFoundError(f"Model file not found: {model_path}")
                
                # Options for optimized CPU execution
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                opts.inter_op_num_threads = 1
                opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

                self.session = ort.InferenceSession(
                    model_path,
                    sess_options=opts,
                    providers=["CPUExecutionProvider"]
                )
                self.input_name = self.session.get_inputs()[0].name
                self.model_path = model_path
                logger.info(f"Loaded ONNX model from {model_path}")
            except Exception as e:
                logger.error(f"Error loading ONNX model from {model_path}: {e}")
                raise

    def reload_model(self, new_model_path: str) -> bool:
        """Hot-reloads the detector with a new model file."""
        try:
            logger.info(f"Hot-reloading model: {new_model_path}")
            self.load_model(new_model_path)
            return True
        except Exception as e:
            logger.error(f"Failed to hot-reload model: {e}")
            return False

    @staticmethod
    def letterbox(img: np.ndarray, new_shape=(640, 640), color=(114, 114, 114)):
        """
        Resizes and pads image to new_shape while preserving aspect ratio.
        Returns: (padded_image, scale_ratio, (pad_left, pad_top))
        """
        shape = img.shape[:2]  # current shape [height, width]
        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)

        # Scale ratio (new / old)
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

        # Compute padding
        new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding

        dw /= 2  # divide padding into 2 sides
        dh /= 2

        if shape[::-1] != new_unpad:  # resize
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return img, r, (dw, dh)

    @staticmethod
    def preprocess_image(img: np.ndarray) -> np.ndarray:
        """Normalizes and converts HWC BGR image to BCHW RGB float32 tensor."""
        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Expand to BHWC
        tensor = img_rgb[np.newaxis, ...]
        # Transpose to BCHW
        tensor = tensor.transpose((0, 3, 1, 2))
        tensor = np.ascontiguousarray(tensor, dtype=np.float32)
        tensor /= 255.0
        return tensor

    def detect_phone(self, raw_frame: np.ndarray, conf: float = 0.5):
        """
        Runs phone detection on raw camera frame.
        Returns: (found: bool, bbox: (x1, y1, x2, y2) in original image coords, confidences: list[float])
        """
        if raw_frame is None or raw_frame.size == 0:
            return False, None, []

        try:
            orig_h, orig_w = raw_frame.shape[:2]

            # 1. Letterbox to 640x640
            padded_img, ratio, (pad_w, pad_h) = self.letterbox(raw_frame, (640, 640))

            # 2. Preprocess to BCHW tensor
            input_data = self.preprocess_image(padded_img)

            # 3. ONNX inference
            with self._lock:
                outputs = self.session.run(None, {self.input_name: input_data})[0]

            # 4. Postprocess detections in 640x640 space
            detections = self.postprocess_output(outputs, conf_thres=conf)

            # 5. Un-letterbox bounding boxes back to original frame coordinates
            phones = []
            confidences = []

            for x1, y1, x2, y2, conf_val, class_id in detections:
                if int(class_id) == 0 and float(conf_val) >= conf:
                    # Un-pad and scale back
                    orig_x1 = max(0, int(round((x1 - pad_w) / ratio)))
                    orig_y1 = max(0, int(round((y1 - pad_h) / ratio)))
                    orig_x2 = min(orig_w, int(round((x2 - pad_w) / ratio)))
                    orig_y2 = min(orig_h, int(round((y2 - pad_h) / ratio)))

                    phones.append((orig_x1, orig_y1, orig_x2, orig_y2))
                    confidences.append(float(conf_val))
                    break

            if phones:
                return True, phones[0], confidences
            return False, None, []
        except Exception as e:
            logger.error(f"Detection error: {e}", exc_info=True)
            return False, None, []

    @staticmethod
    def postprocess_output(
        outputs: np.ndarray,
        conf_thres: float = 0.25,
        iou_thres: float = 0.45
    ) -> list:
        """
        Decodes raw YOLO tensor outputs to bounding boxes.
        Handles shape (1, 5, 8400) [1 class] or (1, 84, 8400) [80 classes].
        """
        boxes = outputs[0]
        num_rows = boxes.shape[0]
        num_cols = boxes.shape[-1]

        if num_rows > num_cols:
            boxes = boxes.T

        channels = boxes.shape[0]
        anchors = boxes.shape[1]

        detections = []
        for i in range(anchors):
            col = boxes[:, i]
            cx, cy, w, h = col[:4]

            if channels == 5:
                # Single class model: col[4] is phone confidence
                conf = float(col[4])
                class_id = 0
            else:
                # Multi-class model: find max class
                scores = col[4:]
                class_id = int(np.argmax(scores))
                conf = float(scores[class_id])
                # In standard COCO, cell phone is class 67
                if class_id == 67:
                    class_id = 0
                elif class_id != 0:
                    continue

            if conf < conf_thres:
                continue

            x1 = cx - w / 2.0
            y1 = cy - h / 2.0
            x2 = cx + w / 2.0
            y2 = cy + h / 2.0

            detections.append((x1, y1, x2, y2, conf, class_id))

        if detections:
            bboxes = np.array([[x1, y1, x2, y2] for x1, y1, x2, y2, _, _ in detections])
            scores = np.array([conf for _, _, _, _, conf, _ in detections])
            indices = cv2.dnn.NMSBoxes(bboxes.tolist(), scores.tolist(), conf_thres, iou_thres)
            if isinstance(indices, tuple):
                indices = indices[0]
            detections = [detections[i] for i in np.array(indices).flatten()]

        return detections

    @staticmethod
    def prepreprocess(frame: np.ndarray) -> np.ndarray:
        """Legacy helper for uniform/similarity checks preserving 640x640 size."""
        img, _, _ = Detector.letterbox(frame, (640, 640))
        return img
