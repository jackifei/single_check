"""USB 相机驱动（纯 OpenCV）。

重要：Linux 上 OpenCV 的 V4L2 后端**只认整数索引**（内部映射到 /dev/videoN），
直接传设备路径字符串会被当成默认设备 0 处理，导致两台相机实际打开同一路。
因此本模块统一使用整数索引作为设备标识，界面只负责展示名称。

枚举时用“实测能否取到一帧”过滤设备，自动排除 UVC 的 metadata 节点
（那种节点能打开但永远取不到图像）。
"""

from __future__ import annotations

import glob
import sys
import time
from pathlib import Path

import cv2
from PyQt6.QtCore import QThread, pyqtSignal


def preferred_backend() -> int:
    """按运行平台选择 OpenCV 采集后端。"""
    if sys.platform.startswith("linux"):
        return cv2.CAP_V4L2
    if sys.platform.startswith("win"):
        return cv2.CAP_DSHOW
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def _linux_video_indices() -> list[int]:
    """返回 /dev/video* 里存在的整数索引（升序）。"""
    indices: list[int] = []
    for path in glob.glob("/dev/video*"):
        suffix = path.rsplit("video", 1)[-1]
        if suffix.isdigit():
            indices.append(int(suffix))
    return sorted(indices)


def _linux_device_name(index: int) -> str:
    """读取 /sys/class/video4linux/videoN/name 得到摄像头可读名称。"""
    name_file = Path("/sys/class/video4linux") / f"video{index}" / "name"
    try:
        return name_file.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


class UsbCameraDriver:
    """基于 OpenCV 的 USB 相机驱动（一个实例对应一台相机）。

    设备标识统一为整数索引；也兼容旧配置里可能保存的 "/dev/videoN" 或
    数字字符串，to_index() 会归一成索引。

    插入点：接入厂商 SDK 时，保持 open / read_frame / close 语义一致即可，
    上层 CameraUnit 无需改动。
    """

    def __init__(self, backend: int | None = None) -> None:
        self.backend = preferred_backend() if backend is None else backend
        self._capture: cv2.VideoCapture | None = None
        self.device: int | None = None  # 当前打开的整数索引

    @staticmethod
    def to_index(device) -> int | None:
        """把设备标识归一成整数索引；无法识别返回 None。"""
        if isinstance(device, int):
            return int(device)
        text = str(device).strip()
        if text.isdigit():
            return int(text)
        if text.startswith("/dev/video"):
            suffix = text.rsplit("video", 1)[-1]
            if suffix.isdigit():
                return int(suffix)
        return None

    # ------------------------------------------------------------------
    # 设备枚举
    # ------------------------------------------------------------------
    @staticmethod
    def list_devices(exclude=None, max_index: int = 8) -> list[dict]:
        """列出**确认能出图**的采集设备。

        exclude：需要跳过的设备索引（通常是被另一台相机占用的设备）。
        返回：[{"id": <整数索引>, "name": <界面显示名>}]
        """
        skip: set[int] = set()
        for item in (exclude or set()):
            index = UsbCameraDriver.to_index(item)
            if index is not None:
                skip.add(index)

        if sys.platform.startswith("linux"):
            candidates = _linux_video_indices()
        else:
            candidates = list(range(max_index))

        devices: list[dict] = []
        for index in candidates:
            if index in skip:
                continue  # 正在被另一台相机取流，探测会打断它。
            if not UsbCameraDriver._delivers_frames(index):
                continue  # 打不开或读不到帧（metadata 节点 / 无权限）。
            if sys.platform.startswith("linux"):
                name = _linux_device_name(index)
                label = (
                    f"[{index}] {name} (/dev/video{index})"
                    if name
                    else f"[{index}] /dev/video{index}"
                )
            else:
                label = f"[{index}] USB Camera {index}"
            devices.append({"id": index, "name": label})
        return devices

    @staticmethod
    def _delivers_frames(index: int, timeout_s: float = 0.6) -> bool:
        """实测在 timeout_s 内能否取到一帧。"""
        capture = cv2.VideoCapture(index, preferred_backend())
        if not capture.isOpened():
            capture.release()
            return False
        delivered = False
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            ok, frame = capture.read()
            if ok and frame is not None and getattr(frame, "size", 0) > 0:
                delivered = True
                break
            time.sleep(0.02)
        capture.release()
        return delivered

    # ------------------------------------------------------------------
    # 打开 / 关闭 / 取帧
    # ------------------------------------------------------------------
    def open(self, device) -> bool:
        """按整数索引打开设备，成功返回 True。"""
        index = self.to_index(device)
        if index is None:
            return False
        self.close()
        capture = cv2.VideoCapture(index, self.backend)
        if not capture.isOpened():
            capture.release()
            return False
        self._capture = capture
        self.device = index
        return True

    def close(self) -> None:
        """释放相机资源。"""
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self.device = None

    def is_opened(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def read_frame(self):
        """读取一帧 OpenCV BGR 图像，失败返回 None。"""
        if not self.is_opened():
            return None
        ok, frame = self._capture.read()
        return frame if ok else None


class UsbCameraCaptureThread(QThread):
    """单台相机的采集线程。

    每台相机一个实例，互不共享；一个线程卡住不会影响另一台相机。
    线程内带节流打印，便于在终端观察两台相机的取流是否正常。
    """

    frame_ready = pyqtSignal(object)

    # 打印节流：每秒最多输出一次，避免 30fps 刷屏。
    PRINT_INTERVAL = 1.0

    def __init__(
        self,
        driver: UsbCameraDriver,
        parent=None,
        camera_label: str = "",
    ) -> None:
        super().__init__(parent)
        self.driver = driver
        self.camera_label = camera_label or f"设备 {driver.device}"
        self._running = False

    def run(self) -> None:
        self._running = True
        # print(
        #     f"[{self.camera_label}][设备索引 {self.driver.device}] 采集线程启动",
        #     flush=True,
        # )
        frame_count = 0
        last_print = 0.0
        while self._running and self.driver.is_opened():
            frame = self.driver.read_frame()
            now = time.monotonic()
            if frame is not None:
                frame_count += 1
                if now - last_print >= self.PRINT_INTERVAL:
                    height, width = frame.shape[:2]
                    # print(
                    #     f"[{self.camera_label}][设备索引 {self.driver.device}] "
                    #     f"取流正常 {width}x{height}，累计 {frame_count} 帧",
                    #     flush=True,
                    # )
                    last_print = now
                self.frame_ready.emit(frame)
            else:
                if now - last_print >= self.PRINT_INTERVAL:
                    print(
                        f"[{self.camera_label}][设备索引 {self.driver.device}] "
                        "read_frame 返回 None（未取到帧）",
                        flush=True,
                    )
                    last_print = now
            self.msleep(1)
        print(
            f"[{self.camera_label}][设备索引 {self.driver.device}] "
            f"采集线程退出（running={self._running}, "
            f"opened={self.driver.is_opened()}）",
            flush=True,
        )

    def stop(self) -> None:
        self._running = False
