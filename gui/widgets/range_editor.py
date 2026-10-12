"""
范围编辑器
==========
用于 range_check 规则的可视化参数配置。
表格形式: 列名 | min | max，支持增删行。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QPushButton, QHeaderView, QSpinBox,
)
from PySide6.QtCore import Qt

from gui.app import AppState


class RangeEditor(QWidget):
    """范围编辑器 — 列 + min + max 可编辑表格"""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._init_ui()
        self.state.table_loaded.connect(self._refresh_columns)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ 添加范围")
        self.btn_add.clicked.connect(self._add_row)
        self.btn_remove = QPushButton("- 删除选中")
        self.btn_remove.clicked.connect(self._remove_row)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 表格: 列名 | min | max
        self.table = QTableWidget(1, 3)
        self.table.setHorizontalHeaderLabels(["列名", "最小值 (min)", "最大值 (max)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self._refresh_columns()

    def _refresh_columns(self, _=None):
        """表格加载后更新列名下拉框"""
        cols = self.state.get_column_names()
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if isinstance(cb, QComboBox):
                current = cb.currentText()
                cb.clear()
                cb.addItems(cols)
                if current in cols:
                    cb.setCurrentText(current)

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 列名下拉
        cb = QComboBox()
        cb.addItems(self.state.get_column_names())
        self.table.setCellWidget(row, 0, cb)

        # min
        min_spin = QSpinBox()
        min_spin.setRange(-999999, 999999)
        min_spin.setValue(0)
        self.table.setCellWidget(row, 1, min_spin)

        # max
        max_spin = QSpinBox()
        max_spin.setRange(-999999, 999999)
        max_spin.setValue(10000)
        self.table.setCellWidget(row, 2, max_spin)

    def _remove_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def get_ranges(self) -> dict:
        """返回 {列名: {min: int, max: int}}"""
        ranges = {}
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            min_w = self.table.cellWidget(row, 1)
            max_w = self.table.cellWidget(row, 2)

            col = cb.currentText() if isinstance(cb, QComboBox) else ""
            min_v = min_w.value() if isinstance(min_w, QSpinBox) else 0
            max_v = max_w.value() if isinstance(max_w, QSpinBox) else 99999

            if col:
                ranges[col] = {"min": min_v, "max": max_v}
        return ranges