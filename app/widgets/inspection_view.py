"""单个检测工位的显示组件：顶部结果区 + 下方相机画面。

与 CameraUnit 的封装思路一致：一个实例对应“一台相机的画面 + 该相机对应的
检测结果”，看板页只需实例化两份（相机 1 / 相机 2）。

结果区布局：
- 左侧：总结果徽标 OK / NG / --；
- 右侧：结果信息文字，NG 时用于显示算法给出的 NG 原因。

插入点：真实检测流程（algorithms/）产出结果后，调用 set_result(ok, message)
即可刷新；message 传 NG 原因即可在结果区显示。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.widgets.camera_view import CameraViewWidget
else:
    from .camera_view import CameraViewWidget


class InspectionView(QGroupBox):
    """检测工位：结果区 + 相机画面。"""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._build_ui()
        self.set_result(None, "")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 顶部结果区：总结果徽标 + 结果信息（NG 原因）。
        result_row = QHBoxLayout()
        result_row.setSpacing(8)
        self.result_badge = QLabel("--")
        self.result_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 徽标框放大 3 倍：宽 192、高 60，字体在 _apply_badge 中放大。
        self.result_badge.setFixedSize(192, 60)
        self.result_info = QLabel("等待检测")
        self.result_info.setWordWrap(True)
        # 结果信息文字与徽标一致，放大 3 倍（默认 13px -> 39px）。
        self.result_info.setStyleSheet("font-size: 39px;")
        result_row.addWidget(self.result_badge)
        result_row.addWidget(self.result_info, 1)
        layout.addLayout(result_row)

        # 下方相机画面区。
        self.view = CameraViewWidget()
        self.view.set_crosshair_visible(False)  # 运行看板不显示十字线。
        layout.addWidget(self.view, 1)

    def set_image(self, pixmap) -> None:
        """更新本工位的相机画面。"""
        self.view.set_pixmap(pixmap)

    def set_result(self, ok: bool | None, message: str = "") -> None:
        """设置检测总结果。

        ok：True=OK，False=NG，None=尚未检测。
        message：结果信息；NG 时传算法给出的原因。
        """
        self._apply_badge(ok)
        if message:
            self.result_info.setText(message)
        else:
            self.result_info.setText(
                "等待检测" if ok is None else ("检测通过" if ok else "检测不通过")
            )

    def _apply_badge(self, ok: bool | None) -> None:
        """按结果更新徽标文字与颜色。"""
        if ok is True:
            text, style = "OK", (
                "QLabel { background-color: #1e8e4e; color: #ffffff;"
                " border-radius: 6px; padding: 6px 0; font-weight: 700;"
                " font-size: 39px; }"
            )
        elif ok is False:
            text, style = "NG", (
                "QLabel { background-color: #d64545; color: #ffffff;"
                " border-radius: 6px; padding: 6px 0; font-weight: 700;"
                " font-size: 39px; }"
            )
        else:
            text, style = "--", (
                "QLabel { background-color: #666666; color: #eeeeee;"
                " border-radius: 6px; padding: 6px 0; font-weight: 700;"
                " font-size: 39px; }"
            )
        self.result_badge.setText(text)
        self.result_badge.setStyleSheet(style)
