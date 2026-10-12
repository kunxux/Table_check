"""
表格预览面板
============
中央区域：展示加载的表格，支持选择 Sheet、查看列信息。
"""

import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableView, QHeaderView, QComboBox, QPushButton,
    QSplitter, QTextBrowser,
)
from PySide6.QtCore import Qt, Signal

from gui.app import AppState
from gui.models.dataframe_model import PandasModel


class TablePanel(QWidget):
    """表格预览面板 — 中央区域"""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._model = PandasModel()
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── 顶部: 文件路径 + Sheet选择 ──
        top_bar = QHBoxLayout()

        self.file_label = QLabel("未加载表格 — 请拖入 .xlsx/.csv 文件或点击 文件→打开")
        self.file_label.setStyleSheet("color: #888; font-style: italic;")
        top_bar.addWidget(self.file_label, 1)

        self.sheet_label = QLabel("Sheet:")
        self.sheet_combo = QComboBox()
        self.sheet_combo.setMinimumWidth(120)
        self.sheet_combo.setVisible(False)
        self.sheet_label.setVisible(False)
        self.sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
        top_bar.addWidget(self.sheet_label)
        top_bar.addWidget(self.sheet_combo)

        layout.addLayout(top_bar)

        # ── 主体: QSplitter (上=表格, 下=列信息) ──
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 表格视图
        self.table_view = QTableView()
        self.table_view.setModel(self._model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.table_view)

        # 列信息文本
        self.column_info = QTextBrowser()
        self.column_info.setMaximumHeight(120)
        self.column_info.setStyleSheet("font-family: 'Consolas', 'Microsoft YaHei'; font-size: 12px;")
        splitter.addWidget(self.column_info)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def _connect_signals(self):
        self.state.table_loaded.connect(self._on_table_loaded)
        self.state.check_finished.connect(self._on_check_finished)
        self._model.highlight_changed.connect(self.table_view.viewport().update)

    # ── 事件 ──

    def _on_table_loaded(self, table_name: str):
        df = self.state.dataframes.get(table_name)
        info = self.state.table_infos.get(table_name)
        if df is None:
            return

        self._model.set_dataframe(df)
        self.file_label.setText(f"📊 {table_name}  ({df.shape[0]} 行 x {df.shape[1]} 列)")

        # 列信息
        if info:
            self._update_column_info(info)

        # Sheet 选择器：有多个 Sheet 时显示
        self._update_sheet_combo()

    def _update_sheet_combo(self):
        """根据当前文件的 Sheet 列表更新下拉框"""
        sheets = self.state.available_sheets
        if len(sheets) > 1:
            # 暂断信号防止切换时触发递归
            self.sheet_combo.blockSignals(True)
            self.sheet_combo.clear()
            self.sheet_combo.addItems(sheets)
            # 选中当前已加载的 Sheet（通过 current_table 名字推断）
            info = self.state.get_current_info()
            if info and info.sheet_name:
                idx = self.sheet_combo.findText(info.sheet_name)
                if idx >= 0:
                    self.sheet_combo.setCurrentIndex(idx)
            self.sheet_combo.blockSignals(False)
            self.sheet_combo.setVisible(True)
            self.sheet_label.setVisible(True)
        else:
            self.sheet_combo.setVisible(False)
            self.sheet_label.setVisible(False)

    def _on_sheet_changed(self, sheet_name: str):
        """用户切换 Sheet"""
        if sheet_name and self.state.current_file:
            info = self.state.get_current_info()
            if info and info.sheet_name == sheet_name:
                return  # 已经是当前 Sheet，跳过
            self.state.switch_sheet(sheet_name)

    def _on_check_finished(self, result):
        """校验完成后，将错误高亮到表格"""
        errors = self.state.last_errors
        if errors:
            self._model.set_error_highlights(errors)

    def _update_column_info(self, info):
        lines = ["<b>列分析:</b>"]
        for col in info.columns:
            kws = ", ".join(col.keywords) if col.keywords else "—"
            ext = f"  [{col.min_value}~{col.max_value}]" if col.min_value is not None else ""
            lines.append(
                f"  {col.name:<18} {col.python_type:<6} "
                f"空值 {col.null_ratio:.0%}  "
                f"唯一 {col.unique_count}  "
                f"<span style='color:#44a'>{kws}</span>{ext}"
            )
        self.column_info.setHtml("<br>".join(lines))

    def clear(self):
        self._model.set_dataframe(pd.DataFrame())
        self.file_label.setText("未加载表格")
        self.column_info.clear()

    def go_to_row(self, row_idx: int, col_name: str = None):
        """跳转到指定行/列"""
        # row_idx 是 DataFrame 索引（0-based）
        if 0 <= row_idx < self._model.rowCount():
            col = -1
            if col_name and col_name in self._model.dataframe().columns:
                col = list(self._model.dataframe().columns).index(col_name)
            elif col_name:
                col = 0
            index = self._model.index(row_idx, col if col >= 0 else 0)
            self.table_view.scrollTo(index)
            self.table_view.selectRow(row_idx)