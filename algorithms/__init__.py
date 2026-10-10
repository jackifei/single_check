"""检测算法包。

自定义模板检测算法请继承 algorithms.base.DetectionAlgorithm，
示例见 algorithms.example_algorithm.GrayMeanAlgorithm。
"""

from .base import (
    DetectionAlgorithm,
    DetectionOutput,
    available_algorithms,
    create_algorithm,
    crop_roi,
    get_bool,
    get_float,
    get_int,
    get_str,
    params_to_dict,
    register_algorithm,
)

__all__ = [
    "DetectionAlgorithm",
    "DetectionOutput",
    "available_algorithms",
    "create_algorithm",
    "crop_roi",
    "get_bool",
    "get_float",
    "get_int",
    "get_str",
    "params_to_dict",
    "register_algorithm",
]
