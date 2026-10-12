"""
DataFrame → Qt Table Model 适配器
=================================
将 pandas DataFrame 包装为 QAbstractTableModel，
支持：
  - 大数据量虚拟渲染
  - 错误行/单元格的条件着色（红色=漏填, 橙色=类型错误, 紫色=外键丢失）
  - 列头点击排序
"""

from typing import Any, Dict, List, Optional

import pandas as pd
from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, Qt, Signal, QSortFilterProxyModel,
)
from PySide6.QtGui import QColor, QFont


# ── 错误类型 → 背景色 ──
ERROR_COLORS: Dict[str, QColor] = {
    "漏填":         QColor(255, 235, 156),   # 淡黄
    "类型错误":     QColor(255, 200, 150),   # 淡橙
    "超出范围":     QColor(255, 200, 150),
    "超出上限":     QColor(255, 200, 150),
    "超出下限":     QColor(255, 200, 150),
    "枚举错误":     QColor(255, 180, 180),   # 淡粉
    "格式错误":     QColor(255, 180, 180),
    "重复值":       QColor(200, 200, 255),   # 淡蓝
    "条件必填缺失": QColor(255, 235, 156),
    "列间关系错误": QColor(255, 200, 150),
    "外键丢失":     QColor(220, 180, 255),   # 淡紫
    "孤立的源引用": QColor(220, 180, 255),
    "跨表数据不一致": QColor(255, 180, 180),
    "实际有·规划无": QColor(255, 200, 150),
    "规划有·实际无": QColor(255, 200, 150),
    "数值不一致":   QColor(255, 180, 180),
}


class PandasModel(QAbstractTableModel):
    """将 pandas DataFrame 暴露给 QTableView 的适配器。

    支持按错误信息高亮单元格：
      调用 set_error_highlights([{行号, 列名, 错误类型}, ...])
    """

    highlight_changed = Signal()

    def __init__(self, df: pd.DataFrame = None):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()

        # 错误高亮索引: {(row_idx, col_name): error_type}
        self._highlights: Dict[tuple, str] = {}

    # ── 数据访问 ──

    def set_dataframe(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self._highlights.clear()
        self.endResetModel()
        self.highlight_changed.emit()

    def dataframe(self) -> pd.DataFrame:
        return self._df

    # ── 错误高亮 ──

    def set_error_highlights(self, errors: List[Dict]):
        """根据错误列表建立高亮索引。

        errors 中每条应有: {"行号": int, "列名": str, "错误类型": str}
        """
        self._highlights.clear()
        for e in errors:
            row = e.get("行号")
            col = e.get("列名")
            err_type = e.get("错误类型", "")
            if row is not None and col is not None:
                # 行号从 Excel 第2行开始 → DataFrame 索引从0开始
                try:
                    row_idx = int(row) - 2
                except (ValueError, TypeError):
                    continue
                self._highlights[(row_idx, col)] = err_type

        self.highlight_changed.emit()
        # 通知视图刷新（发送整个 model 的 dataChanged）
        if self._df is not None and not self._df.empty:
            top_left = self.index(0, 0)
            bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def clear_highlights(self):
        self._highlights.clear()
        self.highlight_changed.emit()
        if self._df is not None and not self._df.empty:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, self.columnCount() - 1),
            )

    def get_cell_error(self, row: int, col_name: str) -> Optional[str]:
        return self._highlights.get((row, col_name))

    # ── QAbstractTableModel 接口 ──

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._df.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row, col = index.row(), index.column()
        col_name = self._df.columns[col]

        if role == Qt.ItemDataRole.DisplayRole:
            val = self._df.iloc[row, col]
            if pd.isna(val):
                return ""
            return str(val)

        if role == Qt.ItemDataRole.BackgroundRole:
            # 错误高亮
            err_type = self._highlights.get((row, col_name))
            if err_type:
                # 精确匹配
                if err_type in ERROR_COLORS:
                    return ERROR_COLORS[err_type]
                # 模糊匹配
                for key, color in ERROR_COLORS.items():
                    if key in err_type:
                        return color
                return QColor(255, 200, 200)  # 默认红色
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            val = self._df.iloc[row, col]
            err = self._highlights.get((row, col_name))
            tip = f"行{row+2} | {col_name} = {val}"
            if err:
                tip += f"\n⚠ {err}"
            return tip

        if role == Qt.ItemDataRole.TextAlignmentRole:
            val = self._df.iloc[row, col]
            if isinstance(val, (int, float)) and not pd.isna(val):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(self._df.columns[section])
            if role == Qt.ItemDataRole.ToolTipRole:
                col_name = self._df.columns[section]
                dtype = str(self._df[col_name].dtype)
                nulls = int(self._df[col_name].isna().sum())
                return f"{col_name}\n类型: {dtype}\n空值: {nulls}/{len(self._df)}"
        elif orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section + 2)  # Excel 行号
        return None

    def flags(self, index: QModelIndex):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable