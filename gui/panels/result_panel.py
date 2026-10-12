"""
结果报告面板
============
底部区域：展示校验结果摘要 + 错误列表，支持点击跳转到表格对应单元格。
"""

from typing import Optional
import pandas as pd

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableView, QHeaderView, QPushButton, QAbstractItemView, QSplitter,
)
from PySide6.QtCore import Qt, Signal, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor

from gui.app import AppState
from table_check.core.rule_base import RuleResult
from table_check.core.chain_engine import ChainResult


class _ErrorModel(QAbstractTableModel):
    """错误列表的轻量级 Model"""

    def __init__(self):
        super().__init__()
        self._errors = []
        self._columns = ["行号", "列名", "当前值", "错误类型", "规则说明"]

    def set_errors(self, errors: list):
        self.beginResetModel()
        self._errors = errors
        if errors:
            self._columns = list(errors[0].keys())
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._errors)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            col_name = self._columns[col]
            val = self._errors[row].get(col_name, "")
            return str(val)
        if role == Qt.ItemDataRole.ToolTipRole:
            col_name = self._columns[col]
            return str(self._errors[row].get(col_name, ""))
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._columns[section]
        return None


class ResultPanel(QWidget):
    """结果报告面板 — 底部"""

    result_clicked = Signal(int, str)  # (row_idx, col_name) → 表格跳转

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 摘要行
        summary_row = QHBoxLayout()
        self.summary_label = QLabel("尚未执行检查")
        self.summary_label.setStyleSheet("font-size: 13px;")
        summary_row.addWidget(self.summary_label, 1)

        self.btn_export = QPushButton("📄 导出 Excel 报告")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export)
        summary_row.addWidget(self.btn_export)

        layout.addLayout(summary_row)

        # 错误表格
        self.error_model = _ErrorModel()
        self.error_table = QTableView()
        self.error_table.setModel(self.error_model)
        self.error_table.setAlternatingRowColors(True)
        self.error_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.error_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.error_table.horizontalHeader().setStretchLastSection(True)
        self.error_table.doubleClicked.connect(self._on_error_double_clicked)
        layout.addWidget(self.error_table)

    def _connect_signals(self):
        self.state.check_finished.connect(self._on_check_finished)

    def _on_check_finished(self, result):
        """校验/链执行完成"""
        if result is None:
            return

        self.btn_export.setEnabled(True)

        if isinstance(result, ChainResult):
            is_pass = result.all_passed
            total = sum(r.total_rows for r in result.step_results if r)
            failed = result.total_errors
            errors = []
            for r in result.step_results or []:
                if r:
                    errors.extend(r.errors)
        else:
            is_pass = result.is_pass
            total = result.total_rows
            failed = result.failed_rows
            errors = result.errors

        icon = "✅" if is_pass else "❌"
        text = f"{icon} {result.summary() if isinstance(result, ChainResult) else result.summary}"
        self.summary_label.setText(text)
        self.error_model.set_errors(errors)
        self.error_table.resizeColumnsToContents()

    def _on_error_double_clicked(self, index: QModelIndex):
        """双击错误行 → 跳转到表格对应位置"""
        col_name = "行号"
        row_val = self.error_model._errors[index.row()].get("行号", "")
        col_val = self.error_model._errors[index.row()].get("列名", "")

        try:
            row_idx = int(str(row_val)) - 2  # 转为 0-based
        except (ValueError, TypeError):
            return

        self.result_clicked.emit(row_idx, str(col_val))

        # 通知 table_panel 跳转（通过 parent 查找）
        from PySide6.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'table_panel'):
                widget.table_panel.go_to_row(row_idx, str(col_val))

    def _on_export(self):
        """导出报告——复用 main_window 的导出逻辑"""
        from PySide6.QtWidgets import QApplication, QMessageBox
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, '_on_export_report'):
                widget._on_export_report()
                return