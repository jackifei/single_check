from __future__ import annotations

import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.config_service import ConfigService


def _solve_3x3(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            continue
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]
        for j in range(col, 4):
            a[col][j] /= divisor
        for row in range(3):
            if row == col:
                continue
            factor = a[row][col]
            for j in range(col, 4):
                a[row][j] -= factor * a[col][j]
    return [a[i][3] for i in range(3)]


def _fit_affine_2d(points: list[tuple[float, float, float, float]]) -> tuple[list[float], float]:
    matrix_x = [[0.0] * 3 for _ in range(3)]
    matrix_y = [[0.0] * 3 for _ in range(3)]
    rhs_x = [0.0, 0.0, 0.0]
    rhs_y = [0.0, 0.0, 0.0]

    for u, v, x, y in points:
        row = [u, v, 1.0]
        for i in range(3):
            for j in range(3):
                matrix_x[i][j] += row[i] * row[j]
                matrix_y[i][j] += row[i] * row[j]
            rhs_x[i] += row[i] * x
            rhs_y[i] += row[i] * y

    coeff_x = _solve_3x3(matrix_x, rhs_x)
    coeff_y = _solve_3x3(matrix_y, rhs_y)

    error_sum = 0.0
    for u, v, x, y in points:
        pred_x = coeff_x[0] * u + coeff_x[1] * v + coeff_x[2]
        pred_y = coeff_y[0] * u + coeff_y[1] * v + coeff_y[2]
        error_sum += (pred_x - x) ** 2 + (pred_y - y) ** 2
    rms = math.sqrt(error_sum / len(points)) if points else 0.0
    return coeff_x + coeff_y, rms


