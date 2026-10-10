"""示例检测算法：灰度均值范围判定。

这是一个可以直接运行的范例，演示如何：
1. 继承 DetectionAlgorithm；
2. 用 params 按“参数名称”读取检测参数；
3. 遍历模板编辑里的 ROI，用 crop_roi() 裁图并判定；
4. 返回 DetectionOutput（OK/NG + NG 原因）。

你可以复制本文件改成自己的算法文件（例如 my_algorithm.py），
只需实现 detect() 并给 name 起个唯一的名字。
"""

from __future__ import annotations

import cv2
import numpy as np

from .base import (
    DetectionAlgorithm,
    DetectionOutput,
    crop_roi,
    get_float,
    register_algorithm,
)


@register_algorithm
class GrayMeanAlgorithm(DetectionAlgorithm):
    """灰度均值范围判定算法。

    检测参数（在“检测参数”表格里按名称填）：
    - 最小灰度（默认 0）：ROI 内平均灰度下限；
    - 最大灰度（默认 255）：ROI 内平均灰度上限。

    所有 ROI 的平均灰度都落在 [最小灰度, 最大灰度] 内才算 OK，
    否则 NG，并在 message 里列出具体哪个 ROI 超限。
    """

    name = "灰度均值范围判定"

    def detect(
        self,
        image: np.ndarray,
        rois: list[dict],
        params: dict[str, str],
    ) -> DetectionOutput:
        min_gray = get_float(params, "最小灰度", 0.0)
        max_gray = get_float(params, "最大灰度", 255.0)

        details: list[dict] = []
        ng_reasons: list[str] = []
        for roi in rois:
            roi_name = str(roi.get("name", "ROI"))
            crop = crop_roi(image, roi)
            if crop is None or crop.size == 0:
                ng_reasons.append(f"{roi_name} 超出图像范围")
                details.append({"roi": roi_name, "mean_gray": None, "ok": False})
                continue

            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            mean_gray = float(gray.mean())
            ok = min_gray <= mean_gray <= max_gray
            details.append(
                {
                    "roi": roi_name,
                    "mean_gray": round(mean_gray, 2),
                    "ok": ok,
                }
            )
            if not ok:
                ng_reasons.append(
                    f"{roi_name} 灰度 {mean_gray:.1f} 超出"
                    f" [{min_gray:.1f}, {max_gray:.1f}]"
                )

        return DetectionOutput(
            ok=not ng_reasons,
            message="；".join(ng_reasons) if ng_reasons else "OK",
            details=details,
        )
