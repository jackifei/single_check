"""模板参数编辑弹窗：只保留“检测参数”表格。

按需求：
- 取消 Model Config 模块；
- 取消 Detection Config 模块；
- 原 Other Config 改名为“检测参数”，表格 20 行（序号 / 参数名称 / 参数值）。

model_file 与 detection 仍原样透传，保证模板里的既有字段不会被清空。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TemplateParamsDialog(QDialog):
    """检测参数编辑弹窗（20 行参数表）。"""

    ROW_COUNT = 20

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
        root.addWidget(self._build_other_group(), 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        buttons.addWidget(self.ok_button)
        buttons.addWidget(self.cancel_button)
        root.addLayout(buttons)

        self.ok_button.clicked.connect(self._accept)
        self.cancel_button.clicked.connect(self.reject)

    def _build_other_group(self) -> QGroupBox:
        """“检测参数”表格：20 行（序号 / 参数名称 / 参数值）。"""
        group = QGroupBox("检测参数")
        layout = QVBoxLayout(group)

        self.other_table = QTableWidget(self.ROW_COUNT, 3)
        self.other_table.setHorizontalHeaderLabels(["序号", "参数名称", "参数值"])
        header = self.other_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.other_table.setColumnWidth(0, 48)
        self.other_table.verticalHeader().setVisible(False)
        layout.addWidget(self.other_table, 1)
        return group

    def _load_values(self) -> None:
        self._populate_other_params(self._other_params)

    def _populate_other_params(self, params: list[dict]) -> None:
        self.other_table.setRowCount(self.ROW_COUNT)
        self.other_table.setColumnCount(3)
        for row in range(self.ROW_COUNT):
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

    def _accept(self) -> None:
        self._other_params = self._collect_other_params()
        self.accept()

    def data(self) -> dict:
        return {
            "model_file": self._model_file,
            "detection": self._detection,
            "other_params": self._other_params,
        }
