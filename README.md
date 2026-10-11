# 兴龙机加刻码机视觉检测

# 相机数量：一拖二（同时打开两台 USB 相机）
# 运行平台：Linux
# 邓飞

## 运行环境

- Python 3.12
- PyQt6 >= 6.6

安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

启动程序：

```bash
python main.py
```

## 当前功能范围（对应 app/修改4.md）

- 运行平台：Linux（相机采集使用 OpenCV + V4L2 后端，Windows 自动切 DirectShow，macOS 使用 AVFoundation 便于调试）。
- 相机管理：仅 USB 相机，界面上下分成两块，各放一台相机（画面可缩放/拖动/取像素信息）；单台相机的画面、开关、参数封装在 `app/widgets/camera_unit.py` 的 `CameraUnit` 中，实例化两次即为双相机。页面底部提供“保存相机配置”和“一键打开相机”。已取消相机/标定功能切换（标定面板源码保留在 `app/widgets/calibration_panel.py`，暂未接入）。
- 相机参数：界面只暴露“曝光时间”；增益、帧率、触发模式、像素格式保持默认值并在界面隐藏。
- 底部状态栏按相机分别显示 `FPS1 / FPS2 / 图像1 / 图像2`。
- 主题：导航栏右上角可在“浅色主题 / 深色主题”之间切换，选择保存在 `config/theme.yaml`。
- 已隐藏页面：AI模型、结果查询、MES对接、日志、参数。源文件保留，恢复时把它们加回 `app/main_window.py` 的 `NAV_ITEMS` 即可。

## 相机配置

相机参数保存到 `config/camera.yaml`，结构如下（两台相机一个列表）：

```yaml
camera_type: USB 相机
cameras:
  - index: 1
    device: 0
    device_name: /dev/video0
    exposure: 5000.0
    gain: 1.0
    frame_rate: 30.0
    trigger: 连续采集
    pixel_format: Mono8
  - index: 2
    device: 1
    ...
```

旧版单相机扁平结构（`exposure` / `gain` 等直接写在顶层）在加载时会回显到 1 号相机，不会丢失参数。

## PyInstaller 打包

安装打包工具：

```bash
python -m pip install pyinstaller
```

打包小 exe，附加配置文件，运行时自动创建：

```bash
pyinstaller -D main.py --noconfirm --windowed --icon=MyAppLog.ico --name single_check --add-data "config:config" --add-data "log:log" --add-data "flow:flow"
```

说明：Windows 下 `--add-data` 使用分号 `;` 分隔源目录和目标目录；Linux/macOS 使用冒号 `:`。
