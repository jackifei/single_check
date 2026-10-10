from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.services.config_service import ConfigService
from app.theme import DEFAULT_THEME, stylesheet_for


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("兴龙视觉检测")
    app.setOrganizationName("兴龙视觉检测")
    # 启动即应用上次选择的主题（黑色 / 浅色），未设置时用默认黑色主题。
    theme_mode = str(
        ConfigService().load_page_config("theme").get("mode", DEFAULT_THEME)
    )
    app.setStyleSheet(stylesheet_for(theme_mode))

    window = MainWindow()
    window.show()
    return app.exec()




if __name__ == "__main__":
    raise SystemExit(main())








# 20261009#
# 创建分支
# 兴龙机加刻码机加上单机视觉检测，相机一拖二
