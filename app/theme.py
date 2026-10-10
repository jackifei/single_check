"""应用主题样式表。

按“修改4.md”要求提供两套主题：
- dark ：原有黑色主题（VSCode 风格），保持默认；
- light：新增的简约浅色主题（白底 + 蓝色强调色）。

切换入口在 main_window.py 顶部导航栏的“浅色/深色”按钮，
选择结果保存到 config/theme.yaml，启动时由 main.py 读取。

插入点：新增主题时，在 THEMES 中登记一份完整 QSS 即可，
页面代码不需要改动（自定义绘制的图像控件自绘背景，不跟随主题）。
"""

from __future__ import annotations

DEFAULT_THEME = "dark"


DARK_STYLESHEET = """
QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}

QFrame#navBar {
    background-color: #252526;
    border-bottom: 1px solid #3c3c3c;
}

QLabel#navAppTitle {
    color: #ffffff;
    font-size: 16px;
    font-weight: 700;
    padding: 0 8px;
}

QLabel#navTip {
    color: #9d9d9d;
    padding: 0 8px;
}

QLabel#navTitle {
    color: #9d9d9d;
    font-size: 11px;
    letter-spacing: 1px;
    padding: 8px 4px;
}

QPushButton#navButton {
    text-align: center;
    padding: 6px 16px;
    border: none;
    border-bottom: 3px solid transparent;
    border-radius: 0;
    background: transparent;
    color: #cccccc;
}

QPushButton#navButton:hover {
    background-color: #2a2d2e;
    color: #ffffff;
}

QPushButton#navButton:checked {
    background-color: #37373d;
    border-bottom: 3px solid #007acc;
    color: #ffffff;
}

QFrame#pageHeader {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
}

QLabel#pageResult {
    color: #4ec9b0;
    font-weight: 600;
}

QLabel#pageTip {
    color: #9d9d9d;
    font-size: 12px;
}

QGroupBox {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #dcdcdc;
}

QPushButton {
    background-color: #333333;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 6px 12px;
    color: #d4d4d4;
}

QPushButton:hover {
    background-color: #3c3c3c;
    border-color: #6c6c6c;
}

QPushButton:pressed {
    background-color: #2a2a2a;
}

QPushButton:checked {
    background-color: #0e639c;
    border-color: #007acc;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #2a2a2a;
    color: #6a6a6a;
    border-color: #3a3a3a;
}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    padding: 4px 6px;
    selection-background-color: #264f78;
}

QComboBox QAbstractItemView {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    selection-background-color: #264f78;
}

QTableWidget,
QTableView,
QTreeWidget {
    background-color: #252526;
    alternate-background-color: #2a2a2b;
    border: 1px solid #3c3c3c;
    gridline-color: #3c3c3c;
}

QTableWidget::item,
QTreeWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background-color: #333333;
    color: #d4d4d4;
    border: none;
    border-right: 1px solid #3c3c3c;
    border-bottom: 1px solid #3c3c3c;
    padding: 6px;
    font-weight: 600;
}

QSplitter::handle {
    background-color: #3c3c3c;
}

QSplitter::handle:horizontal {
    width: 5px;
}

QSplitter::handle:vertical {
    height: 5px;
}

QLabel#imageView {
    background-color: #111111;
    border: 1px dashed #4a4a4a;
    border-radius: 4px;
}

QLabel#ioIndicator {
    font-size: 18px;
}

QFrame#statCard {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
}

QLabel#statCardTitle {
    color: #9d9d9d;
    font-size: 12px;
}

QLabel#statCardValue {
    color: #ffffff;
    font-size: 24px;
    font-weight: 700;
}

QWidget#cameraView {
    background-color: #111111;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
}

QWidget#roiCanvas {
    background-color: #111111;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
}

QFrame#statusBar {
    background-color: #007acc;
    color: #ffffff;
}

QFrame#statusBar QLabel {
    background: transparent;
    color: #ffffff;
}

QLabel#statusText {
    color: #ffffff;
    padding: 0 6px;
}

QScrollArea {
    border: none;
}
"""

# ---- 下边是“修改4.md”新增的浅色主题与主题表 ----

# 相机页设备选择框 / 图像信息条 / 看板模板框，改用 objectName 让两套主题都能换肤。
DARK_STYLESHEET += """
QComboBox#cameraDeviceCombo {
    background-color: #123a56;
    color: #ffffff;
    border: 2px solid #4ec9b0;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
}

QLabel#imageInfoLabel {
    padding: 4px 6px;
    background: #252526;
    color: #9d9d9d;
    border-radius: 3px;
}

QComboBox#dashboardTemplateCombo {
    background-color: #123a56;
    color: #ffffff;
    border: 2px solid #4ec9b0;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
}
"""


