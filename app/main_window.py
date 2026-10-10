from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .help_dialog import HelpDialog
from .checkdog.license_manager import LicenseManager
from .services.config_service import ConfigService
from .theme import DEFAULT_THEME, stylesheet_for
from .pages import (
    AIModelPage,
    CameraPage,
    FlowPage,
    HardwareConfigPage,
    LogPage,
    MesPage,
    ParametersPage,
    PersonnelPage,
    ResultQueryPage,
    RunDashboardPage,
)
from .status_bar import StatusBar


# 按“修改4.md”要求：AI模型、结果查询、MES对接、日志、参数 5 个页面隐藏，
# 不加载进导航栏，但源文件与导出保持不变，需要恢复时把它们加回本列表即可。
NAV_ITEMS = [
    ("相机管理", CameraPage),
    ("运行看板", RunDashboardPage),
    ("模板编辑", FlowPage),
    ("硬件配置", HardwareConfigPage),
    ("人员管理", PersonnelPage),
]

# 已隐藏页面（保留源文件，仅作记录，便于一键恢复）：
# AIModelPage / ResultQueryPage / MesPage / LogPage / ParametersPage
HIDDEN_PAGE_NAMES = ("AI模型", "结果查询", "MES对接", "日志", "参数")

# 新增页面时：在 app/pages 下创建页面类，并在此列表中注册即可。


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("兴龙戴卡视觉检测")
        self.resize(1440, 860)
        self.setMinimumSize(1100, 700)

        self.status_bar = StatusBar()
        self.license_manager = LicenseManager()
        # 主题：启动时读取上次选择，默认黑色主题。
        self.config_service = ConfigService()
        self.theme_mode = str(
            self.config_service.load_page_config("theme").get("mode", DEFAULT_THEME)
        )
        self.stack = QStackedWidget()
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.help_dialog: HelpDialog | None = None
        self.global_tip_label: QLabel | None = None

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_pages()
        nav_bar = self._build_nav_bar()

        root.addWidget(nav_bar)
        root.addWidget(self.stack, 1)
        root.addWidget(self.status_bar)

        self.setCentralWidget(central)
        self._set_active_page(0)
        self._setup_license()
        # 应用上次选择的主题（不重复落盘）。
        self._apply_theme(self.theme_mode, persist=False)
        # 自启动：按保存配置自动打开相机并连接 IO 板卡。
        self._setup_autostart()

    def _build_pages(self) -> None:
        self.pages: list[QWidget] = []
        self.camera_page: CameraPage | None = None
        self.dashboard_page: RunDashboardPage | None = None
        self.flow_page: FlowPage | None = None
        self.ai_model_page: AIModelPage | None = None
        self.hardware_page: HardwareConfigPage | None = None
        for _, page_class in NAV_ITEMS:
            page = page_class()
            self.pages.append(page)
            self.stack.addWidget(page)
            # 将各页面顶部提示同步到主窗口导航栏右侧，减少页面内占用。
            page.tip_changed.connect(self._on_page_tip_changed)
            if isinstance(page, CameraPage):
                self.camera_page = page
                page.camera_metrics_changed.connect(self._on_camera_metrics_changed)
            if isinstance(page, RunDashboardPage):
                self.dashboard_page = page
            if isinstance(page, FlowPage):
                self.flow_page = page
            if isinstance(page, AIModelPage):
                self.ai_model_page = page
            if isinstance(page, HardwareConfigPage):
                self.hardware_page = page

        if self.camera_page is not None and self.dashboard_page is not None:
            self.camera_page.camera_image_changed.connect(
                self.dashboard_page.set_camera_image
            )
        if self.camera_page is not None and self.flow_page is not None:
            # 模板编辑 ROI 背景只跟随“快照”（拍照/打开本地图像），
            # 不随相机实时预览流逐帧刷新。
            self.camera_page.snapshot_changed.connect(self.flow_page.set_roi_image)
            # 模板编辑页“拍照检测”按钮：触发对应相机拍照并进入检测流程。
            self.flow_page.capture_detect_requested.connect(
                self._on_capture_detect_requested
            )
        if self.camera_page is not None and self.ai_model_page is not None:
            # 把相机管理页最新画面同步给 AI 模型页，供“使用相机画面”测试。
            self.camera_page.image_changed.connect(self.ai_model_page.set_camera_pixmap)
        if self.flow_page is not None and self.ai_model_page is not None:
            # 模板编辑页新建/复制/删除模板后，AI 模型页模板列表同步刷新。
            self.flow_page.template_list_changed.connect(
                self.ai_model_page.refresh_templates
            )

    def _build_nav_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("navBar")
        bar.setFixedHeight(48)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(2)

        app_title = QLabel("")
        app_title.setObjectName("navAppTitle")
        layout.addWidget(app_title)
        layout.addSpacing(12)

        for index, (label, _) in enumerate(NAV_ITEMS):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setMinimumHeight(34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.button_group.addButton(button, index)
            layout.addWidget(button)

        # 插入点：需要全局快捷操作/菜单时，可在这里继续添加工具栏按钮或 QMenu。

        layout.addStretch(1)

        self.global_tip_label = QLabel("操作提示：--")
        self.global_tip_label.setObjectName("navTip")
        self.global_tip_label.setWordWrap(False)
        layout.addWidget(self.global_tip_label)

        # 主题切换按钮：在黑色主题与新增的浅色主题之间切换。
        self.theme_button = QPushButton("浅色主题")
        self.theme_button.setObjectName("themeButton")
        self.theme_button.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_button)

        self.help_button = QPushButton("帮助")
        self.help_button.setObjectName("helpButton")
        self.help_button.clicked.connect(self._show_help)
        layout.addWidget(self.help_button)

        self.button_group.buttonClicked.connect(self._on_nav_clicked)
        return bar

    def _on_nav_clicked(self, button: QPushButton) -> None:
        index = self.button_group.id(button)
        if index >= 0:
            self._set_active_page(index)

    def _set_active_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        buttons = self.button_group.buttons()
        if 0 <= index < len(buttons):
            buttons[index].setChecked(True)

        page_title = NAV_ITEMS[index][0]
        self.status_bar.set_status("page", f"界面: {page_title}")
        if self.global_tip_label is not None:
            self.global_tip_label.setText(self.pages[index].current_tip())
        # 插入点：页面切换时可在此广播事件，例如暂停其他页面的定时刷新。

    def _on_page_tip_changed(self, tip: str) -> None:
        if self.global_tip_label is not None:
            self.global_tip_label.setText(tip)

    def _on_camera_metrics_changed(self, data: dict) -> None:
        # 一拖二：按相机序号更新 FPS（图像尺寸已从状态栏移除）。
        index = int(data.get("index", 1))
        fps = data.get("fps", "--")
        self.status_bar.set_status(f"fps{index}", f"FPS{index}: {fps}")

    def _toggle_theme(self) -> None:
        """在黑色主题与浅色主题之间切换，并保存选择。"""
        self.theme_mode = "light" if self.theme_mode == "dark" else "dark"
        self._apply_theme(self.theme_mode)

    def _apply_theme(self, mode: str, persist: bool = True) -> None:
        """应用主题：更新全局样式表与按钮文案，可选写入 config/theme.yaml。"""
        self.theme_mode = mode
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet_for(mode))
        self.theme_button.setText("深色主题" if mode == "light" else "浅色主题")
        if persist:
            self.config_service.save_page_config("theme", {"mode": mode})

    def _show_help(self) -> None:
        if self.help_dialog is None:
            self.help_dialog = HelpDialog(self)
            self.help_dialog.license_activated.connect(self._on_license_activated)
        self.help_dialog.show()
        self.help_dialog.raise_()
        self.help_dialog.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        # 关闭主窗口前，依次保存配置并释放各页面持有的资源（如相机）。
        for page in self.pages:
            page.auto_save_config()
            page.shutdown()
        super().closeEvent(event)

    def _setup_license(self) -> None:
        self.license_grace_timer = QTimer(self)
        self.license_grace_timer.setInterval(30 * 60 * 1000)
        self.license_grace_timer.timeout.connect(self._block_expired_license)
        if self.license_manager.is_expired():
            self.license_grace_timer.start()
            self.status_bar.set_status("ready", "授权已到期", kind="warn")

    def _setup_autostart(self) -> None:
        """按硬件页“自启动”配置，启动后自动打开相机并连接 IO 板卡。"""
        data = self.config_service.load_page_config("hardware")
        if not data.get("auto_start", False):
            return
        if self.camera_page is not None:
            self.camera_page.auto_open_cameras()
        if self.hardware_page is not None:
            self.hardware_page.auto_connect_io()

    def _on_capture_detect_requested(self, camera_index: int) -> None:
        """模板编辑页“拍照检测”：触发对应相机拍照，然后接入检测流程。"""
        if self.camera_page is not None:
            self.camera_page.capture_camera(camera_index)
        # 插入点：在此处接入检测流程——
        # 1) 用 self.flow_page.camera_template(camera_index) 取该相机分配的模板；
        # 2) 取该相机的当前帧，调用 algorithms/detector.py 做检测；
        # 3) 把结果写回 dashboard_page.set_inspection_result(camera_index, ok, msg)；
        # 4) 按结果调用 hardware_page.pulse_output(...) 输出 OK/NG 脉冲。

    def _block_expired_license(self) -> None:
        self.stack.setEnabled(False)
        self.license_grace_timer.stop()
        QMessageBox.warning(
            self,
            "授权已到期",
            "软件授权已到期，当前操作已锁定。\n请打开“帮助 -> 软件激活”输入新密钥。",
        )

    def _on_license_activated(self, expiry_date: str) -> None:
        self.stack.setEnabled(True)
        self.license_grace_timer.stop()
        self.status_bar.set_status("ready", f"授权到期：{expiry_date}", kind="ok")
