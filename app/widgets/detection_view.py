from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class DetectionResultView(QWidget):
    """AI 模型页测试图像显示控件。

    显示测试图像，并把检测结果（类别、置信度、矩形框）按比例叠加绘制。
    results 元素需要包含 class_name / confidence / x / y / w / h 属性，
    与 algorithms/detector.py 中的 DetectionResult 结构保持一致。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detectionView")
        self.setMinimumSize(480, 360)
        self._pixmap: QPixmap | None = None
        self.results: list = []
        self.status_text = "等待测试图像"

    def set_image(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def set_results(self, results: list) -> None:
        self.results = list(results or [])
        self.update()

    def set_status_text(self, text: str) -> None:
        self.status_text = text
        self.update()

    def _image_rect(self) -> QRectF:
        if self._pixmap is None or self._pixmap.isNull():
            return QRectF()
        image_w = self._pixmap.width()
        image_h = self._pixmap.height()
        if image_w <= 0 or image_h <= 0:
            return QRectF()
        scale = min(self.width() / image_w, self.height() / image_h)
        w = image_w * scale
        h = image_h * scale
        return QRectF((self.width() - w) / 2.0, (self.height() - h) / 2.0, w, h)

    def _scale(self) -> float:
        if self._pixmap is None or self._pixmap.width() <= 0:
            return 1.0
        rect = self._image_rect()
        return rect.width() / self._pixmap.width() if rect.width() > 0 else 1.0

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111111"))

        image_rect = self._image_rect()
        if self._pixmap is not None and not self._pixmap.isNull() and not image_rect.isNull():
            painter.drawPixmap(image_rect.toRect(), self._pixmap)
        else:
            painter.setPen(QColor("#9d9d9d"))
            painter.setFont(QFont("Microsoft YaHei", 13))
            painter.drawText(
                self.rect().adjusted(12, 12, -12, -12),
                Qt.AlignmentFlag.AlignCenter,
                self.status_text,
            )
            return

        scale = self._scale()
        offset = image_rect.topLeft()
        pen = QPen(QColor("#4ec9b0"))
        pen.setWidth(2)
        painter.setPen(pen)
        for item in self.results:
            rx = offset.x() + item.x * scale
            ry = offset.y() + item.y * scale
            rw = item.w * scale
            rh = item.h * scale
            painter.drawRect(QRectF(rx, ry, rw, rh))
            painter.drawText(
                int(rx) + 4,
                int(ry) + 16,
                f"{item.class_name} {item.confidence:.2f}",
            )
