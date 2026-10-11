"""相机单元：把“一台相机”的画面显示、开关操作和相机参数封装成一个类。

本次重写原则（简单、可靠、两台相机互相独立）：
- 设备**由用户显式选择**：界面下拉框直接列出可用设备（Linux 下为 /dev/videoN），
  不做任何“自动挑一个”的猜测——猜错设备（UVC 的 metadata 节点）会出现
  “打开成功但没有画面”；
- 每台相机拥有独立的驱动实例和独立的采集线程，可分别开关、互不影响；
- 只做一件共享的事：登记表 DeviceRegistry，防止两台相机同时打开同一路设备。

参数区只保留“曝光时间”，增益 / 帧率 / 触发模式 / 像素格式保持默认值并隐藏。
"""

from __future__ import annotations

import sys
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.widgets.camera_image_view import CameraImageView
    from drivers.camera.usb_camera import UsbCameraCaptureThread, UsbCameraDriver
else:
    from .camera_image_view import CameraImageView
    from drivers.camera.usb_camera import UsbCameraCaptureThread, UsbCameraDriver


class DeviceRegistry:
    """设备占用登记表：保证同一路设备只被一台相机取流。

    两台相机各自独立取流，唯一需要协调的就是“别开同一路设备”，
    由这张表统一记录，逻辑简单、不涉及线程。
    """

    def __init__(self) -> None:
        self._owners: dict[str, str] = {}

    @staticmethod
    def _key(device) -> str:
        # Linux 上把整数索引与设备路径归一成同一个键，
        # 避免旧配置里的 0 与枚举出的 /dev/video0 被当成两台设备。
        if isinstance(device, int) and sys.platform.startswith("linux"):
            return f"/dev/video{device}"
        return str(device)

    def owner(self, device) -> str | None:
        """返回设备的当前占用者名称，未被占用返回 None。"""
        return self._owners.get(self._key(device))

    def claim(self, device, owner: str) -> str | None:
        """占用设备：成功返回 None；已被他人占用则返回占用者名称。"""
        key = self._key(device)
        current = self._owners.get(key)
        if current is not None and current != owner:
            return current
        self._owners[key] = owner
        return None

    def release(self, device, owner: str) -> None:
        """释放设备（仅当占用者是本人时才生效）。"""
        key = self._key(device)
        if self._owners.get(key) == owner:
            self._owners.pop(key, None)

    def owned_keys(self) -> set[str]:
        """当前所有被占用的设备标识。"""
        return set(self._owners)


