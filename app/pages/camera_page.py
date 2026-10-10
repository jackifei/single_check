"""相机管理页：一拖二 USB 相机。

本次改造要点：
- 单台相机的画面显示（缩放/拖动/像素信息）、打开关闭、相机参数全部封装在
  `app/widgets/camera_unit.py` 的 CameraUnit 中，本页只负责实例化两次；
- 页面用纵向 QSplitter 把两块相机单元上下分隔（中间的横向分隔栏可拖动）；
- 去掉“功能选择（相机/标定）”，只保留相机操作，界面更简洁；
- 底部保留“保存相机配置”和“一键打开相机”。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.widgets import camera_unit

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.pages.base_page import BasePage
    from app.services.config_service import ConfigService
    from app.widgets.camera_unit import CameraUnit, DeviceRegistry
    from drivers.camera.usb_camera import UsbCameraDriver
else:
    from .base_page import BasePage
    from ..services.config_service import ConfigService
    from ..widgets.camera_unit import CameraUnit, DeviceRegistry
    from drivers.camera.usb_camera import UsbCameraDriver


class CameraPage(BasePage):
    """相机管理页。

    页面内容是一根纵向分隔栏，上方为 1 号相机单元，下方为 2 号相机单元。
    """

    camera_metrics_changed = pyqtSignal(dict)
    image_changed = pyqtSignal(object)
    # 带相机序号的画面广播：供看板把画面分到相机 1 / 相机 2 两个工位。
    camera_image_changed = pyqtSignal(int, object)
    # 单帧快照广播：仅拍照/打开本地图像时发出，供模板编辑 ROI 背景使用。
    snapshot_changed = pyqtSignal(object)

    # 一拖二：同时管理的相机数量。
    CAMERA_COUNT = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "相机管理",
            "打开两台 USB 相机并预览；拖动中间分隔栏可调整上下画面比例。",
            parent,
        )
        self.config_service = ConfigService()
        self.camera_units: list[CameraUnit] = []
        # 两台相机共用一张设备占用登记表：只用于防止同时打开同一路设备。
        self.device_registry = DeviceRegistry()
        self._build_ui()
        self._load_config()
        self.set_result("检测结果：相机未连接")
        self.set_tip("操作提示：枚举相机后打开，或点击右下角“一键打开相机”按保存配置启动。")

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 上下分割：两台相机各占一部分，中间的横向分隔栏可拖动。
        self.camera_splitter = QSplitter(Qt.Orientation.Vertical)
        self.camera_splitter.setChildrenCollapsible(False)
        self.camera_splitter.setHandleWidth(6)
        for index in range(1, self.CAMERA_COUNT + 1):
            # 每台相机独立驱动、独立采集线程；仅共享设备占用登记表。
            unit = CameraUnit(index, registry=self.device_registry)
            unit.metrics_changed.connect(self._on_unit_metrics)
            unit.image_changed.connect(self.image_changed.emit)
            unit.image_changed.connect(
                lambda pixmap, i=index: self.camera_image_changed.emit(i, pixmap)
            )
            unit.snapshot_changed.connect(self.snapshot_changed.emit)
            unit.result_changed.connect(self.set_result)
            unit.tip_changed.connect(self.set_tip)
            self.camera_units.append(unit)
            self.camera_splitter.addWidget(unit)
        # 默认上下等分，用户可再拖动中间分隔栏调整比例。

        self.camera_splitter.setSizes([1, 1])
        layout.addWidget(self.camera_splitter, 1)

        # 页面底部：枚举相机 + 保存配置 + 一键打开（水平排列）。
        bottom = QHBoxLayout()
        self.save_button = QPushButton("保存相机配置")
        self.one_click_button = QPushButton("一键打开相机")
        self.one_click_button.setMinimumHeight(34)
        self.enumerate_button = QPushButton("枚举相机")
        bottom.addWidget(self.save_button)
        bottom.addWidget(self.one_click_button, 1)
        bottom.addWidget(self.enumerate_button)
        layout.addLayout(bottom)

        self.add_to_content(container, stretch=1)

        self.enumerate_button.clicked.connect(self._enumerate_cameras)
        self.save_button.clicked.connect(self._save_config)
        self.one_click_button.clicked.connect(self._one_click_open)

    def _on_unit_metrics(self, data: dict) -> None:
        """把相机单元上报的指标转发给主窗口，用于底部状态栏 FPS/图像显示。"""
        self.camera_metrics_changed.emit(data)

    def _enumerate_cameras(self) -> None:
        """页面级枚举：得到完整设备列表后，把全部索引同步给两台相机。"""
        devices = UsbCameraDriver.list_devices()
        for unit in self.camera_units:
            unit.set_device_list(devices)
        if devices:
            self.set_result(
                f"检测结果：枚举到 {len(devices)} 台 USB 相机，已同步到相机 1 / 相机 2"
            )
            self.set_tip("操作提示：请在相机 1、相机 2 的下拉框中选择不同的设备。")
        else:
            self.set_result("检测结果：未枚举到可用的 USB 相机")
            self.set_tip(
                "操作提示：请确认相机已插好、当前用户有摄像头权限，且未被其它程序占用。"
            )

    # ------------------------------------------------------------------
    # 配置读写 / 一键打开
    # ------------------------------------------------------------------
    def _save_config(self) -> None:
        """把两台相机的参数保存到 config/camera.yaml。"""
        self.config_service.save_page_config(
            "camera",
            {
                "camera_type": "USB 相机",
                "cameras": [unit.config() for unit in self.camera_units],
            },
        )
        self.set_tip("操作提示：两台相机配置已保存到 config/camera.yaml。")

    def _load_config(self) -> None:
        """启动时回显已保存的配置（只回显曝光时间与设备，不自动打开）。"""
        data = self.config_service.load_page_config("camera")
        cameras = data.get("cameras") or []
        if cameras:
            for unit, config in zip(self.camera_units, cameras):
                unit.apply_config(config)
        elif data:
            # 兼容旧版“单相机扁平结构”：回显到 1 号相机，避免升级后参数丢失。
            self.camera_units[0].apply_config(
                {"exposure": data.get("exposure", 5000.0)}
            )

    def _one_click_open(self) -> None:
        """一键打开：按保存的配置打开两台相机并各做一次首帧拍照（不启动实时预览）。"""
        data = self.config_service.load_page_config("camera")
        cameras = data.get("cameras") or []
        if not cameras:
            self.set_result("检测结果：暂无已保存的相机配置，请先枚举、打开并保存")
            self.set_tip("操作提示：先配置两台相机并点击“保存相机配置”，再使用一键打开。")
            return

        opened = 0
        for unit, config in zip(self.camera_units, cameras):
            if unit.auto_start(config):
                opened += 1
        self.set_tip(
            f"操作提示：一键打开完成，成功打开并完成首帧拍照 "
            f"{opened}/{len(self.camera_units)} 台相机。"
        )

    def auto_open_cameras(self) -> None:
        """供“自启动”调用：按保存的配置打开两台相机并开始预览。"""
        self._one_click_open()

    def capture_camera(self, index: int) -> None:
        """对指定相机（1 或 2）执行一次拍照，供“拍照检测”触发。"""
        position = index - 1
        if 0 <= position < len(self.camera_units):
            self.camera_units[position].capture()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def auto_save_config(self) -> None:
        self._save_config()

    def shutdown(self) -> None:
        """关闭页面/应用前，释放两台相机的采集线程与设备。"""
        for unit in self.camera_units:
            unit.shutdown()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.standalone import run_page

    raise SystemExit(run_page(sys.modules[__name__].CameraPage))
