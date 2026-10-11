"""检测算法统一接口与工具函数。

自定义算法放在 algorithms/ 目录，继承 DetectionAlgorithm 并实现 detect()。
detect() 的输入约定：

- image  : OpenCV BGR 图像，np.uint8，形状 (H, W, 3)。
- rois   : 模板编辑中编辑的 ROI 列表，坐标在“原图”像素坐标系。
- params : “编辑参数”子界面里“检测参数”表格转成的字典，按参数名称索引。

ROI 结构（与 flow/<模板名>/template.yaml 的 rois 一致）：
- 旋转矩形：{"name": "ROI-1", "shape": "rect", "cx": 150, "cy": 120,
             "w": 200, "h": 150, "angle": 0}
- 圆形    ：{"name": "ROI-2", "shape": "circle", "cx": 400, "cy": 200,
             "radius": 60}

“检测参数”表格每行是 {"name": "阈值", "value": "0.8"}，用 params_to_dict()
转成 {"阈值": "0.8"}，再用 get_float / get_int / get_bool / get_str 取值。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class DetectionOutput:
    """一次检测的输出。

    ok      ：整体判定，True=OK，False=NG。
    message ：结果信息；NG 时填原因（会显示到运行看板对应工位）。
    details ：可选明细，供日志/扩展使用。
    """

    ok: bool
    message: str = ""
    details: list[dict] = field(default_factory=list)


# ----------------------------------------------------------------------
# 参数读取：把“检测参数”列表按名称索引，并提供带类型的取值
# ----------------------------------------------------------------------
def params_to_dict(params: list[dict] | None) -> dict[str, str]:
    """把 [{"name": "阈值", "value": "0.8"}, ...] 转成 {"阈值": "0.8"}。"""
    result: dict[str, str] = {}
    for entry in (params or []):
        if isinstance(entry, dict):
            name = str(entry.get("name", "")).strip()
            if name:
                result[name] = str(entry.get("value", ""))
    return result


def get_str(params: dict[str, str], name: str, default: str = "") -> str:
    """按名称取字符串参数。"""
    value = params.get(name, "")
    return value if value != "" else default


def get_float(params: dict[str, str], name: str, default: float = 0.0) -> float:
    """按名称取浮点参数，解析失败返回 default。"""
    try:
        return float(params[name])
    except (KeyError, ValueError):
        return default


def get_int(params: dict[str, str], name: str, default: int = 0) -> int:
    """按名称取整数参数，解析失败返回 default。"""
    try:
        return int(float(params[name]))
    except (KeyError, ValueError):
        return default


def get_bool(params: dict[str, str], name: str, default: bool = False) -> bool:
    """按名称取布尔参数。支持 true/1/yes/是/开（不区分大小写）。"""
    value = params.get(name, "").strip().lower()
    if value in ("",):
        return default
    if value in ("true", "1", "yes", "y", "是", "开"):
        return True
    if value in ("false", "0", "no", "n", "否", "关"):
        return False
    return default


# ----------------------------------------------------------------------
# ROI 工具：按 ROI 从原图裁出子图
# ----------------------------------------------------------------------
def crop_roi(image: np.ndarray, roi: dict) -> np.ndarray:
    """按 ROI 从 image 裁出子图。

    - rect（含 angle）返回转正后的矩形区域；
    - circle 返回外接正方形区域；
    - 越界部分会被裁掉（可能得到比预期小的图）。
    """
    shape = roi.get("shape", "rect")
    cx = float(roi.get("cx", 0.0))
    cy = float(roi.get("cy", 0.0))

    if shape == "circle":
        radius = float(roi.get("radius", 0.0))
        x0 = max(0, int(round(cx - radius)))
        y0 = max(0, int(round(cy - radius)))
        side = int(round(radius * 2))
        x1 = min(image.shape[1], x0 + side)
        y1 = min(image.shape[0], y0 + side)
        return image[y0:y1, x0:x1]

    w = float(roi.get("w", 0.0))
    h = float(roi.get("h", 0.0))
    angle = float(roi.get("angle", 0.0))
    if abs(angle) > 1e-6:
        return _crop_rotated_rect(image, cx, cy, w, h, angle)

    x0 = max(0, int(round(cx - w / 2.0)))
    y0 = max(0, int(round(cy - h / 2.0)))
    x1 = min(image.shape[1], x0 + int(round(w)))
    y1 = min(image.shape[0], y0 + int(round(h)))
    return image[y0:y1, x0:x1]


def _crop_rotated_rect(
    image: np.ndarray, cx: float, cy: float, w: float, h: float, angle: float
) -> np.ndarray:
    """把旋转矩形区域转正后裁出。"""
    matrix = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    cos_a = abs(matrix[0, 0])
    sin_a = abs(matrix[0, 1])
    bound_w = int(round(h * sin_a + w * cos_a))
    bound_h = int(round(h * cos_a + w * sin_a))
    matrix[0, 2] += bound_w / 2.0 - cx
    matrix[1, 2] += bound_h / 2.0 - cy
    rotated = cv2.warpAffine(image, matrix, (bound_w, bound_h))

    x = max(0, int(round((bound_w - w) / 2.0)))
    y = max(0, int(round((bound_h - h) / 2.0)))
    x2 = min(bound_w, x + int(round(w)))
    y2 = min(bound_h, y + int(round(h)))
    return rotated[y:y2, x:x2]


# ----------------------------------------------------------------------
# 算法基类
# ----------------------------------------------------------------------
class DetectionAlgorithm(ABC):
    """自定义检测算法基类。

    子类只需要实现 detect()；name 用于界面/日志标识。
    """

    name: str = "未命名算法"

    @abstractmethod
    def detect(
        self,
        image: np.ndarray,
        rois: list[dict],
        params: dict[str, str],
    ) -> DetectionOutput:
        """对一帧图像执行检测。

        image  ：OpenCV BGR 图像（np.uint8，HxWx3）。
        rois   ：模板编辑中编辑的 ROI 列表。
        params ：检测参数，已按名称索引（用 get_float 等取值）。
        返回   ：DetectionOutput，ok 决定 OK/NG，message 填 NG 原因。
        """
        raise NotImplementedError


# ----------------------------------------------------------------------
# 算法注册表：后续“拍照检测”流程按名称创建算法
# ----------------------------------------------------------------------
_REGISTRY: dict[str, type[DetectionAlgorithm]] = {}


def register_algorithm(cls: type[DetectionAlgorithm]) -> type[DetectionAlgorithm]:
    """把算法类注册进登记表（可用作装饰器）。"""
    _REGISTRY[cls.name] = cls
    return cls


def create_algorithm(name: str) -> DetectionAlgorithm:
    """按名称创建算法实例，名称不存在时抛 ValueError。"""
    if name not in _REGISTRY:
        raise ValueError(f"未注册的检测算法：{name}")
    return _REGISTRY[name]()


def available_algorithms() -> list[str]:
    """返回所有已注册算法名。"""
    return sorted(_REGISTRY)
