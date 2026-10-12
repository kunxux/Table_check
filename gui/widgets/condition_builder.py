"""
条件构建器
==========
Layer② 表达式编辑器的核心组件。
每一行 = [列选择 ▼] [操作符 ▼] [值输入] [AND/OR] [×删除]
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit,
    QPushButton, QScrollArea, QLabel, QToolButton,
)
from PySide6.QtCore import Qt, Signal

from gui.app import AppState


# 操作符（按列类型分组）
NUMERIC_OPS = ["==", "!=", ">", ">=", "<", "<=", "为空", "不为空"]
TEXT_OPS = ["==", "!=", "包含", "不包含", "开头是", "结尾是", "为空", "不为空", "in", "not_in"]
GENERAL_OPS = ["==", "!=", "为空", "不为空", "in", "not_in"]


class ConditionRow(QWidget):
    """一行条件"""

    removed = Signal(object)  # 通知父组件自己被删除

    def __init__(self, columns: list, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # 列选择
        self.col_combo = QComboBox()
        self.col_combo.addItems(self._columns)
        self.col_combo.setMinimumWidth(100)
        self.col_combo.currentTextChanged.connect(self._on_col_changed)
        layout.addWidget(self.col_combo)

        # 操作符
        self.op_combo = QComboBox()
        self.op_combo.setMinimumWidth(80)
        layout.addWidget(self.op_combo)

        # 值输入
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("值")
        self.value_input.setMinimumWidth(80)
        layout.addWidget(self.value_input)

        # AND / OR
        self.connector_combo = QComboBox()
        self.connector_combo.addItems(["AND", "OR"])
        self.connector_combo.setMaximumWidth(60)
        layout.addWidget(self.connector_combo)

        # 删除按钮
        btn_del = QToolButton()
        btn_del.setText("×")
        btn_del.setToolTip("删除此条件")
        btn_del.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(btn_del)

        # 初始操作符列表
        self._on_col_changed(self._columns[0] if self._columns else "")

    def _on_col_changed(self, col_name: str):
        """列变化时更新操作符列表"""
        self.op_combo.clear()

        info = None
        from PySide6.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'state'):
                info_obj = widget.state.get_current_info()
                if info_obj:
                    info = info_obj
                    break

        if info:
            for col_info in info.columns:
                if col_info.name == col_name:
                    if col_info.python_type in ("int", "float"):
                        self.op_combo.addItems(NUMERIC_OPS)
                    elif col_info.python_type == "str":
                        self.op_combo.addItems(TEXT_OPS)
                    else:
                        self.op_combo.addItems(GENERAL_OPS)
                    self._update_value_placeholder()
                    return

        self.op_combo.addItems(GENERAL_OPS)
        self._update_value_placeholder()

    def _update_value_placeholder(self):
        op = self.op_combo.currentText()
        if op in ("为空", "不为空"):
            self.value_input.setPlaceholderText("(无需输入)")
            self.value_input.setEnabled(False)
        elif op == "in":
            self.value_input.setPlaceholderText("逗号分隔: 1,2,3")
            self.value_input.setEnabled(True)
        else:
            self.value_input.setPlaceholderText("值")
            self.value_input.setEnabled(True)

    def get_condition(self) -> dict:
        return {
            "column": self.col_combo.currentText(),
            "operator": self.op_combo.currentText(),
            "value": self.value_input.text(),
            "connector": self.connector_combo.currentText(),
        }

    def update_columns(self, columns: list):
        current = self.col_combo.currentText()
        self.col_combo.clear()
        self.col_combo.addItems(columns)
        if current in columns:
            self.col_combo.setCurrentText(current)


class ConditionBuilder(QWidget):
    """条件构建器容器"""

    conditions_changed = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._rows = []
        self._init_ui()
        self.state.table_loaded.connect(self._on_table_changed)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 条件列表滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_container = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_container)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.scroll_container)
        layout.addWidget(self.scroll, 1)

        # 添加按钮
        self.btn_add = QPushButton("+ 添加条件")
        self.btn_add.clicked.connect(self._add_row)
        layout.addWidget(self.btn_add)

        # 初始一行
        self._add_row()

    def _on_table_changed(self, _=None):
        cols = self.state.get_column_names()
        for row in self._rows:
            row.update_columns(cols)

    def _add_row(self):
        cols = self.state.get_column_names()
        if not cols:
            cols = ["(无列)"]

        row = ConditionRow(cols)
        row.removed.connect(self._remove_row)
        row.col_combo.currentTextChanged.connect(lambda _: self.conditions_changed.emit())
        row.op_combo.currentTextChanged.connect(lambda _: self.conditions_changed.emit())
        row.value_input.textChanged.connect(lambda _: self.conditions_changed.emit())

        self._rows.append(row)
        self.scroll_layout.addWidget(row)
        self.conditions_changed.emit()

    def _remove_row(self, row: ConditionRow):
        if len(self._rows) <= 1:
            return  # 至少保留一行
        self._rows.remove(row)
        self.scroll_layout.removeWidget(row)
        row.deleteLater()
        self.conditions_changed.emit()

    def get_conditions(self) -> list:
        return [row.get_condition() for row in self._rows]