class CameraUnit(QGroupBox):
    """单台相机的完整单元：画面 + 开关 + 参数。"""

    metrics_changed = pyqtSignal(dict)
    image_changed = pyqtSignal(object)
    # 仅“拍照 / 打开本地图像”这类单帧快照时发出，用于模板编辑 ROI 背景，
    # 不随实时预览流逐帧刷新。
    snapshot_changed = pyqtSignal(object)
    result_changed = pyqtSignal(str)
    tip_changed = pyqtSignal(str)

    # 隐藏参数使用固定默认值（需求：均改为默认并隐藏）。
    DEFAULT_GAIN = 1.0
    DEFAULT_FRAME_RATE = 30.0
    DEFAULT_TRIGGER = "连续采集"
    DEFAULT_PIXEL_FORMAT = "Mono8"

    # 预览启动后超过该时间仍没取到帧，就提示排查。
    FRAME_WATCHDOG_MS = 3000
    # FPS 指标上报间隔：1 秒刷新一次，避免数字跳太快。
    METRICS_INTERVAL = 1.0

    def __init__(
        self,
        index: int,
        parent: QWidget | None = None,
        registry: DeviceRegistry | None = None,
    ) -> None:
        super().__init__(f"相机 {index}", parent)
        self.index = index
        self.owner_name = f"相机 {index}"
        self.driver = UsbCameraDriver()
        self.registry = registry if registry is not None else DeviceRegistry()
        self.capture_thread: UsbCameraCaptureThread | None = None
        self._last_metrics_time = 0.0
        self._frame_count = 0
        self._frame_seen = False
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_frame_watchdog)
        # 图像信息条状态：尺寸 / XY / RGB / 灰度。
        self._info = {"size": "--", "xy": "--", "rgb": "--", "gray": "--"}
        self._build_ui()
        # 图像尺寸统一由 metrics_changed 驱动，避免多处写入不一致。
        self.metrics_changed.connect(self._apply_metrics)

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        root.addWidget(self._build_image_area(), 1)
        root.addWidget(self._build_operation_area(), 0)

    def _build_image_area(self) -> QWidget:
        """左侧图像显示区：画面控件（缩放/拖动/取点）+ 像素信息条。"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.view = CameraImageView()
        layout.addWidget(self.view, 1)

        self.info_label = QLabel()
        self.info_label.setObjectName("imageInfoLabel")
        layout.addWidget(self.info_label)
        self._refresh_info_label()

        self.view.pixel_info_changed.connect(self._on_pixel_info)
        self.view.mouse_position_changed.connect(self._on_mouse_position)
        return container

    def _build_operation_area(self) -> QWidget:
        """右侧操作区：设备 / 开关 / 预览 / 本地图像 / 参数，宽度自适应内容。"""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        container.setMinimumWidth(260)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.device_combo = QComboBox()
        self.device_combo.setObjectName("cameraDeviceCombo")
        self.device_combo.setToolTip("选择本相机使用的设备，两台相机请选择不同的设备")
        form.addRow("设备", self.device_combo)
        layout.addLayout(form)

        # 第一行：打开相机 + 十字线居中。
        open_row = QHBoxLayout()
        self.open_button = QPushButton("打开相机")
        self.open_button.setCheckable(True)
        self.center_cross_button = QPushButton("十字线居中")
        open_row.addWidget(self.open_button)
        open_row.addWidget(self.center_cross_button)
        layout.addLayout(open_row)

        # 第二行：开始预览 + 停止预览。
        preview_row = QHBoxLayout()
        preview_row.setContentsMargins(0, 0, 0, 0)
        self.start_preview_button = QPushButton("开始预览")
        self.stop_preview_button = QPushButton("停止预览")
        preview_row.addWidget(self.start_preview_button)
        preview_row.addWidget(self.stop_preview_button)
        layout.addLayout(preview_row)

        # 第三行：拍照 + 打开本地图像。
        capture_row = QHBoxLayout()
        capture_row.setContentsMargins(0, 0, 0, 0)
        self.capture_button = QPushButton("拍照")
        self.open_local_button = QPushButton("打开本地图像")
        capture_row.addWidget(self.capture_button)
        capture_row.addWidget(self.open_local_button)
        layout.addLayout(capture_row)

        layout.addWidget(self._build_param_group())
        layout.addStretch(1)

        self.open_button.clicked.connect(self._toggle_camera)
        self.start_preview_button.clicked.connect(self.start_preview)
        # clicked 会带一个 bool 参数，用 lambda 隔开，避免把它当成 notify。
        self.stop_preview_button.clicked.connect(lambda: self.stop_preview())
        self.capture_button.clicked.connect(self.capture)
        self.open_local_button.clicked.connect(self.open_local_image)
        self.center_cross_button.clicked.connect(self.view.center_cross)
        return container

    def _build_param_group(self) -> QGroupBox:
        """相机参数：仅“曝光时间”可见，其余参数保持默认值并隐藏。"""
        group = QGroupBox("相机参数")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setRange(0.0, 100000.0)
        self.exposure_spin.setDecimals(1)
        self.exposure_spin.setValue(5000.0)
        self.exposure_spin.setSuffix(" us")
        form.addRow("曝光时间", self.exposure_spin)

        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(0.0, 48.0)
        self.gain_spin.setDecimals(2)
        self.gain_spin.setValue(self.DEFAULT_GAIN)
        form.addRow("增益", self.gain_spin)

        self.frame_rate_spin = QDoubleSpinBox()
        self.frame_rate_spin.setRange(0.1, 500.0)
        self.frame_rate_spin.setDecimals(1)
        self.frame_rate_spin.setValue(self.DEFAULT_FRAME_RATE)
        form.addRow("帧率", self.frame_rate_spin)

        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems([self.DEFAULT_TRIGGER, "软件触发", "硬件触发"])
        form.addRow("触发模式", self.trigger_combo)

        self.pixel_format_combo = QComboBox()
        self.pixel_format_combo.addItems(
            [self.DEFAULT_PIXEL_FORMAT, "Mono10", "BayerRG8", "RGB8"]
        )
        form.addRow("像素格式", self.pixel_format_combo)

        for row in range(1, 5):
            self._hide_form_row(form, row)
        return group

    @staticmethod
    def _hide_form_row(form: QFormLayout, row: int) -> None:
        """隐藏 QFormLayout 的整行（标签 + 字段）。"""
        if hasattr(form, "setRowVisible"):
            form.setRowVisible(row, False)
            return
        for role in (QFormLayout.ItemRole.LabelRole, QFormLayout.ItemRole.FieldRole):
            item = form.itemAt(row, role)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setVisible(False)

    # ------------------------------------------------------------------
    # 设备选择
    # ------------------------------------------------------------------
    def current_device(self):
        """当前选中的设备标识（路径或索引），未选择时为 None。"""
        return self.device_combo.currentData()

    def set_device(self, device, name: str = "") -> None:
        """选中指定设备；列表里没有就直接补进去（用于一键打开，不依赖枚举）。"""
        index = UsbCameraDriver.to_index(device)
        if index is None:
            return
        position = self.device_combo.findData(index)
        if position < 0:
            self.device_combo.addItem(name or f"设备 {index}", index)
            position = self.device_combo.count() - 1
        self.device_combo.setCurrentIndex(position)

    def set_device_list(self, devices: list[dict]) -> None:
        """把页面级枚举得到的完整设备列表填入本相机下拉框。

        枚举现在由页面统一执行，本方法只负责接收全部索引并展示；
        保留原选择，原选择不在列表里时默认选中第一台。
        """
        current = self.current_device()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for device in devices:
            self.device_combo.addItem(device["name"], device["id"])
        position = self.device_combo.findData(current) if current is not None else -1
        if position >= 0:
            self.device_combo.setCurrentIndex(position)
        elif self.device_combo.count() > 0:
            self.device_combo.setCurrentIndex(0)
        self.device_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # 打开 / 关闭
    # ------------------------------------------------------------------
    def _toggle_camera(self, checked: bool) -> None:
        """“打开/关闭相机”按钮回调。"""
        if checked:
            if not self.open_camera():
                self.open_button.setChecked(False)
        else:
            self.close_camera()

    def open_camera(self) -> bool:
        """打开当前选中的设备，成功返回 True。"""
        device = self.current_device()
        if device is None:
            self.result_changed.emit(
                f"检测结果：相机 {self.index} 未选择设备，请先点击“枚举相机”"
            )
            return False

        holder = self.registry.owner(device)
        if holder is not None and holder != self.owner_name:
            self.result_changed.emit(
                f"检测结果：设备 {device} 正被“{holder}”使用，"
                f"请为相机 {self.index} 选择另一台设备"
            )
            return False

        if not self.driver.open(device):
            self.result_changed.emit(
                f"检测结果：相机 {self.index} 打开设备 {device} 失败"
            )
            return False

        self.registry.claim(device, self.owner_name)
        self.open_button.setChecked(True)
        self.open_button.setText("关闭相机")
        self.result_changed.emit(
            f"检测结果：相机 {self.index}（{self.device_combo.currentText()}）已打开"
        )
        return True

    def close_camera(self) -> None:
        """停止预览并关闭相机。"""
        device = self.driver.device
        self.stop_preview(notify=False)
        self.driver.close()
        if device is not None:
            self.registry.release(device, self.owner_name)
        self.open_button.setChecked(False)
        self.open_button.setText("打开相机")
        self.metrics_changed.emit({"index": self.index, "fps": 0, "image_size": "--"})
        self.result_changed.emit(f"检测结果：相机 {self.index} 已关闭")

    def is_opened(self) -> bool:
        return self.driver.is_opened()

    # ------------------------------------------------------------------
    # 预览 / 拍照 / 本地图像
    # ------------------------------------------------------------------
    def start_preview(self) -> None:
        """启动本相机的采集线程（只影响本相机）。"""
        if not self.driver.is_opened():
            self.result_changed.emit(f"检测结果：相机 {self.index} 未打开，无法预览")
            return
        self.stop_preview(notify=False)
        self._last_metrics_time = time.perf_counter()
        self._frame_count = 0
        self._frame_seen = False
        self.capture_thread = UsbCameraCaptureThread(
            self.driver, self, camera_label=f"相机 {self.index}"
        )
        self.capture_thread.frame_ready.connect(self._on_frame)
        self.capture_thread.start()
        self._watchdog.start(self.FRAME_WATCHDOG_MS)
        self.tip_changed.emit(f"操作提示：相机 {self.index} 预览已启动。")

    def stop_preview(self, notify: bool = True) -> None:
        """停止本相机的采集线程。"""
        self._watchdog.stop()
        if self.capture_thread is not None:
            self.capture_thread.stop()
            self.capture_thread.wait(1000)
            self.capture_thread.deleteLater()
            self.capture_thread = None
        if notify:
            self.tip_changed.emit(f"操作提示：相机 {self.index} 预览已停止。")

    def capture(self) -> None:
        """单次拍照：停预览后取一帧显示并广播（带重试，应对首帧较慢）。"""
        self.stop_preview(notify=False)
        frame = self._read_frame_with_retry()
        if frame is None:
            self.result_changed.emit(f"检测结果：相机 {self.index} 拍照失败，未取到图像")
            return
        height, width = frame.shape[:2]
        pixmap = self._frame_to_pixmap(frame)
        self._show_pixmap(pixmap)
        self.snapshot_changed.emit(pixmap)
        self.metrics_changed.emit(
            {"index": self.index, "fps": 0, "image_size": f"{width}x{height}"}
        )
        self.result_changed.emit(
            f"检测结果：相机 {self.index} 拍照完成，图像大小 {width}x{height}"
        )

    def _read_frame_with_retry(self, timeout_s: float = 1.5):
        """带重试取一帧，应对相机刚打开时首帧较慢的情况。"""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            frame = self.driver.read_frame()
            if frame is not None and getattr(frame, "size", 0) > 0:
                return frame
            time.sleep(0.05)
        return None

    def open_local_image(self) -> None:
        """打开本地图像并显示（无相机时便于调试）。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"相机 {self.index} 打开本地图像",
            "",
            "图像文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*.*)",
        )
        if not file_path:
            return
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.result_changed.emit(f"检测结果：相机 {self.index} 本地图像打开失败")
            return
        self.stop_preview(notify=False)
        self._show_pixmap(pixmap)
        self.snapshot_changed.emit(pixmap)
        self.metrics_changed.emit(
            {
                "index": self.index,
                "fps": 0,
                "image_size": f"{pixmap.width()}x{pixmap.height()}",
            }
        )
        self.result_changed.emit(
            f"检测结果：相机 {self.index} 已打开本地图像 {file_path}"
        )

    def _on_frame(self, frame) -> None:
        """采集线程回调：刷新画面；FPS 指标每 1 秒按平均帧率上报一次。"""
        if not self._frame_seen:
            self._frame_seen = True
            self._watchdog.stop()
        now = time.perf_counter()
        height, width = frame.shape[:2]
        self._show_pixmap(self._frame_to_pixmap(frame))

        # 图像尺寸只在变化时刷新信息条（基本只更新一次）。
        size_text = f"{width}x{height}"
        if size_text != self._info["size"]:
            self._info["size"] = size_text
            self._refresh_info_label()

        self._frame_count += 1
        if now - self._last_metrics_time >= self.METRICS_INTERVAL:
            interval = now - self._last_metrics_time
            fps = self._frame_count / interval if interval > 0 else 0.0
            self.metrics_changed.emit(
                {
                    "index": self.index,
                    "fps": round(fps, 1),
                    "image_size": size_text,
                }
            )
            self._last_metrics_time = now
            self._frame_count = 0

    def _on_frame_watchdog(self) -> None:
        """预览启动后一直没取到帧时给出排查提示。"""
        if self._frame_seen or not self.driver.is_opened():
            return
        self.result_changed.emit(
            f"检测结果：相机 {self.index}（设备 {self.current_device()}）已打开，"
            f"但 {self.FRAME_WATCHDOG_MS // 1000} 秒内未取到任何图像"
        )
        self.tip_changed.emit(
            f"操作提示：相机 {self.index} 无图像。先单独打开这一台确认它能出图；"
            "若单独能出图、两台同时只出一台，通常是 USB 带宽不足或该“一拖二”"
            "模组同一时刻只支持一路流，需要降分辨率/帧率，或改走厂商 SDK。"
        )

    def _show_pixmap(self, pixmap: QPixmap) -> None:
        """显示到画面区并广播给其它页面。"""
        self.view.set_pixmap(pixmap)
        self.image_changed.emit(pixmap)

    @staticmethod
    def _frame_to_pixmap(frame) -> QPixmap:
        """OpenCV BGR 帧转 QPixmap。"""
        height, width = frame.shape[:2]
        image = QImage(
            frame.data, width, height, 3 * width, QImage.Format.Format_RGB888
        ).rgbSwapped().copy()
        return QPixmap.fromImage(image)

    # ------------------------------------------------------------------
    # 图像信息条
    # ------------------------------------------------------------------
    def _refresh_info_label(self) -> None:
        self.info_label.setText(
            f"图像尺寸：{self._info['size']}    XY：{self._info['xy']}"
            f"    RGB：{self._info['rgb']}    灰度：{self._info['gray']}"
        )

    def _on_pixel_info(self, rgb: str, gray: str) -> None:
        self._info["rgb"] = rgb
        self._info["gray"] = gray
        self._refresh_info_label()

    def _on_mouse_position(self, x: float, y: float) -> None:
        self._info["xy"] = "--" if x < 0 or y < 0 else f"{int(x)},{int(y)}"
        self._refresh_info_label()

    def _apply_metrics(self, data: dict) -> None:
        """指标回调：刷新信息条中的图像尺寸（仅处理本相机）。"""
        if int(data.get("index", self.index)) != self.index:
            return
        self._info["size"] = str(data.get("image_size", "--"))
        self._refresh_info_label()

    # ------------------------------------------------------------------
    # 配置读写 / 一键启动
    # ------------------------------------------------------------------
    def config(self) -> dict:
        """导出本相机配置。"""
        return {
            "index": self.index,
            "device": self.current_device(),
            "device_name": self.device_combo.currentText(),
            "exposure": self.exposure_spin.value(),
            "gain": self.gain_spin.value(),
            "frame_rate": self.frame_rate_spin.value(),
            "trigger": self.trigger_combo.currentText(),
            "pixel_format": self.pixel_format_combo.currentText(),
        }

    def apply_config(self, data: dict) -> None:
        """回显配置：设备 + 曝光时间（其余参数恒为默认值）。"""
        if not isinstance(data, dict):
            return
        self.set_device(data.get("device"), str(data.get("device_name", "")))
        self.exposure_spin.setValue(
            float(data.get("exposure", self.exposure_spin.value()))
        )

    def auto_start(self, data: dict) -> bool:
        """一键打开：打开相机后只做一次首帧拍照，不启动实时预览。"""
        self.apply_config(data)
        if self.current_device() is None:
            self.result_changed.emit(
                f"检测结果：相机 {self.index} 没有已保存的设备，"
                "请先点击“枚举相机”并选择设备后保存配置"
            )
            return False
        if not self.open_camera():
            return False
        self.capture()
        return True

    def shutdown(self) -> None:
        """应用关闭前彻底释放本相机资源。

        先关闭底层 capture（让阻塞在 read() 里的线程立即返回），
        再停止并等待采集线程退出，最后释放设备占用登记。
        """
        device = self.driver.device
        self._watchdog.stop()
        thread = self.capture_thread
        self.capture_thread = None
        if thread is not None:
            thread.stop()
            self.driver.close()  # 解除 read() 阻塞，线程随后退出循环。
            thread.wait(2000)
            if not thread.isFinished():
                thread.terminate()  # 兜底：正常情况不会走到这里。
                thread.wait()
        else:
            self.driver.close()
        if device is not None:
            self.registry.release(device, self.owner_name)
