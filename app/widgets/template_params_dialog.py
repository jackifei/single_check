from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TemplateParamsDialog(QDialog):
    """模板参数编辑弹窗。

    包含 Detection Config、Model Config、Other Config，编辑结果返回给
    模板编辑页后随当前模板一起保存。
    """

    FUNCTION_OPTIONS = ["功能1", "功能2", "功能3", "功能4", "功能5"]

    def __init__(
        self,
        model_file: str = "",
        detection: dict | None = None,
        other_params: list[dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑参数")
        self.resize(820, 720)
        self._model_file = model_file or ""
        self._detection = detection or {}
        self._other_params = other_params or []
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        layout.addWidget(self._build_detection_group())
        layout.addWidget(self._build_model_group())
        layout.addWidget(self._build_other_group())
        layout.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        buttons.addWidget(self.ok_button)
        buttons.addWidget(self.cancel_button)
        root.addLayout(buttons)

        self.ok_button.clicked.connect(self._accept)
        self.cancel_button.clicked.connect(self.reject)

    def _build_detection_group(self) -> QGroupBox:
        group = QGroupBox("Detection Config")
        layout = QVBoxLayout(group)

        param_row = QHBoxLayout()
        param_row.addWidget(QLabel("置信度"))
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.01, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(0.5)
        param_row.addWidget(self.confidence_spin)

        param_row.addWidget(QLabel("检测数量"))
        self.detection_count_spin = QSpinBox()
        self.detection_count_spin.setRange(1, 1000)
        self.detection_count_spin.setValue(20)
        param_row.addWidget(self.detection_count_spin)

        self.spare_edit_1 = QLineEdit()
        self.spare_edit_1.setPlaceholderText("备用参数1")
        param_row.addWidget(QLabel("备用参数1"))
        param_row.addWidget(self.spare_edit_1)

        self.spare_edit_2 = QLineEdit()
        self.spare_edit_2.setPlaceholderText("备用参数2")
        param_row.addWidget(QLabel("备用参数2"))
        param_row.addWidget(self.spare_edit_2)

        self.spare_edit_3 = QLineEdit()
        self.spare_edit_3.setPlaceholderText("备用参数3")
        param_row.addWidget(QLabel("备用参数3"))
        param_row.addWidget(self.spare_edit_3)
        param_row.addStretch(1)
        layout.addLayout(param_row)

        enable_row = QHBoxLayout()
        enable_row.addWidget(QLabel("启用项"))
        self.enable_check_1 = QCheckBox("是否启用1")
        self.enable_check_2 = QCheckBox("是否启用2")
        self.enable_check_3 = QCheckBox("是否启用3")
        self.enable_check_4 = QCheckBox("是否启用4")
        self.enable_check_5 = QCheckBox("是否启用5")
        for check in (
            self.enable_check_1,
            self.enable_check_2,
            self.enable_check_3,
            self.enable_check_4,
            self.enable_check_5,
        ):
            enable_row.addWidget(self._wrap_with_border(check))
        enable_row.addStretch(1)
        layout.addLayout(enable_row)

        function_grid = QGridLayout()
        self.function_combo_1 = QComboBox()
        self.function_combo_2 = QComboBox()
        self.function_combo_3 = QComboBox()
        self.function_combo_4 = QComboBox()
        self.function_combo_5 = QComboBox()
        combos = [
            self.function_combo_1,
            self.function_combo_2,
            self.function_combo_3,
            self.function_combo_4,
            self.function_combo_5,
        ]
        for index, combo in enumerate(combos, start=1):
            combo.addItems(self.FUNCTION_OPTIONS)
            function_grid.addWidget(QLabel(f"功能选择{index}"), 0, index - 1)
            function_grid.addWidget(combo, 1, index - 1)
        layout.addLayout(function_grid)
        layout.addStretch(1)
        return group

    def _build_model_group(self) -> QGroupBox:
        group = QGroupBox("Model Config")
        layout = QVBoxLayout(group)

        self.model_file_label = QLabel(f"模型文件：{self._model_file or '未加载'}")
        self.model_file_label.setWordWrap(True)
        layout.addWidget(self.model_file_label)

        buttons = QHBoxLayout()
        self.load_model_button = QPushButton("加载模型")
        self.release_model_button = QPushButton("释放模型")
        buttons.addWidget(self.load_model_button)
        buttons.addWidget(self.release_model_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.load_model_button.clicked.connect(self._load_model)
        self.release_model_button.clicked.connect(self._release_model)
        return group

    def _build_other_group(self) -> QGroupBox:
        group = QGroupBox("Other Config")
        layout = QVBoxLayout(group)

        self.other_table = QTableWidget(10, 3)
        self.other_table.setHorizontalHeaderLabels(["序号", "参数名称", "参数值"])
        header = self.other_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.other_table.setColumnWidth(0, 48)
        self.other_table.verticalHeader().setVisible(False)
        layout.addWidget(self.other_table, 1)
        return group

    @staticmethod
    def _wrap_with_border(widget: QWidget) -> QFrame:
        container = QFrame()
        container.setFrameShape(QFrame.Shape.NoFrame)
        container.setStyleSheet(
            "QFrame { border: 1px solid #3c3c3c; border-radius: 4px; padding: 2px 6px; background: #252526; }"
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        return container

    def _load_values(self) -> None:
        detection = self._detection
        self.confidence_spin.setValue(float(detection.get("confidence", 0.5)))
        self.detection_count_spin.setValue(int(detection.get("detection_count", 20)))
        self.spare_edit_1.setText(str(detection.get("spare_1", "")))
        self.spare_edit_2.setText(str(detection.get("spare_2", "")))
        self.spare_edit_3.setText(str(detection.get("spare_3", "")))
        self.enable_check_1.setChecked(bool(detection.get("enable_1", False)))
        self.enable_check_2.setChecked(bool(detection.get("enable_2", False)))
        self.enable_check_3.setChecked(bool(detection.get("enable_3", False)))
        self.enable_check_4.setChecked(bool(detection.get("enable_4", False)))
        self.enable_check_5.setChecked(bool(detection.get("enable_5", False)))
        self.function_combo_1.setCurrentText(str(detection.get("function_1", "功能1")))
        self.function_combo_2.setCurrentText(str(detection.get("function_2", "功能2")))
        self.function_combo_3.setCurrentText(str(detection.get("function_3", "功能3")))
        self.function_combo_4.setCurrentText(str(detection.get("function_4", "功能4")))
        self.function_combo_5.setCurrentText(str(detection.get("function_5", "功能5")))
        self._populate_other_params(self._other_params)

    def _populate_other_params(self, params: list[dict]) -> None:
        self.other_table.setRowCount(10)
        self.other_table.setColumnCount(3)
        for row in range(10):
            name = ""
            value = ""
            if row < len(params):
                entry = params[row]
                if isinstance(entry, dict):
                    name = str(entry.get("name", ""))
                    value = str(entry.get("value", ""))
            seq_item = QTableWidgetItem(str(row + 1))
            seq_item.setFlags(seq_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            seq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.other_table.setItem(row, 0, seq_item)
            self.other_table.setItem(row, 1, QTableWidgetItem(name))
            self.other_table.setItem(row, 2, QTableWidgetItem(value))

    def _collect_other_params(self) -> list[dict]:
        params: list[dict] = []
        for row in range(self.other_table.rowCount()):
            name_item = self.other_table.item(row, 1)
            value_item = self.other_table.item(row, 2)
            name = name_item.text().strip() if name_item else ""
            value = value_item.text().strip() if value_item else ""
            if name:
                params.append({"name": name, "value": value})
        return params

    def _load_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "加载模型",
            "",
            "模型文件 (*.pt *.pth *.onnx *.engine *.bin);;所有文件 (*.*)",
        )
        if not file_path:
            return
        self._model_file = file_path
        self.model_file_label.setText(f"模型文件：{file_path}")

    def _release_model(self) -> None:
        self._model_file = ""
        self.model_file_label.setText("模型文件：未加载")

    def _accept(self) -> None:
        self._detection = {
            "confidence": self.confidence_spin.value(),
            "detection_count": self.detection_count_spin.value(),
            "spare_1": self.spare_edit_1.text().strip(),
            "spare_2": self.spare_edit_2.text().strip(),
            "spare_3": self.spare_edit_3.text().strip(),
            "enable_1": self.enable_check_1.isChecked(),
            "enable_2": self.enable_check_2.isChecked(),
            "enable_3": self.enable_check_3.isChecked(),
            "enable_4": self.enable_check_4.isChecked(),
            "enable_5": self.enable_check_5.isChecked(),
            "function_1": self.function_combo_1.currentText(),
            "function_2": self.function_combo_2.currentText(),
            "function_3": self.function_combo_3.currentText(),
            "function_4": self.function_combo_4.currentText(),
            "function_5": self.function_combo_5.currentText(),
        }
        self._other_params = self._collect_other_params()
        self.accept()

    def data(self) -> dict:
        return {
            "model_file": self._model_file,
            "detection": self._detection,
            "other_params": self._other_params,
        }