LIGHT_STYLESHEET = """
QWidget {
    background-color: #f4f5f7;
    color: #202124;
    font-family: "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", sans-serif;
    font-size: 13px;
}

QFrame#navBar {
    background-color: #ffffff;
    border-bottom: 1px solid #dfe1e6;
}

QLabel#navAppTitle {
    color: #1a1a1a;
    font-size: 16px;
    font-weight: 700;
    padding: 0 8px;
}

QLabel#navTip {
    color: #5f6368;
    padding: 0 8px;
}

QLabel#navTitle {
    color: #5f6368;
    font-size: 11px;
    letter-spacing: 1px;
    padding: 8px 4px;
}

QPushButton#navButton {
    text-align: center;
    padding: 6px 16px;
    border: none;
    border-bottom: 3px solid transparent;
    border-radius: 0;
    background: transparent;
    color: #3c4043;
}

QPushButton#navButton:hover {
    background-color: #f1f3f4;
    color: #1a1a1a;
}

QPushButton#navButton:checked {
    background-color: #e8f0fe;
    border-bottom: 3px solid #2f6feb;
    color: #1a73e8;
}

QFrame#pageHeader {
    background-color: #ffffff;
    border: 1px solid #dfe1e6;
    border-radius: 4px;
}

QLabel#pageResult {
    color: #0b7a63;
    font-weight: 600;
}

QLabel#pageTip {
    color: #5f6368;
    font-size: 12px;
}

QGroupBox {
    border: 1px solid #dfe1e6;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: 600;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #3c4043;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #d8dbe0;
    border-radius: 3px;
    padding: 6px 12px;
    color: #202124;
}

QPushButton:hover {
    background-color: #f1f3f4;
    border-color: #c3c7cd;
}

QPushButton:pressed {
    background-color: #e6e8eb;
}

QPushButton:checked {
    background-color: #e8f0fe;
    border-color: #2f6feb;
    color: #1a73e8;
}

QPushButton:disabled {
    background-color: #f1f3f4;
    color: #9aa0a6;
    border-color: #e2e4e8;
}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #d8dbe0;
    border-radius: 3px;
    padding: 4px 6px;
    selection-background-color: #cfe0ff;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d8dbe0;
    selection-background-color: #cfe0ff;
}

QTableWidget,
QTableView,
QTreeWidget {
    background-color: #ffffff;
    alternate-background-color: #f7f8fa;
    border: 1px solid #dfe1e6;
    gridline-color: #e6e8eb;
}

QTableWidget::item,
QTreeWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background-color: #eef0f3;
    color: #3c4043;
    border: none;
    border-right: 1px solid #dfe1e6;
    border-bottom: 1px solid #dfe1e6;
    padding: 6px;
    font-weight: 600;
}

QSplitter::handle {
    background-color: #dfe1e6;
}

QSplitter::handle:horizontal {
    width: 5px;
}

QSplitter::handle:vertical {
    height: 5px;
}

QLabel#imageView {
    background-color: #111111;
    border: 1px dashed #b6bcc6;
    border-radius: 4px;
}

QLabel#ioIndicator {
    font-size: 18px;
}

QFrame#statCard {
    background-color: #ffffff;
    border: 1px solid #dfe1e6;
    border-radius: 6px;
}

QLabel#statCardTitle {
    color: #5f6368;
    font-size: 12px;
}

QLabel#statCardValue {
    color: #1a1a1a;
    font-size: 24px;
    font-weight: 700;
}

QWidget#cameraView {
    background-color: #111111;
    border: 1px solid #dfe1e6;
    border-radius: 4px;
}

QWidget#roiCanvas {
    background-color: #111111;
    border: 1px solid #dfe1e6;
    border-radius: 4px;
}

QComboBox#cameraDeviceCombo {
    background-color: #ffffff;
    color: #202124;
    border: 2px solid #2f6feb;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
}

QLabel#imageInfoLabel {
    padding: 4px 6px;
    background: #eceff3;
    color: #3c4043;
    border-radius: 3px;
}

QComboBox#dashboardTemplateCombo {
    background-color: #ffffff;
    color: #202124;
    border: 2px solid #2f6feb;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
}

/* 状态栏在浅色主题下仍使用蓝色底，保证浅色状态文字可读。 */
QFrame#statusBar {
    background-color: #007acc;
    color: #ffffff;
}

QFrame#statusBar QLabel {
    background: transparent;
    color: #ffffff;
}

QLabel#statusText {
    color: #ffffff;
    padding: 0 6px;
}

QScrollArea {
    border: none;
}
"""


# 主题表：新增主题只需在此登记。
THEMES = {
    "dark": DARK_STYLESHEET,
    "light": LIGHT_STYLESHEET,
}

# 兼容旧代码（standalone.py 等）使用的中性名称，默认黑色主题。
APP_STYLESHEET = DARK_STYLESHEET


def stylesheet_for(mode: str) -> str:
    """按主题名返回样式表；名称非法时回退到默认主题。"""
    return THEMES.get(mode, THEMES[DEFAULT_THEME])
