from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.pages.base_page import BasePage
    from app.services.config_service import ConfigService
    from app.widgets.detection_view import DetectionResultView
    from algorithms.detector import DetectionThread, YoloOnnxDetector
else:
    from .base_page import BasePage
    from ..services.config_service import ConfigService
    from ..widgets.detection_view import DetectionResultView
    from algorithms.detector import DetectionThread, YoloOnnxDetector


class AIModelPage(BasePage):
    """AI 模型配置页。

    功能：
    - 模型参数：模型文件、推理后端、设备、输入尺寸
    - 标签加载：加载标签文件（txt / yaml），类别列表展示
    - 阈值设置：全局置信度、NMS IoU、按类别独立阈值
    - 手动测试：打开本地图像或使用相机画面，执行一次检测并叠加显示结果

    配置跟随模板名称，保存到 flow/<模板名>/modelconfig/ 下：
    - model.yaml      模型路径与推理参数
    - labels.yaml     标签列表（含标签文件来源）
    - threshold.yaml  全局阈值与按类别阈值

    扩展点：推理引擎当前支持 YOLO ONNX（algorithms/detector.py），
    后续如需 PyTorch/TensorRT，可新增引擎类并保持 detect() 接口一致。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "AI模型",
            "配置模型参数、加载标签、设置阈值，并手动测试检测效果。",
            parent,
        )
        self.config_service = ConfigService()
        self.current_template_name = ""
        self.labels: list[str] = []
        self.detector = YoloOnnxDetector()
        self.detection_thread: DetectionThread | None = None
        self.test_pixmap: QPixmap | None = None
        self._test_frame: np.ndarray | None = None
        self._camera_pixmap: QPixmap | None = None
        self._build_ui()
        self._refresh_template_list()
        self.set_result("检测结果：AI 模型未加载")
        self.set_tip("操作提示：请选择模板，加载模型和标签后即可手动测试。")

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.add_to_content(self._build_template_group())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)
        splitter.addWidget(self._build_config_panel())
        splitter.addWidget(self._build_test_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 900])
        self.add_to_content(splitter, stretch=1)

    def _build_template_group(self) -> QGroupBox:
        group = QGroupBox("模板选择")
        layout = QHBoxLayout(group)
        layout.addWidget(QLabel("当前模板"))
        self.template_combo = QComboBox()
        layout.addWidget(self.template_combo, 1)
        hint = QLabel("AI 模型配置跟随模板，保存到 flow/&lt;模板名&gt;/modelconfig")
        hint.setObjectName("pageTip")
        layout.addWidget(hint)

        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        return group

    def _build_config_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        layout.addWidget(self._build_model_group())
        layout.addWidget(self._build_label_group())
        layout.addWidget(self._build_threshold_group())

        self.save_button = QPushButton("保存模型配置")
        self.save_button.setMinimumHeight(36)
        layout.addWidget(self.save_button)
        layout.addStretch(1)

        scroll.setWidget(container)
        self.save_button.clicked.connect(self._save_config)
        return scroll

    def _build_model_group(self) -> QGroupBox:
        group = QGroupBox("模型参数")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.model_file_edit = QLineEdit()
        self.model_file_edit.setPlaceholderText("选择 .onnx 模型文件")
        self.model_browse_button = QPushButton("浏览")
        model_row = QWidget()
        model_layout = QHBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.addWidget(self.model_file_edit, 1)
        model_layout.addWidget(self.model_browse_button)
        form.addRow("模型文件", model_row)

        model_buttons = QHBoxLayout()
        self.load_model_button = QPushButton("加载模型")
        self.release_model_button = QPushButton("释放模型")
        model_buttons.addWidget(self.load_model_button)
        model_buttons.addWidget(self.release_model_button)
        model_buttons.addStretch(1)
        button_widget = QWidget()
        button_widget.setLayout(model_buttons)
        form.addRow("", button_widget)

        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["ONNX (OpenCV DNN)", "PyTorch (预留)", "TensorRT (预留)"])
        form.addRow("推理后端", self.backend_combo)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["CPU", "CUDA GPU (预留)"])
        form.addRow("推理设备", self.device_combo)

        size_row = QWidget()
        size_layout = QHBoxLayout(size_row)
        size_layout.setContentsMargins(0, 0, 0, 0)
        self.input_w_spin = QSpinBox()
        self.input_w_spin.setRange(32, 4096)
        self.input_w_spin.setSingleStep(32)
        self.input_w_spin.setValue(640)
        self.input_h_spin = QSpinBox()
        self.input_h_spin.setRange(32, 4096)
        self.input_h_spin.setSingleStep(32)
        self.input_h_spin.setValue(640)
        size_layout.addWidget(self.input_w_spin)
        size_layout.addWidget(QLabel("×"))
        size_layout.addWidget(self.input_h_spin)
        size_layout.addStretch(1)
        form.addRow("输入尺寸", size_row)

        self.model_browse_button.clicked.connect(self._browse_model)
        self.load_model_button.clicked.connect(self._load_model)
        self.release_model_button.clicked.connect(self._release_model)
        return group

    def _build_label_group(self) -> QGroupBox:
        group = QGroupBox("标签加载")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self.label_file_edit = QLineEdit()
        self.label_file_edit.setPlaceholderText("选择标签文件（txt / yaml，每行一个类别名）")
        self.label_browse_button = QPushButton("浏览")
        self.load_labels_button = QPushButton("加载标签")
        row.addWidget(self.label_file_edit, 1)
        row.addWidget(self.label_browse_button)
        row.addWidget(self.load_labels_button)
        layout.addLayout(row)

        self.labels_list = QListWidget()
        self.labels_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.labels_list, 1)

        self.label_browse_button.clicked.connect(self._browse_labels)
        self.load_labels_button.clicked.connect(self._load_labels_file)
        return group

    def _build_threshold_group(self) -> QGroupBox:
        group = QGroupBox("阈值设置")
        layout = QVBoxLayout(group)

        top = QHBoxLayout()
        top.addWidget(QLabel("全局置信度"))
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.01, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(0.25)
        top.addWidget(self.confidence_spin)

        top.addWidget(QLabel("NMS IoU"))
        self.iou_spin = QDoubleSpinBox()
        self.iou_spin.setRange(0.01, 1.0)
        self.iou_spin.setSingleStep(0.05)
        self.iou_spin.setValue(0.45)
        top.addWidget(self.iou_spin)

        self.reset_threshold_button = QPushButton("全部恢复为全局阈值")
        top.addWidget(self.reset_threshold_button)
        top.addStretch(1)
        layout.addLayout(top)

        hint = QLabel("按类别阈值可单独调整；留空或解析失败时使用全局置信度。")
        hint.setObjectName("pageTip")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.threshold_table = QTableWidget(0, 2)
        self.threshold_table.setHorizontalHeaderLabels(["类别", "阈值"])
        header = self.threshold_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.threshold_table.verticalHeader().setVisible(False)
        self.threshold_table.setAlternatingRowColors(True)
        layout.addWidget(self.threshold_table, 1)

        self.reset_threshold_button.clicked.connect(self._reset_thresholds)
        return group

    def _build_test_panel(self) -> QGroupBox:
        group = QGroupBox("手动测试")
        layout = QVBoxLayout(group)

        buttons = QHBoxLayout()
        self.open_image_button = QPushButton("打开测试图像")
        self.use_camera_button = QPushButton("使用相机画面")
        self.detect_button = QPushButton("开始检测")
        self.clear_button = QPushButton("清空结果")
        for button in (
            self.open_image_button,
            self.use_camera_button,
            self.detect_button,
            self.clear_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.detection_view = DetectionResultView()
        layout.addWidget(self.detection_view, 1)

        self.detect_status_label = QLabel("检测状态：未检测")
        self.detect_status_label.setObjectName("pageTip")
        layout.addWidget(self.detect_status_label)

        self.result_table = QTableWidget(0, 6)
        self.result_table.setHorizontalHeaderLabels(
            ["类别", "置信度", "X", "Y", "宽", "高"]
        )
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.setMaximumHeight(180)
        layout.addWidget(self.result_table)

        self.open_image_button.clicked.connect(self._open_test_image)
        self.use_camera_button.clicked.connect(self._use_camera_image)
        self.detect_button.clicked.connect(self._start_detection)
        self.clear_button.clicked.connect(self._clear_results)
        return group

    # ------------------------------------------------------------------
    # 模板切换与配置读写
    # ------------------------------------------------------------------
    def _refresh_template_list(self) -> None:
        """从 flow 目录刷新模板下拉框（模板编辑页增删模板后也会调用）。"""
        names = self.config_service.list_templates()
        current = self.template_combo.currentText()
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItems(names)
        self.template_combo.blockSignals(False)
        if current in names:
            self._load_template_config(current)
        elif names:
            self._load_template_config(names[0])
        else:
            self.current_template_name = ""

    def refresh_templates(self) -> None:
        """供主窗口在模板列表变化时调用，保持与模板编辑页同步。"""
        self._refresh_template_list()

    def _on_template_changed(self, name: str) -> None:
        if name:
            self._load_template_config(name)

    def _load_template_config(self, name: str) -> None:
        self.current_template_name = name
        category = ConfigService.MODEL_CONFIG_DIR
        model_data = self.config_service.load_template_category(name, category, "model.yaml")
        labels_data = self.config_service.load_template_category(name, category, "labels.yaml")
        threshold_data = self.config_service.load_template_category(name, category, "threshold.yaml")

        model_file = str(model_data.get("model_file", ""))
        if not model_file:
            # 首次进入该模板时，回退读取模板自身的 model_file 字段。
            template = self.config_service.load_template(name)
            model_file = str(template.get("model_file", ""))
        self.model_file_edit.setText(model_file)

        backend = str(model_data.get("backend", "ONNX (OpenCV DNN)"))
        if self.backend_combo.findText(backend) >= 0:
            self.backend_combo.setCurrentText(backend)
        device = str(model_data.get("device", "CPU"))
        if self.device_combo.findText(device) >= 0:
            self.device_combo.setCurrentText(device)
        self.input_w_spin.setValue(int(model_data.get("input_width", 640)))
        self.input_h_spin.setValue(int(model_data.get("input_height", 640)))

        self.labels = [str(item) for item in (labels_data.get("labels") or [])]
        self.label_file_edit.setText(str(labels_data.get("source_file", "")))
        self._refresh_labels_view()

        self.confidence_spin.setValue(float(threshold_data.get("confidence", 0.25)))
        self.iou_spin.setValue(float(threshold_data.get("nms_iou", 0.45)))
        per_class = threshold_data.get("per_class") or {}
        self._rebuild_threshold_table(per_class)

        # 模板切换后释放已加载的模型，避免串模板使用。
        self.detector.release()
        self.set_result(f"检测结果：已加载模板「{name}」的 AI 模型配置")
        self.set_tip("操作提示：加载模型和标签后即可手动测试，保存写入 modelconfig 目录。")

    def _save_config(self) -> None:
        name = self.current_template_name
        if not name:
            self.set_tip("操作提示：请先选择模板。")
            return
        category = ConfigService.MODEL_CONFIG_DIR
        self.config_service.save_template_category(
            name,
            category,
            "model.yaml",
            {
                "model_file": self.model_file_edit.text().strip(),
                "backend": self.backend_combo.currentText(),
                "device": self.device_combo.currentText(),
                "input_width": self.input_w_spin.value(),
                "input_height": self.input_h_spin.value(),
            },
        )
        self.config_service.save_template_category(
            name,
            category,
            "labels.yaml",
            {
                "source_file": self.label_file_edit.text().strip(),
                "labels": list(self.labels),
            },
        )
        self.config_service.save_template_category(
            name,
            category,
            "threshold.yaml",
            {
                "confidence": self.confidence_spin.value(),
                "nms_iou": self.iou_spin.value(),
                "per_class": self._collect_thresholds(),
            },
        )
        self.set_tip(f"操作提示：AI 模型配置已保存到 flow/{name}/modelconfig/。")

    def auto_save_config(self) -> None:
        self._save_config()

    # ------------------------------------------------------------------
    # 模型加载
    # ------------------------------------------------------------------
    def _browse_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "加载模型",
            "",
            "ONNX 模型 (*.onnx);;所有文件 (*.*)",
        )
        if file_path:
            self.model_file_edit.setText(file_path)

    def _load_model(self) -> None:
        path = self.model_file_edit.text().strip()
        if not path:
            self._browse_model()
            path = self.model_file_edit.text().strip()
        if not path:
            return

        backend = self.backend_combo.currentText()
        if not backend.startswith("ONNX"):
            QMessageBox.information(
                self,
                "提示",
                f"{backend} 暂未实现，当前仅支持 ONNX 模型。",
            )
            return
        if not Path(path).exists():
            QMessageBox.warning(self, "加载失败", f"模型文件不存在：{path}")
            return
        try:
            self.detector.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "加载失败", f"模型加载失败：{exc}")
            return
        self.set_result(f"检测结果：模型已加载（{Path(path).name}）")
        self.set_tip("操作提示：模型已就绪，可打开测试图像执行手动检测。")

    def _release_model(self) -> None:
        self.detector.release()
        self.set_result("检测结果：模型已释放")
        self.set_tip("操作提示：可在“保存模型配置”后继续编辑其他模板。")

    # ------------------------------------------------------------------
    # 标签加载
    # ------------------------------------------------------------------
    def _browse_labels(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "加载标签文件",
            "",
            "标签文件 (*.txt *.names *.yaml *.yml);;所有文件 (*.*)",
        )
        if file_path:
            self.label_file_edit.setText(file_path)

    def _load_labels_file(self) -> None:
        path = self.label_file_edit.text().strip()
        if not path:
            self._browse_labels()
            path = self.label_file_edit.text().strip()
        if not path:
            return
        if not Path(path).exists():
            QMessageBox.warning(self, "加载失败", f"标签文件不存在：{path}")
            return
        try:
            labels = self._parse_labels_file(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "加载失败", f"标签文件解析失败：{exc}")
            return
        if not labels:
            QMessageBox.information(self, "提示", "标签文件为空，未加载任何类别。")
            return
        self.labels = labels
        self._refresh_labels_view()
        self.set_result(f"检测结果：已加载 {len(labels)} 个标签")
        self.set_tip("操作提示：类别数量需与模型输出通道匹配，保存后写入 labels.yaml。")

    @staticmethod
    def _parse_labels_file(path: str) -> list[str]:
        """解析标签文件：txt/names 每行一个类别名，yaml 支持列表。"""
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or []
            if isinstance(data, dict):
                data = data.get("labels") or data.get("names") or []
            if not isinstance(data, list):
                raise ValueError("YAML 标签文件应为列表或包含 labels/names 列表")
            return [str(item).strip() for item in data if str(item).strip()]

        labels: list[str] = []
        for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 兼容 "0 person" 这类带序号格式，取最后一段作为类别名。
            labels.append(line.split()[-1])
        return labels

    def _refresh_labels_view(self) -> None:
        self.labels_list.clear()
        for index, name in enumerate(self.labels):
            self.labels_list.addItem(QListWidgetItem(f"{index}: {name}"))
        self._rebuild_threshold_table()

    # ------------------------------------------------------------------
    # 阈值设置
    # ------------------------------------------------------------------
    def _rebuild_threshold_table(self, initial: dict | None = None) -> None:
        self.threshold_table.setRowCount(0)
        for name in self.labels:
            row = self.threshold_table.rowCount()
            self.threshold_table.insertRow(row)

            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.threshold_table.setItem(row, 0, name_item)

            value = (initial or {}).get(name, self.confidence_spin.value())
            value_item = QTableWidgetItem(f"{float(value):.3f}")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.threshold_table.setItem(row, 1, value_item)

    def _collect_thresholds(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for row in range(self.threshold_table.rowCount()):
            name_item = self.threshold_table.item(row, 0)
            value_item = self.threshold_table.item(row, 1)
            if not name_item or not value_item:
                continue
            name = name_item.text().strip()
            if not name:
                continue
            try:
                value = float(value_item.text())
            except ValueError:
                value = self.confidence_spin.value()
            result[name] = max(0.01, min(1.0, value))
        return result

    def _reset_thresholds(self) -> None:
        self._rebuild_threshold_table()
        self.set_tip("操作提示：所有类别阈值已恢复为全局置信度。")

    # ------------------------------------------------------------------
    # 手动测试
    # ------------------------------------------------------------------
    def _open_test_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开测试图像",
            "",
            "图像文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*.*)",
        )
        if not file_path:
            return
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "打开失败", "图像文件无法读取。")
            return
        self._set_test_image(pixmap)

    def set_camera_pixmap(self, pixmap: QPixmap) -> None:
        """主窗口把相机管理页的最新画面广播到这里，供“使用相机画面”按钮使用。"""
        self._camera_pixmap = pixmap

    def _use_camera_image(self) -> None:
        if self._camera_pixmap is None or self._camera_pixmap.isNull():
            QMessageBox.information(self, "提示", "暂无相机画面，请先在相机管理页打开相机。")
            return
        self._set_test_image(self._camera_pixmap)

    def _set_test_image(self, pixmap: QPixmap) -> None:
        self.test_pixmap = pixmap
        self._test_frame = self._pixmap_to_rgb(pixmap)
        self.detection_view.set_image(pixmap)
        self.detection_view.set_results([])
        self.result_table.setRowCount(0)
        self.detect_status_label.setText("检测状态：已加载测试图像")
        self.set_result(
            f"检测结果：已加载测试图像 {pixmap.width()}x{pixmap.height()}"
        )

    @staticmethod
    def _pixmap_to_rgb(pixmap: QPixmap) -> np.ndarray | None:
        if pixmap is None or pixmap.isNull():
            return None
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        pointer = image.bits()
        pointer.setsize(image.sizeInBytes())
        array = np.frombuffer(pointer, dtype=np.uint8).reshape(
            image.height(), image.width(), 3
        )
        return array.copy()

    def _start_detection(self) -> None:
        if self._test_frame is None:
            QMessageBox.information(
                self, "提示", "请先打开测试图像或使用相机画面。"
            )
            return
        if not self.detector.is_loaded():
            self._load_model()
            if not self.detector.is_loaded():
                return
        if self.detection_thread is not None and self.detection_thread.isRunning():
            return

        self.detect_button.setEnabled(False)
        self.set_result("检测结果：正在检测…")
        self.detect_status_label.setText("检测状态：检测中…")
        self.detection_thread = DetectionThread(
            self.detector,
            self._test_frame,
            confidence=self.confidence_spin.value(),
            iou_threshold=self.iou_spin.value(),
            labels=list(self.labels) or None,
            input_size=(self.input_w_spin.value(), self.input_h_spin.value()),
            class_thresholds=self._collect_thresholds() or None,
            parent=self,
        )
        self.detection_thread.detection_done.connect(self._on_detection_done)
        self.detection_thread.detection_error.connect(self._on_detection_error)
        self.detection_thread.finished.connect(self._on_detection_finished)
        self.detection_thread.start()

    def _on_detection_done(self, results: list, elapsed: float) -> None:
        self.detection_view.set_results(results)
        self.result_table.setRowCount(0)
        for item in results:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            values = [
                item.class_name,
                f"{item.confidence:.3f}",
                str(item.x),
                str(item.y),
                str(item.w),
                str(item.h),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.result_table.setItem(row, column, cell)
        self.detect_status_label.setText(
            f"检测状态：检测到 {len(results)} 个目标，耗时 {elapsed * 1000:.1f} ms"
        )
        self.set_result(f"检测结果：检测到 {len(results)} 个目标")

    def _on_detection_error(self, message: str) -> None:
        self.detect_status_label.setText(f"检测状态：失败（{message}）")
        self.set_result("检测结果：检测失败")
        QMessageBox.warning(self, "检测失败", message)

    def _on_detection_finished(self) -> None:
        self.detect_button.setEnabled(True)
        if self.detection_thread is not None:
            self.detection_thread.deleteLater()
            self.detection_thread = None

    def _clear_results(self) -> None:
        self.detection_view.set_results([])
        self.result_table.setRowCount(0)
        self.detect_status_label.setText("检测状态：已清空")

    # ------------------------------------------------------------------
    # 关闭处理
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:
        if self.detection_thread is not None:
            if self.detection_thread.isRunning():
                self.detection_thread.wait(2000)
            self.detection_thread = None
        self.detector.release()
        super().closeEvent(event)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.standalone import run_page

    raise SystemExit(run_page(sys.modules[__name__].AIModelPage))
