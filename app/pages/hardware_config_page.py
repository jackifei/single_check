"""硬件配置页：ModbusRTU IO 控制（4 入 4 出）+ 自启动开关。

按需求：
- 取消原来的“串口设置”与“IO 控制（ModbusTCP）”；
- 新增“IO 控制（ModbusRTU）”：4 路输入指示灯 + 4 路输出按钮；
- 串口参数固定为 9600、8 数据位、无奇偶校验、1 停止位，界面只暴露串口号选择；
- 输入/输出样式沿用之前 ModbusTCP 模块的灯/按钮风格；
- 新增“自启动”勾选项：勾选后软件启动时自动打开相机并连接 IO 板卡。

插入点：接入真实 ModbusRTU 驱动时，在 _toggle_output 中写入线圈寄存器、
在输入刷新处读取离散输入即可。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.pages.base_page import BasePage
    from app.services.config_service import ConfigService
else:
    from .base_page import BasePage
    from ..services.config_service import ConfigService


class HardwareConfigPage(BasePage):
    """硬件配置页。"""

    # 固定串口参数（需求：默认 9600, 8 位, 无奇偶校验, 停止位 1）。
    SERIAL_BAUD = 9600
    SERIAL_DATA_BITS = 8
    SERIAL_PARITY = "无"
    SERIAL_STOP_BITS = 1

    IO_COUNT = 4
    PORT_NAMES = ("COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8")

    # IO 信号默认定义（需求）。
    IO_MAP = {
        "inputs": [
            {"name": "IN01", "function": "相机1 触发", "edge": "上升沿"},
            {"name": "IN02", "function": "相机2 触发", "edge": "上升沿"},
            {"name": "IN03", "function": "备用", "edge": "-"},
            {"name": "IN04", "function": "备用", "edge": "-"},
        ],
        "outputs": [
            {"name": "OUT01", "function": "相机1 OK", "pulse_ms": 1000},
            {"name": "OUT02", "function": "相机1 NG", "pulse_ms": 1000},
            {"name": "OUT03", "function": "相机2 OK", "pulse_ms": 1000},
            {"name": "OUT04", "function": "相机2 NG", "pulse_ms": 1000},
        ],
    }

    # 检测结果 -> 输出通道（0 起）：相机1 OK=OUT01，NG=OUT02；相机2 OK=OUT03，NG=OUT04。
    RESULT_OUTPUT = {(1, True): 0, (1, False): 1, (2, True): 2, (2, False): 3}
    # 触发输入（0 起）：IN01=相机1，IN02=相机2。
    TRIGGER_INPUT = {1: 0, 2: 1}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "硬件配置",
            "ModbusRTU 控制 4 路输入与 4 路输出。",
            parent,
        )
        self.config_service = ConfigService()
        self.input_indicators: list[QLabel] = []
        self.output_buttons: list[QPushButton] = []
        self.io_connected = False
        self._build_ui()
        self._load_config()
        self.set_result("检测结果：IO 板卡未连接")

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        layout.addWidget(self._build_io_group())

        self.auto_start_check = QCheckBox("自启动：软件启动后自动打开相机并连接 IO 板卡")
        layout.addWidget(self.auto_start_check)

        save_row = QHBoxLayout()
        self.save_button = QPushButton("保存硬件配置")
        save_row.addWidget(self.save_button)
        save_row.addStretch(1)
        layout.addLayout(save_row)
        self.save_button.clicked.connect(self._save_config)

        layout.addStretch(1)
        scroll.setWidget(container)
        self.add_to_content(scroll, stretch=1)

    def _build_io_group(self) -> QGroupBox:
        """ModbusRTU 串口行 + 4 入 4 出。"""
        group = QGroupBox("IO 控制（ModbusRTU）")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel("串口"))
        self.port_combo = QComboBox()
        self.port_combo.addItems(self.PORT_NAMES)
        row.addWidget(self.port_combo)
        self.connect_button = QPushButton("连接串口")
        self.connect_button.setCheckable(True)
        row.addWidget(self.connect_button)
        hint = QLabel("9600,8,N,1（固定）")
        hint.setObjectName("pageTip")
        row.addWidget(hint)
        row.addStretch(1)
        layout.addLayout(row)

        io_columns = QHBoxLayout()
        input_group = self._build_input_group()
        output_group = self._build_output_group()
        input_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        output_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        io_columns.addWidget(input_group)
        io_columns.addWidget(output_group)
        io_columns.addStretch(1)
        io_columns.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addLayout(io_columns)

        self.connect_button.clicked.connect(self._toggle_io)
        self._set_output_buttons_enabled(False)
        return group

    def _build_input_group(self) -> QGroupBox:
        """4 路输入指示灯 + 默认功能说明。"""
        group = QGroupBox("输入状态（4 路）")
        grid = QGridLayout(group)
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)
        for index in range(self.IO_COUNT):
            item = self.IO_MAP["inputs"][index]
            indicator = QLabel("●")
            indicator.setObjectName("ioIndicator")
            indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            indicator.setFixedSize(28, 28)
            self._apply_indicator_state(indicator, False)
            name = QLabel(item["name"])
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edge = item["edge"] if item["edge"] != "-" else ""
            function = QLabel(item["function"] + (f"（{edge}）" if edge else ""))
            function.setObjectName("pageTip")
            function.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(indicator, 0, index)
            grid.addWidget(name, 1, index)
            grid.addWidget(function, 2, index)
            self.input_indicators.append(indicator)
        return group

    def _build_output_group(self) -> QGroupBox:
        """4 路输出按钮 + 默认功能与脉冲时长说明。"""
        group = QGroupBox("输出控制（4 路）")
        grid = QGridLayout(group)
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)
        for index in range(self.IO_COUNT):
            item = self.IO_MAP["outputs"][index]
            button = QPushButton(item["name"])
            button.setCheckable(True)
            button.setMinimumHeight(36)
            function = QLabel(f"{item['function']} · {item['pulse_ms'] // 1000}s 脉冲")
            function.setObjectName("pageTip")
            function.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(button, 0, index)
            grid.addWidget(function, 1, index)
            button.clicked.connect(lambda checked, i=index: self._toggle_output(i, checked))
            self.output_buttons.append(button)
        return group

    # ------------------------------------------------------------------
    # 连接 / 输出
    # ------------------------------------------------------------------
    def _toggle_io(self, checked: bool) -> None:
        """连接 / 断开 ModbusRTU 串口。"""
        self.io_connected = checked
        self.connect_button.setText("断开串口" if checked else "连接串口")
        self.set_result(
            f"检测结果：IO 板卡（ModbusRTU）{'已连接' if checked else '未连接'}"
            f"（串口 {self.port_combo.currentText()}）"
        )
        self._set_output_buttons_enabled(checked)

    def _set_output_buttons_enabled(self, enabled: bool) -> None:
        for button in self.output_buttons:
            button.setEnabled(enabled)

    def _toggle_output(self, index: int, checked: bool) -> None:
        # 插入点：在此处写入 ModbusRTU 线圈寄存器。
        name = self.IO_MAP["outputs"][index]["name"]
        self.set_tip(f"操作提示：输出 {name} 已{'置位' if checked else '复位'}")

    def output_for_result(self, camera_index: int, ok: bool) -> int:
        """返回某相机检测结果对应的输出通道（0 起）。"""
        return self.RESULT_OUTPUT[(camera_index, ok)]

    def pulse_output(self, index: int, duration_ms: int | None = None) -> None:
        """对某路输出发一个脉冲（默认按 IO_MAP 定义，均为 1 秒）。

        供检测流程在判定结果后调用：相机1 OK->OUT01、NG->OUT02，
        相机2 OK->OUT03、NG->OUT04。
        """
        if not (0 <= index < len(self.output_buttons)):
            return
        default_ms = int(self.IO_MAP["outputs"][index].get("pulse_ms", 1000))
        duration = duration_ms if duration_ms is not None else default_ms
        self.output_buttons[index].setChecked(True)
        # 插入点：写入 ModbusRTU 线圈 = 1
        QTimer.singleShot(duration, lambda: self._end_pulse(index))

    def _end_pulse(self, index: int) -> None:
        """脉冲结束：复位输出。"""
        if 0 <= index < len(self.output_buttons):
            self.output_buttons[index].setChecked(False)
        # 插入点：写入 ModbusRTU 线圈 = 0

    def on_trigger_input(self, camera_index: int) -> None:
        """触发输入（IN01/IN02，上升沿有效）回调：触发对应相机拍照并检测。

        插入点：由 ModbusRTU 输入扫描检测到上升沿时调用，后续在此触发
        相机拍照与检测流程。
        """
        self.set_tip(
            f"操作提示：收到相机 {camera_index} 触发信号（上升沿），可在此触发拍照检测。"
        )

    def auto_connect_io(self) -> None:
        """自启动调用：按保存的串口连接 IO 板卡。"""
        if self.io_connected:
            return
        self.connect_button.setChecked(True)
        self._toggle_io(True)

    # ------------------------------------------------------------------
    # 配置读写
    # ------------------------------------------------------------------
    def _save_config(self) -> None:
        self.config_service.save_page_config(
            "hardware",
            {
                "modbus_type": "rtu",
                "serial_port": self.port_combo.currentText(),
                "auto_start": self.auto_start_check.isChecked(),
                "io_map": self.IO_MAP,
            },
        )
        self.set_tip("操作提示：硬件配置已保存到 config/hardware.yaml。")

    def _load_config(self) -> None:
        data = self.config_service.load_page_config("hardware")
        if not data:
            return
        self.port_combo.setCurrentText(
            str(data.get("serial_port", self.port_combo.currentText()))
        )
        self.auto_start_check.setChecked(bool(data.get("auto_start", False)))

    def auto_save_config(self) -> None:
        self._save_config()

    @staticmethod
    def _apply_indicator_state(indicator: QLabel, on: bool) -> None:
        color = "#4ec9b0" if on else "#444444"
        indicator.setStyleSheet(
            f"background-color: {color}; border: 1px solid #666666; border-radius: 14px;"
        )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.standalone import run_page

    raise SystemExit(run_page(sys.modules[__name__].HardwareConfigPage))