class CalibrationPanel(QWidget):
    """相机页内嵌的标定面板。

    显示内参标定和 9 点标定状态，并通过二级下拉切换具体标定子界面；
    9 点标定支持从图像区域点击拾取像素坐标。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config_service = ConfigService()
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        status_group = QGroupBox("标定状态")
        status_layout = QHBoxLayout(status_group)
        self.intrinsic_status_label = QLabel("内参标定：未标定")
        self.point_status_label = QLabel("9点标定：未标定")
        status_layout.addWidget(self.intrinsic_status_label)
        status_layout.addWidget(self.point_status_label)
        status_layout.addStretch(1)
        layout.addWidget(status_group)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("标定类型"))
        self.calib_type_combo = QComboBox()
        self.calib_type_combo.addItem("无选择", "none")
        self.calib_type_combo.addItem("内参标定", "intrinsic")
        self.calib_type_combo.addItem("9点标定", "point")
        type_row.addWidget(self.calib_type_combo)
        type_row.addStretch(1)
        layout.addLayout(type_row)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_placeholder_page())
        self.stack.addWidget(self._build_intrinsic_panel())
        self.stack.addWidget(self._build_point_panel())
        layout.addWidget(self.stack, 1)

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.calib_type_combo.currentIndexChanged.connect(self._on_type_changed)

    def _build_placeholder_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel("请选择标定类型。")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return page

    def _build_intrinsic_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        board_group = QGroupBox("标定板设置")
        board_layout = QHBoxLayout(board_group)
        board_layout.addWidget(QLabel("列数"))
        self.board_cols_spin = QSpinBox()
        self.board_cols_spin.setRange(3, 50)
        self.board_cols_spin.setValue(9)
        board_layout.addWidget(self.board_cols_spin)
        board_layout.addWidget(QLabel("行数"))
        self.board_rows_spin = QSpinBox()
        self.board_rows_spin.setRange(3, 50)
        self.board_rows_spin.setValue(6)
        board_layout.addWidget(self.board_rows_spin)
        board_layout.addWidget(QLabel("尺寸(mm)"))
        self.square_size_spin = QDoubleSpinBox()
        self.square_size_spin.setRange(0.1, 1000.0)
        self.square_size_spin.setDecimals(3)
        self.square_size_spin.setValue(25.0)
        board_layout.addWidget(self.square_size_spin)
        board_layout.addStretch(1)
        layout.addWidget(board_group)

        image_group = QGroupBox("标定图像")
        image_layout = QVBoxLayout(image_group)
        self.image_list = QListWidget()
        self.image_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        image_layout.addWidget(self.image_list, 1)

        image_buttons = QHBoxLayout()
        self.add_image_button = QPushButton("添加图像")
        self.capture_calib_image_button = QPushButton("采集当前帧")
        self.delete_image_button = QPushButton("删除选中")
        self.clear_image_button = QPushButton("清空")
        image_buttons.addWidget(self.add_image_button)
        image_buttons.addWidget(self.capture_calib_image_button)
        image_buttons.addWidget(self.delete_image_button)
        image_buttons.addWidget(self.clear_image_button)
        image_buttons.addStretch(1)
        image_layout.addLayout(image_buttons)

        result_group = QGroupBox("内参标定结果")
        result_layout = QVBoxLayout(result_group)
        self.intrinsic_result_edit = QPlainTextEdit()
        self.intrinsic_result_edit.setReadOnly(True)
        self.intrinsic_result_edit.setPlaceholderText("标定结果将在此显示。")
        result_layout.addWidget(self.intrinsic_result_edit, 1)
        self.start_intrinsic_button = QPushButton("开始标定")
        result_layout.addWidget(self.start_intrinsic_button)

        intrinsic_splitter = QSplitter(Qt.Orientation.Vertical)
        intrinsic_splitter.setChildrenCollapsible(False)
        intrinsic_splitter.setHandleWidth(5)
        intrinsic_splitter.addWidget(image_group)
        intrinsic_splitter.addWidget(result_group)
        intrinsic_splitter.setStretchFactor(0, 1)
        intrinsic_splitter.setStretchFactor(1, 1)
        layout.addWidget(intrinsic_splitter, 1)

        self.add_image_button.clicked.connect(self._add_calib_images)
        self.capture_calib_image_button.clicked.connect(self._capture_calib_image)
        self.delete_image_button.clicked.connect(self._delete_selected_images)
        self.clear_image_button.clicked.connect(self._clear_images)
        self.start_intrinsic_button.clicked.connect(self._run_intrinsic_calibration)
        return panel

    def _build_point_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        mode_group = QGroupBox("手眼关系")
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.addWidget(QLabel("手眼模式"))
        self.hand_eye_mode_combo = QComboBox()
        self.hand_eye_mode_combo.addItem("眼在手上", "eye_in_hand")
        self.hand_eye_mode_combo.addItem("眼在手外", "eye_to_hand")
        mode_layout.addWidget(self.hand_eye_mode_combo)
        mode_layout.addStretch(1)
        layout.addWidget(mode_group)

        point_group = QGroupBox("9 点数据")
        point_layout = QVBoxLayout(point_group)
        self.point_table = QTableWidget(9, 5)
        self.point_table.setHorizontalHeaderLabels(["序号", "机器人X", "机器人Y", "像素U", "像素V"])
        header = self.point_table.horizontalHeader()
        for col in range(5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self.point_table.verticalHeader().setVisible(False)
        self.point_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for row in range(9):
            seq_item = QTableWidgetItem(str(row + 1))
            seq_item.setFlags(seq_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            seq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.point_table.setItem(row, 0, seq_item)
            for col in range(1, 5):
                self.point_table.setItem(row, col, QTableWidgetItem(""))
        point_layout.addWidget(self.point_table, 1)

        point_buttons = QHBoxLayout()
        self.capture_point_button = QPushButton("采集当前点")
        self.compute_points_button = QPushButton("计算标定")
        self.save_calib_button = QPushButton("保存标定")
        self.load_calib_button = QPushButton("加载标定")
        point_buttons.addWidget(self.capture_point_button)
        point_buttons.addWidget(self.compute_points_button)
        point_buttons.addWidget(self.save_calib_button)
        point_buttons.addWidget(self.load_calib_button)
        point_buttons.addStretch(1)
        point_layout.addLayout(point_buttons)

        result_group = QGroupBox("9 点标定结果")
        result_group.setMaximumHeight(280)
        result_layout = QVBoxLayout(result_group)
        self.matrix_table = QTableWidget(2, 3)
        self.matrix_table.setHorizontalHeaderLabels(["u", "v", "1"])
        self.matrix_table.setVerticalHeaderLabels(["X", "Y"])
        header = self.matrix_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.matrix_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.matrix_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.matrix_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for row in range(2):
            for col in range(3):
                item = QTableWidgetItem("--")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.matrix_table.setItem(row, col, item)
        result_layout.addWidget(self.matrix_table)

        self.point_result_edit = QPlainTextEdit()
        self.point_result_edit.setReadOnly(True)
        self.point_result_edit.setPlaceholderText("标定结果将在此显示。")
        result_layout.addWidget(self.point_result_edit, 1)

        point_splitter = QSplitter(Qt.Orientation.Vertical)
        point_splitter.setChildrenCollapsible(False)
        point_splitter.setHandleWidth(5)
        point_splitter.addWidget(point_group)
        point_splitter.addWidget(result_group)
        point_splitter.setStretchFactor(0, 3)
        point_splitter.setStretchFactor(1, 1)
        point_splitter.setSizes([560, 260])
        layout.addWidget(point_splitter, 1)

        self.capture_point_button.clicked.connect(self._capture_point)
        self.compute_points_button.clicked.connect(self._compute_points)
        self.save_calib_button.clicked.connect(self._save_calib_config)
        self.load_calib_button.clicked.connect(self._load_config)
        return panel

    def _on_type_changed(self, index: int) -> None:
        data = self.calib_type_combo.currentData()
        if data == "intrinsic":
            self.stack.setCurrentIndex(1)
        elif data == "point":
            self.stack.setCurrentIndex(2)
        else:
            self.stack.setCurrentIndex(0)

    def handle_image_point(self, x: float, y: float) -> None:
        if self.calib_type_combo.currentData() != "point":
            return
        row = self.point_table.currentRow()
        if row < 0:
            return
        self.point_table.setItem(row, 3, QTableWidgetItem(f"{x:.1f}"))
        self.point_table.setItem(row, 4, QTableWidgetItem(f"{y:.1f}"))

    def _add_calib_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择标定图像",
            "",
            "图像文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*.*)",
        )
        for file_path in files:
            item = QListWidgetItem(file_path)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.image_list.addItem(item)

    def _capture_calib_image(self) -> None:
        # 插入点：接入相机后，把当前帧保存为标定图像并加入列表。
        pass

    def _delete_selected_images(self) -> None:
        for item in self.image_list.selectedItems():
            self.image_list.takeItem(self.image_list.row(item))

    def _clear_images(self) -> None:
        self.image_list.clear()

    def _run_intrinsic_calibration(self) -> None:
        paths = [
            self.image_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.image_list.count())
        ]
        if not paths:
            QMessageBox.information(self, "提示", "请先添加标定图像。")
            return
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            self.intrinsic_result_edit.setPlainText(f"缺少标定依赖：{exc}")
            return

        cols = self.board_cols_spin.value()
        rows = self.board_rows_spin.value()
        size = self.square_size_spin.value()
        object_points = np.zeros((rows * cols, 3), np.float32)
        object_points[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * size

        obj_points: list = []
        img_points: list = []
        image_size = None
        for path in paths:
            image = cv2.imread(path)
            if image is None:
                continue
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            image_size = gray.shape[::-1]
            found, corners = cv2.findChessboardCorners(gray, (cols, rows), None)
            if not found:
                continue
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            obj_points.append(object_points)
            img_points.append(corners)

        if not obj_points or image_size is None:
            self.intrinsic_result_edit.setPlainText("未检测到棋盘格角点，请检查棋盘格行列数或图像。")
            return

        ret, matrix, dist, rvecs, tvecs = cv2.calibrateCamera(
            obj_points, img_points, image_size, None, None
        )
        error_sum = 0.0
        total_points = 0
        for index, _ in enumerate(obj_points):
            projected, _ = cv2.projectPoints(obj_points[index], rvecs[index], tvecs[index], matrix, dist)
            error = cv2.norm(img_points[index], projected, cv2.NORM_L2) / len(projected)
            error_sum += error * error
            total_points += 1
        rms = math.sqrt(error_sum / total_points) if total_points else 0.0

        self.intrinsic_result_edit.setPlainText(
            f"标定完成\nRMS 重投影误差：{rms:.4f}\n\n"
            f"内参矩阵：\n{matrix}\n\n畸变系数：\n{dist.ravel()}"
        )
        self.intrinsic_status_label.setText("内参标定：已标定")

    def _capture_point(self) -> None:
        row = self.point_table.currentRow()
        if row < 0:
            row = 0
        self.point_table.setCurrentCell(row, 1)

    def _compute_points(self) -> None:
        points: list[tuple[float, float, float, float]] = []
        for row in range(self.point_table.rowCount()):
            robot_x = self.point_table.item(row, 1)
            robot_y = self.point_table.item(row, 2)
            pixel_u = self.point_table.item(row, 3)
            pixel_v = self.point_table.item(row, 4)
            if not robot_x or not robot_y or not pixel_u or not pixel_v:
                QMessageBox.warning(self, "提示", f"第 {row + 1} 点数据不完整。")
                return
            if not (robot_x.text().strip() and robot_y.text().strip() and pixel_u.text().strip() and pixel_v.text().strip()):
                QMessageBox.warning(self, "提示", f"第 {row + 1} 点数据不完整。")
                return
            try:
                x = float(robot_x.text())
                y = float(robot_y.text())
                u = float(pixel_u.text())
                v = float(pixel_v.text())
            except ValueError:
                QMessageBox.warning(self, "提示", "请填写有效数值。")
                return
            points.append((u, v, x, y))

        coeff, rms = _fit_affine_2d(points)
        mode = self.hand_eye_mode_combo.currentText()
        matrix_values = [
            [coeff[0], coeff[1], coeff[2]],
            [coeff[3], coeff[4], coeff[5]],
        ]
        for row in range(2):
            for col in range(3):
                self.matrix_table.item(row, col).setText(f"{matrix_values[row][col]:.6f}")
        self.point_result_edit.setPlainText(
            f"手眼模式：{mode}\n拟合 RMS：{rms:.4f}\n\n"
            f"仿射系数（u, v -> X）：\n"
            f"a={coeff[0]:.6f}, b={coeff[1]:.6f}, c={coeff[2]:.6f}\n\n"
            f"仿射系数（u, v -> Y）：\n"
            f"d={coeff[3]:.6f}, e={coeff[4]:.6f}, f={coeff[5]:.6f}"
        )
        self.point_status_label.setText("9点标定：已标定")

    def _save_calib_config(self) -> None:
        self.config_service.save_page_config(
            "calibration",
            {
                "hand_eye_mode": self.hand_eye_mode_combo.currentData(),
                "board_cols": self.board_cols_spin.value(),
                "board_rows": self.board_rows_spin.value(),
                "square_size": self.square_size_spin.value(),
                "points": self._collect_point_table_data(),
                "point_result": self.point_result_edit.toPlainText(),
                "intrinsic_result": self.intrinsic_result_edit.toPlainText(),
            },
        )

    def _load_config(self) -> None:
        data = self.config_service.load_page_config("calibration")
        if not data:
            return
        self.hand_eye_mode_combo.setCurrentIndex(
            self.hand_eye_mode_combo.findData(data.get("hand_eye_mode", "eye_in_hand"))
        )
        self.board_cols_spin.setValue(int(data.get("board_cols", self.board_cols_spin.value())))
        self.board_rows_spin.setValue(int(data.get("board_rows", self.board_rows_spin.value())))
        self.square_size_spin.setValue(float(data.get("square_size", self.square_size_spin.value())))
        self._apply_point_table_data(data.get("points", []))
        self.point_result_edit.setPlainText(str(data.get("point_result", "")))
        self.intrinsic_result_edit.setPlainText(str(data.get("intrinsic_result", "")))

    def _collect_point_table_data(self) -> list[dict]:
        points: list[dict] = []
        for row in range(self.point_table.rowCount()):
            points.append(
                {
                    "x": self.point_table.item(row, 1).text() if self.point_table.item(row, 1) else "",
                    "y": self.point_table.item(row, 2).text() if self.point_table.item(row, 2) else "",
                    "u": self.point_table.item(row, 3).text() if self.point_table.item(row, 3) else "",
                    "v": self.point_table.item(row, 4).text() if self.point_table.item(row, 4) else "",
                }
            )
        return points

    def _apply_point_table_data(self, points: list[dict]) -> None:
        for row in range(self.point_table.rowCount()):
            point = points[row] if row < len(points) else {}
            values = [
                str(point.get("x", "")),
                str(point.get("y", "")),
                str(point.get("u", "")),
                str(point.get("v", "")),
            ]
            for col, value in enumerate(values, start=1):
                self.point_table.setItem(row, col, QTableWidgetItem(value))
