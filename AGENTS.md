# 项目约定（single_check / 兴龙机加刻码机视觉检测）

## Python 解释器（重要）

本项目**必须**使用 Miniconda 创建的虚拟环境 `py312packages`（Python 3.12）作为解释器。

- 解释器绝对路径：`/opt/miniconda3/envs/py312packages/bin/python`
- 环境位置：`/opt/miniconda3/envs/py312packages`
- 该环境已安装：PyQt6、opencv-python、PyYAML、numpy

规则：

1. 运行脚本、跑测试、装依赖、调试页面等所有 Python 操作，默认一律使用上面的解释器路径，不再使用系统 `python` / `python3`。
2. 除非用户在当次对话中明确要求更换解释器或环境，否则不要切换到其它解释器。
3. 该环境已具备运行本项目所需的依赖，通常无需重新安装。

常用命令：

```bash
# 启动程序
/opt/miniconda3/envs/py312packages/bin/python main.py

# 单独调试某个页面
/opt/miniconda3/envs/py312packages/bin/python app/pages/camera_page.py

# 无显示器环境下做界面冒烟测试
QT_QPA_PLATFORM=offscreen /opt/miniconda3/envs/py312packages/bin/python your_script.py
```
