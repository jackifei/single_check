"""运行看板页：左右并列显示相机 1 / 相机 2 的画面与检测结果。

已按需求移除原“看板统计”区（OK/NG/日/周/月卡片与模拟按钮）。
两个工位用竖直分隔栏分隔，各自上方是结果区（OK / NG + 结果信息），
下方是相机画面；工位封装在 InspectionView 中，实例化两份即可。

插入点：检测流程产出结果后，调用 set_inspection_result(index, ok, message)
即可刷新对应工位的总结果与 NG 原因。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSplitter

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.pages.base_page import BasePage
    from app.widgets.inspection_view import InspectionView
else:
    from .base_page import BasePage
    from ..widgets.inspection_view import InspectionView


class RunDashboardPage(BasePage):
    """运行看板页面：两个检测工位左右并列。"""

    CAMERA_COUNT = 2

    def __init__(self, parent=None) -> None:
        super().__init__(
            "运行看板",
            "左右并列显示相机 1 / 相机 2 的画面与检测结果。",
            parent,
        )
        self.inspection_views: list[InspectionView] = []
        self._build_ui()
        self.set_result("检测结果：等待检测")
        self.set_tip(
            "操作提示：在相机管理页打开相机后，画面会分别同步到这里的相机 1 / 相机 2。"
        )

    def _build_ui(self) -> None:
        # 两个工位用竖直分隔栏并列，中间可拖动调整宽度。
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        for index in range(1, self.CAMERA_COUNT + 1):
            view = InspectionView(f"相机 {index}")
            self.inspection_views.append(view)
            splitter.addWidget(view)
        splitter.setSizes([1, 1])
        self.add_to_content(splitter, stretch=1)

    def set_camera_image(self, index: int, pixmap) -> None:
        """把相机页某一路的画面同步到对应工位。"""
        position = index - 1
        if 0 <= position < len(self.inspection_views):
            self.inspection_views[position].set_image(pixmap)

    def set_inspection_result(self, index: int, ok: bool | None, message: str = "") -> None:
        """设置某一路的检测结果（由检测流程调用）。

        index：1=相机 1，2=相机 2；ok：True/False/None；message：结果信息或 NG 原因。
        """
        position = index - 1
        if 0 <= position < len(self.inspection_views):
            self.inspection_views[position].set_result(ok, message)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.standalone import run_page

    raise SystemExit(run_page(sys.modules[__name__].RunDashboardPage))
