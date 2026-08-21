from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal


@dataclass
class DetectionResult:
    """单次检测结果（坐标已映射回原图像素）。"""

    class_id: int
    class_name: str
    confidence: float
    x: int
    y: int
    w: int
    h: int


class YoloOnnxDetector:
    """基于 OpenCV DNN 的 YOLO ONNX 检测引擎。

    支持常见 YOLOv5（输出 5+类别数 通道）和 YOLOv8（输出 4+类别数 通道）
    的 ONNX 导出格式；输入图像按 letterbox 缩放到模型输入尺寸，检测结果
    会映射回原始图像坐标。

    扩展点：如需接入 PyTorch/TensorRT 等其它引擎，可在 algorithms/ 目录
    新增引擎类，并保持统一的 detect() 接口，页面无需改动。
    """

    def __init__(self) -> None:
        self.net: cv2.dnn.Net | None = None
        self.model_path: str = ""

    def load(self, model_path: str) -> None:
        """加载 ONNX 模型文件。"""
        self.release()
        self.net = cv2.dnn.readNetFromONNX(model_path)
        self.model_path = model_path

    def release(self) -> None:
        self.net = None
        self.model_path = ""

    def is_loaded(self) -> bool:
        return self.net is not None

    def detect(
        self,
        image_rgb: np.ndarray,
        confidence: float = 0.25,
        iou_threshold: float = 0.45,
        labels: list[str] | None = None,
        input_size: tuple[int, int] = (640, 640),
        class_thresholds: dict[str, float] | None = None,
    ) -> list[DetectionResult]:
        """对 RGB 图像执行一次检测，返回按位置排序的结果列表。"""
        if self.net is None:
            raise RuntimeError("模型未加载")
        if image_rgb is None or image_rgb.size == 0:
            raise RuntimeError("图像为空")

        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        img_h, img_w = image_bgr.shape[:2]
        input_w, input_h = input_size

        # letterbox 缩放：保持宽高比，四周填充灰色，检测结果再映射回原图。
        scale = min(input_w / img_w, input_h / img_h)
        new_w = max(1, int(round(img_w * scale)))
        new_h = max(1, int(round(img_h * scale)))
        resized = cv2.resize(image_bgr, (new_w, new_h))
        canvas = np.full((input_h, input_w, 3), 114, dtype=np.uint8)
        dx = (input_w - new_w) // 2
        dy = (input_h - new_h) // 2
        canvas[dy : dy + new_h, dx : dx + new_w] = resized

        blob = cv2.dnn.blobFromImage(
            canvas, 1.0 / 255.0, (input_w, input_h), swapRB=False, crop=False
        )
        self.net.setInput(blob)
        outputs = self.net.forward()

        data = outputs[0] if outputs.ndim == 3 else outputs
        if data.ndim != 2:
            raise RuntimeError(f"不支持的模型输出维度：{data.shape}")

        # 统一为 (N, 通道) 排列：YOLOv8 常见 (4+nc, N)，YOLOv5 常见 (N, 5+nc)。
        if data.shape[0] <= data.shape[1] and data.shape[0] <= 85:
            data = data.T

        channels = data.shape[1]
        if labels:
            num_classes = len(labels)
            if channels == 4 + num_classes:
                has_objectness = False  # YOLOv8 风格：无单独目标置信度
            elif channels == 5 + num_classes:
                has_objectness = True   # YOLOv5 风格：含目标置信度
            else:
                raise RuntimeError(
                    f"模型输出通道数 {channels} 与标签数量 {num_classes} 不匹配"
                    f"（应为 {4 + num_classes} 或 {5 + num_classes}）"
                )
        else:
            # 未加载标签时按常见结构推断：通道>6 视为含目标置信度。
            has_objectness = channels > 6
            num_classes = channels - 5 if has_objectness else channels - 4
            labels = [f"class_{index}" for index in range(num_classes)]

        boxes = data[:, :4]  # cx, cy, w, h（模型输入坐标系）
        if has_objectness:
            objectness = data[:, 4]
            scores = data[:, 5:] * objectness[:, None]
        else:
            scores = data[:, 4:]

        class_ids = np.argmax(scores, axis=1)
        class_scores = scores[np.arange(scores.shape[0]), class_ids]

        # 支持按类别单独设置阈值，否则统一使用全局置信度。
        if class_thresholds:
            per_class = np.array(
                [
                    float(class_thresholds.get(labels[cid], confidence))
                    for cid in class_ids
                ]
            )
            keep = np.where(class_scores >= per_class)[0]
        else:
            keep = np.where(class_scores >= confidence)[0]

        if len(keep) == 0:
            return []

        boxes = boxes[keep]
        class_ids = class_ids[keep]
        class_scores = class_scores[keep]
        xywh = boxes.astype(float).tolist()

        indices = cv2.dnn.NMSBoxes(
            xywh, class_scores.astype(float).tolist(), confidence, iou_threshold
        )
        if indices is None:
            return []
        if isinstance(indices, tuple):
            indices = indices[0] if len(indices) == 1 else indices
        indices = np.asarray(indices).reshape(-1).tolist()

        results: list[DetectionResult] = []
        for index in indices:
            cid = int(class_ids[index])
            conf = float(class_scores[index])
            cx, cy, bw, bh = boxes[index]
            x = (cx - bw / 2.0 - dx) / scale
            y = (cy - bh / 2.0 - dy) / scale
            w = bw / scale
            h = bh / scale
            results.append(
                DetectionResult(
                    class_id=cid,
                    class_name=labels[cid] if cid < len(labels) else f"class_{cid}",
                    confidence=conf,
                    x=int(round(x)),
                    y=int(round(y)),
                    w=int(round(w)),
                    h=int(round(h)),
                )
            )

        results.sort(key=lambda item: (item.y, item.x))
        return results


class DetectionThread(QThread):
    """后台检测线程，避免大图推理阻塞 UI。"""

    detection_done = pyqtSignal(object, float)  # (results, 耗时秒)
    detection_error = pyqtSignal(str)

    def __init__(
        self,
        detector: YoloOnnxDetector,
        image_rgb: np.ndarray,
        confidence: float = 0.25,
        iou_threshold: float = 0.45,
        labels: list[str] | None = None,
        input_size: tuple[int, int] = (640, 640),
        class_thresholds: dict[str, float] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.detector = detector
        self.image_rgb = image_rgb
        self.confidence = confidence
        self.iou_threshold = iou_threshold
        self.labels = labels
        self.input_size = input_size
        self.class_thresholds = class_thresholds

    def run(self) -> None:
        start = time.perf_counter()
        try:
            results = self.detector.detect(
                self.image_rgb,
                confidence=self.confidence,
                iou_threshold=self.iou_threshold,
                labels=self.labels,
                input_size=self.input_size,
                class_thresholds=self.class_thresholds,
            )
            elapsed = time.perf_counter() - start
            self.detection_done.emit(results, elapsed)
        except Exception as exc:  # noqa: BLE001
            self.detection_error.emit(str(exc))
