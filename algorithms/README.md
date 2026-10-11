# 算法目录说明

这里放自定义检测算法。模板编辑页里编辑的 ROI 和「检测参数」会作为输入传给算法，
算法只需返回「OK / NG + 原因」即可。

## 文件

- `base.py`：统一接口与工具函数（核心，见下）。
- `example_algorithm.py`：可直接运行的范例「灰度均值范围判定」，照着改即可。
- `detector.py`：AI 模型页使用的 YOLO ONNX 引擎，与模板检测接口是两套，互不影响。

## 接口约定

算法类继承 `DetectionAlgorithm`，实现一个方法：

```python
class MyAlgorithm(DetectionAlgorithm):
    name = "我的算法"  # 唯一名称，用于登记

    def detect(self, image, rois, params) -> DetectionOutput:
        ...
        return DetectionOutput(ok=True, message="OK", details=[])
```

### 输入

- `image`：OpenCV **BGR** 图像，`np.uint8`，形状 `(H, W, 3)`。
- `rois`：模板编辑里编辑的 ROI 列表，坐标在**原图像素坐标系**：

```python
# 旋转矩形
{"name": "ROI-1", "shape": "rect", "cx": 150, "cy": 120, "w": 200, "h": 150, "angle": 0}
# 圆形
{"name": "ROI-2", "shape": "circle", "cx": 400, "cy": 200, "radius": 60}
```

- `params`：「检测参数」表格转成的字典，按参数名称索引。表格里每行是
  `{"name": "阈值", "value": "0.8"}`，传入时变成 `{"阈值": "0.8"}`。

### 输出

`DetectionOutput`：

- `ok`：`True` = OK，`False` = NG。
- `message`：结果信息，NG 时填原因（会显示到运行看板对应工位）。
- `details`：可选明细列表，用于日志或扩展。

## 工具函数（在 base.py 里，直接 import）

```python
from algorithms import get_float, get_int, get_bool, get_str, crop_roi, params_to_dict

threshold = get_float(params, "阈值", 0.5)     # 按名称取浮点
count     = get_int(params, "数量", 1)
enabled   = get_bool(params, "是否启用", False)
text      = get_str(params, "模式", "")

crop = crop_roi(image, roi)                    # 按 ROI 裁出子图（支持旋转矩形/圆形）
```

取值失败时都会返回 `default`，不会抛异常。

## 注册与调用

用装饰器注册（示例里已做）：

```python
from algorithms import register_algorithm

@register_algorithm
class MyAlgorithm(DetectionAlgorithm):
    name = "我的算法"
    ...
```

以后「拍照检测」流程会这样调用：

```python
from algorithms import create_algorithm, params_to_dict

algorithm = create_algorithm(template["algorithm"])   # 模板里指定算法名
result = algorithm.detect(
    image=bgr_frame,
    rois=template["rois"],
    params=params_to_dict(template["other_params"]),
)
# result.ok  -> OK/NG
# result.message -> NG 原因
```

## 新增算法的步骤

1. 复制 `example_algorithm.py` 成你的文件，例如 `my_algorithm.py`。
2. 改类名和 `name`。
3. 实现 `detect()`，用 `get_*` 读参数、用 `crop_roi` 裁 ROI、用 OpenCV 处理。
4. 用 `@register_algorithm` 注册（或之后在流程里指定算法名）。

注意：`image` 是 BGR；裁出的 ROI 也是 BGR；`crop_roi` 对越界区域会裁剪，返回的图可能比设定小。
