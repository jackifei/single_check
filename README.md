# 兴龙机加刻码机视觉检测  、
# 相机数量 ： 一拖二
# 邓飞
## 运行环境

- Python 3.12
- PyQt6 >= 6.6

安装依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

```

启动程序：
```powershell
python main.py
```

## PyInstaller 打包

安装打包工具：

```powershell
python -m pip install pyinstaller
```

打包 `main.py` 为单个 exe，并同时打包 `config`、`flow` 目录：

```powershell
pyinstaller --noconfirm --windowed --onefile --name SOP --add-data "config;config" --add-data "log;log" --add-data "flow;flow" main.py
```
打包小exe，附加配置文件，运行时自动创建
```
pyinstaller -D main.py --noconfirm --windowed --icon=MyAppLog.ico --name single_check --uac-admin --add-data "config;config" --add-data "log;log" --add-data "flow;flow"
```
说明：Windows 下 `--add-data` 使用分号 `;` 分隔源目录和目标目录；Linux/macOS 使用冒号 `:`。

