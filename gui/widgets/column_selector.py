"""
列多选组件
==========
QListWidget + 复选框，显示列名 + 类型图标。
提供全选/取消全选按钮。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QCheckBox,
)
from PySide6.QtCore import Qt, Signal

from gui.app import AppState


class ColumnSelector(QWidget):
    """列多选组件"""

    selection_changed = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._init_ui()
        self.state.table_loaded.connect(self._refresh)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 全选/全不选
        btn_row = QHBoxLayout()
        self.btn_all = QPushButton("全选")
        self.btn_none = QPushButton("全不选")
        self.btn_all.clicked.connect(self._select_all)
        self.btn_none.clicked.connect(self._select_none)
        btn_row.addWidget(self.btn_all)
        btn_row.addWidget(self.btn_none)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 列列表
        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(lambda _: self.selection_changed.emit())
        layout.addWidget(self.list_widget)

        self._refresh()

    def _refresh(self, _=None):
        self.list_widget.clear()
        cols = self.state.get_column_names()
        info = self.state.get_current_info()

        for col_name in cols:
            item = QListWidgetItem()
            item.setText(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)

            # 类型图标标记
            if info:
                for col_info in info.columns:
                    if col_info.name == col_name:
                        type_icon = {"int": "🔢", "float": "📊", "str": "📝",
                                     "bool": "☑", "datetime": "📅"}.get(col_info.python_type, "📌")
                        null_info = f"  空值{col_info.null_ratio:.0%}" if col_info.null_ratio > 0 else ""
                        item.setText(f"{type_icon} {col_name}{null_info}")
                        break

            self.list_widget.addItem(item)

    def get_selected_columns(self) -> list:
        """返回被勾选的列名列表"""
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                # 提取原始列名（去掉 emoji 前缀）
                text = item.text()
                # 简单处理: 跳过第一个字如果是 emoji
                parts = text.split(" ", 1)
                if len(parts) > 1:
                    selected.append(parts[1].split("  ")[0])  # 去掉空值信息
                else:
                    selected.append(text)
        return selected

    def _select_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.CheckState.Checked)
        self.selection_changed.emit()

    def _select_none(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.selection_changed.emit()