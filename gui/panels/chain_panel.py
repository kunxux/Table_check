"""
链式编排面板
============
右侧下半部：展示当前链的步骤列表，支持拖拽排序、删除、一键执行。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from gui.app import AppState


class ChainPanel(QWidget):
    """链式编排面板"""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 标题
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("🔗 链式编排"))
        title_row.addStretch()
        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self._on_clear)
        title_row.addWidget(self.btn_clear)
        layout.addLayout(title_row)

        # 步骤列表（支持拖拽排序）
        self.step_list = QListWidget()
        self.step_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.step_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.step_list.setAlternatingRowColors(True)
        self.step_list.setMinimumHeight(80)
        self.step_list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.step_list, 1)

        # 操作按钮
        btn_row = QHBoxLayout()

        self.btn_delete = QPushButton("删除选中")
        self.btn_delete.clicked.connect(self._on_delete_selected)
        btn_row.addWidget(self.btn_delete)

        btn_row.addStretch()

        self.btn_run = QPushButton("▶ 执行链")
        self.btn_run.setStyleSheet("background-color: #5b9bd5; color: white; font-weight: bold; padding: 6px 20px;")
        self.btn_run.clicked.connect(self._on_run_chain)
        btn_row.addWidget(self.btn_run)

        layout.addLayout(btn_row)

    def _connect_signals(self):
        self.state.chain_changed.connect(self._refresh_list)
        self.state.check_finished.connect(self._on_check_finished)

    # ── 刷新 ──

    def _refresh_list(self):
        self.step_list.clear()
        for step in self.state.chain_steps:
            mode_icon = "🔍" if step.mode == "validate" else "📊"
            text = f"{mode_icon} {step.step_index}. {step.step_name}  [{step.rule_name}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, step.step_index - 1)
            item.setToolTip(
                f"规则: {step.rule_name}\n"
                f"模式: {step.mode}\n"
                f"配置: {step.config}"
            )
            self.step_list.addItem(item)

    # ── 动作 ──

    def _on_rows_moved(self, parent, start, end, dest, row):
        """拖拽排序后同步到 state"""
        # 收集当前列表中的顺序
        new_order = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            orig_idx = item.data(Qt.ItemDataRole.UserRole)
            if orig_idx is not None and orig_idx < len(self.state.chain_steps):
                new_order.append(orig_idx)

        # 更新 state 中的顺序
        steps = self.state.chain_steps
        new_steps = [steps[i] for i in new_order if i < len(steps)]
        self.state.chain_steps = new_steps
        for idx, s in enumerate(self.state.chain_steps):
            s.step_index = idx + 1
        self.state.chain_changed.emit()

    def _on_delete_selected(self):
        row = self.step_list.currentRow()
        if row >= 0:
            self.state.remove_chain_step(row)

    def _on_clear(self):
        reply = QMessageBox.question(
            self, "确认", "清空整条链？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.state.clear_chain()

    def _on_run_chain(self):
        if not self.state.chain_steps:
            QMessageBox.information(self, "提示", "链中没有步骤")
            return
        try:
            self.state.run_chain()
        except Exception as e:
            QMessageBox.warning(self, "执行失败", str(e))

    def _on_check_finished(self, result):
        """链执行完成后高亮标签"""
        from table_check.core.chain_engine import ChainResult
        if isinstance(result, ChainResult):
            icon = "✅" if result.all_passed else "❌"
            self.state.status_message.emit(
                f"{icon} 链执行完成 — {result.total_errors} 个错误"
            )