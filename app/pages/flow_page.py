from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.pages.base_page import BasePage
    from app.services.config_service import ConfigService
    from app.widgets import RoiCanvas, RoiEditorDialog, TemplateParamsDialog
else:
    from .base_page import BasePage
    from ..services.config_service import ConfigService
    from ..widgets import RoiCanvas, RoiEditorDialog, TemplateParamsDialog


def _default_template(name: str) -> dict:
    """生成新模板的默认数据。"""
    return {
        "name": name,
        "model_file": "",
        "rois": [
            {"name": "ROI-1", "shape": "rect", "cx": 150, "cy": 120, "w": 200, "h": 150, "angle": 0},
            {"name": "ROI-2", "shape": "rect", "cx": 440, "cy": 170, "w": 220, "h": 160, "angle": 0},
        ],
        "detection": {
            "confidence": 0.5,
            "detection_count": 20,
            "spare_1": "",
            "spare_2": "",
            "spare_3": "",
            "enable_1": False,
            "enable_2": False,
            "enable_3": False,
            "enable_4": False,
            "enable_5": False,
            "function_1": "功能1",
            "function_2": "功能2",
            "function_3": "功能3",
            "function_4": "功能4",
            "function_5": "功能5",
        },
        "other_params": [],
    }


class FlowPage(BasePage):
    """模板编辑页。

    左侧为产品模板管理，右侧 ROI Config 占满剩余区域；
    Detection Config、Model Config、Other Config 通过“编辑参数”弹窗编辑。
    """

    template_list_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "模板编辑",
            "创建产品模板，配置 ROI 和参数。",
            parent,
        )
        self.config_service = ConfigService()
        self.templates: dict[str, dict] = {}
        self.current_template_name = ""
        self._build_ui()
        self._load_template_list()

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)

        self.template_panel = self._build_template_panel()
        self.template_panel.setMinimumWidth(300)
        splitter.addWidget(self.template_panel)
        splitter.addWidget(self._build_roi_group())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 900])
        self.add_to_content(splitter, stretch=1)

    def _build_template_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        switch_group = QGroupBox("模板名称")
        switch_layout = QHBoxLayout(switch_group)
        self.template_combo = QComboBox()
        switch_layout.addWidget(self.template_combo, 1)
        layout.addWidget(switch_group)

        template_group = QGroupBox("产品模板")
        template_layout = QVBoxLayout(template_group)
        self.template_list = QListWidget()
        self.template_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        template_layout.addWidget(self.template_list, 1)

        button_row = QHBoxLayout()
        self.new_template_button = QPushButton("新建模板")
        self.copy_template_button = QPushButton("复制模板")
        self.delete_template_button = QPushButton("删除模板")
        button_row.addWidget(self.new_template_button)
        button_row.addWidget(self.copy_template_button)
        button_row.addWidget(self.delete_template_button)
        template_layout.addLayout(button_row)

        self.save_template_button = QPushButton("保存当前模板")
        template_layout.addWidget(self.save_template_button)
        layout.addWidget(template_group, 1)

        self.template_combo.currentTextChanged.connect(self._on_template_combo_changed)
        self.new_template_button.clicked.connect(self._new_template)
        self.copy_template_button.clicked.connect(self._copy_template)
        self.delete_template_button.clicked.connect(self._delete_template)
        self.save_template_button.clicked.connect(self._save_current_template)
        return container

    def _build_roi_group(self) -> QGroupBox:
        group = QGroupBox("ROI Config")
        layout = QVBoxLayout(group)

        self.roi_canvas = RoiCanvas()
        layout.addWidget(self.roi_canvas, 1)

        button_row = QHBoxLayout()
        self.edit_roi_button = QPushButton("编辑 ROI")
        self.edit_params_button = QPushButton("编辑参数")
        self.crosshair_check = QCheckBox("显示十字线")
        self.crosshair_check.setChecked(True)
        button_row.addWidget(self.edit_roi_button)
        button_row.addWidget(self.edit_params_button)
        button_row.addWidget(self.crosshair_check)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.edit_roi_button.clicked.connect(self._open_roi_editor)
        self.edit_params_button.clicked.connect(self._open_params_dialog)
        self.crosshair_check.toggled.connect(self.roi_canvas.set_crosshair_visible)
        return group

    def _load_template_list(self) -> None:
        if not self.config_service.list_templates():
            self._create_template("默认产品A")
        self._refresh_template_list()

    def _refresh_template_list(self, select_name: str | None = None) -> None:
        names = self.config_service.list_templates()
        self.template_list_changed.emit()

        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItems(names)
        self.template_combo.blockSignals(False)

        self.template_list.clear()
        for name in names:
            self.config_service.ensure_template_dirs(name)
            self.template_list.addItem(QListWidgetItem(name))

        if select_name and select_name in names:
            self._set_current_template(select_name)
        elif names:
            self._set_current_template(names[0])

    def _set_current_template(self, name: str) -> None:
        self.template_combo.blockSignals(True)
        self.template_combo.setCurrentText(name)
        self.template_combo.blockSignals(False)
        self._sync_list_selection(name)
        self._load_template(name)

    def _sync_list_selection(self, name: str) -> None:
        items = self.template_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.template_list.blockSignals(True)
            self.template_list.setCurrentItem(items[0])
            self.template_list.blockSignals(False)

    def _on_template_combo_changed(self, name: str) -> None:
        if not name:
            return
        self._sync_list_selection(name)
        self._load_template(name)

    def _load_template(self, name: str) -> None:
        data = self.config_service.load_template(name)
        if not data:
            data = _default_template(name)
        self.templates[name] = data
        self.current_template_name = name
        self.roi_canvas.set_rois(deepcopy(data.get("rois", [])))
        self.set_result(f"检测结果：模板「{name}」已加载")
        self.set_tip("操作提示：ROI 在当前页面编辑，其他参数通过“编辑参数”弹窗修改。")

    def set_roi_image(self, pixmap) -> None:
        """接收相机管理页广播的图像，用于 ROI 配置区实时显示。"""
        self.roi_canvas.set_pixmap(pixmap)

    def _new_template(self) -> None:
        name, ok = QInputDialog.getText(self, "新建模板", "请输入模板名称：")
        if not ok or not name.strip():
            return
        name = name.strip()
        self._save_current_template()
        if self._create_template(name):
            self._refresh_template_list(name)

    def _create_template(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        if name in self.config_service.list_templates():
            QMessageBox.warning(self, "提示", "模板名称已存在。")
            return False
        self._persist_template(name, _default_template(name))
        return True

    def _copy_template(self) -> None:
        current = self.template_list.currentItem()
        if current is None:
            QMessageBox.information(self, "提示", "请先在列表中选择要复制的模板。")
            return
        source = current.text()
        target, ok = QInputDialog.getText(self, "复制模板", "请输入复制后的模板名称：")
        if not ok or not target.strip():
            return
        target = target.strip()
        if target in self.config_service.list_templates():
            QMessageBox.warning(self, "提示", "模板名称已存在。")
            return

        self._save_current_template()
        try:
            self.config_service.copy_template(source, target)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "复制失败", str(exc))
            return
        self._refresh_template_list(target)

    def _delete_template(self) -> None:
        current = self.template_list.currentItem()
        if current is None:
            QMessageBox.information(self, "提示", "请先在列表中选择要删除的模板。")
            return
        name = current.text()
        if len(self.config_service.list_templates()) <= 1:
            QMessageBox.information(self, "提示", "至少需要保留一个产品模板。")
            return

        answer = QMessageBox.question(
            self,
            "删除模板",
            f"确定删除模板「{name}」及其目录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.config_service.delete_template(name):
            self.templates.pop(name, None)
            self._refresh_template_list()
        else:
            QMessageBox.warning(self, "删除失败", "未能删除该模板目录。")

    def _save_current_template(self) -> None:
        name = self.current_template_name
        if not name:
            return
        data = self.templates.get(name, _default_template(name))
        data.update({"name": name, "rois": self.roi_canvas.get_rois()})
        self.templates[name] = data
        self._persist_template(name, data)
        self.set_tip(f"操作提示：模板「{name}」已保存到模板目录。")

    def _persist_template(self, name: str, data: dict) -> None:
        payload = {
            "name": data.get("name", name),
            "model_file": data.get("model_file", ""),
            "rois": data.get("rois", []),
            "detection": data.get("detection", {}),
            "other_params": data.get("other_params", []),
        }
        self.config_service.save_template(name, payload)
        self.config_service.ensure_template_dirs(name)
        self.config_service.save_template_category(name, "ROI Config", "roi.yaml", {"rois": payload["rois"]})
        self.config_service.save_template_category(name, "Detection Config", "detection.yaml", {"detection": payload["detection"]})
        self.config_service.save_template_category(name, "Model Config", "model.yaml", {"model_file": payload["model_file"]})
        self.config_service.save_template_category(name, "Other Config", "other.yaml", {"other_params": payload["other_params"]})

    def _open_roi_editor(self) -> None:
        dialog = RoiEditorDialog(
            self.roi_canvas.get_rois(),
            self,
            pixmap=self.roi_canvas.pixmap(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.roi_canvas.set_rois(dialog.selected_rois())
        if self.current_template_name in self.templates:
            self.templates[self.current_template_name]["rois"] = self.roi_canvas.get_rois()
        self.set_tip("操作提示：ROI 配置已更新，点击“保存当前模板”可写入模板目录。")

    def _open_params_dialog(self) -> None:
        name = self.current_template_name
        if not name:
            self.set_tip("操作提示：请先选择模板。")
            return
        data = self.templates.get(name, _default_template(name))
        dialog = TemplateParamsDialog(
            data.get("model_file", ""),
            data.get("detection", {}),
            data.get("other_params", []),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.data()
        data["model_file"] = result["model_file"]
        data["detection"] = result["detection"]
        data["other_params"] = result["other_params"]
        self.templates[name] = data
        self._persist_template(name, data)
        self.set_tip("操作提示：参数已更新并保存到当前模板目录。")

    def auto_save_config(self) -> None:
        self._save_current_template()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.standalone import run_page

    raise SystemExit(run_page(sys.modules[__name__].FlowPage))
