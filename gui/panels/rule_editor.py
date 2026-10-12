"""
规则编辑面板
============
右侧上半部：三个 Tab（预置规则 | 表达式规则 | Python 表达式）
统一容器：规则名输入 + Tab 切换 + 测试/保存/加入链按钮
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTabWidget, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from gui.app import AppState
from table_check.core.chain_engine import ChainStep
from gui.editors.preset_editor import PresetEditor
from gui.editors.expression_editor import ExpressionEditor
from gui.editors.python_editor import PythonEditor


class RuleEditorPanel(QWidget):
    """规则编辑面板 — 右侧上半部"""

    rule_add_to_chain = Signal(object)  # 发射 ChainStep

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── 顶部: 规则名 ──
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("规则名称:"))
        self.rule_name_input = QLineEdit()
        self.rule_name_input.setPlaceholderText("给这条规则取个名字...")
        name_row.addWidget(self.rule_name_input, 1)
        layout.addLayout(name_row)

        # ── Tab 切换 ──
        self.tabs = QTabWidget()

        self.preset_editor = PresetEditor(self.state)
        self.expr_editor = ExpressionEditor(self.state)
        self.python_editor = PythonEditor(self.state)

        self.tabs.addTab(self.preset_editor, "① 预置规则")
        self.tabs.addTab(self.expr_editor, "② 表达式规则")
        self.tabs.addTab(self.python_editor, "③ Python 表达式")

        layout.addWidget(self.tabs, 1)

        # ── 底部按钮 ──
        btn_row = QHBoxLayout()

        self.btn_test = QPushButton("▶ 测试")
        self.btn_test.setStyleSheet("font-weight: bold;")
        self.btn_test.clicked.connect(self._on_test)
        btn_row.addWidget(self.btn_test)

        self.btn_save = QPushButton("💾 保存到我的规则")
        self.btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self.btn_save)

        self.btn_add_chain = QPushButton("➕ 加入链")
        self.btn_add_chain.setStyleSheet("background-color: #5b9bd5; color: white; font-weight: bold;")
        self.btn_add_chain.clicked.connect(self._on_add_to_chain)
        btn_row.addWidget(self.btn_add_chain)

        layout.addLayout(btn_row)

    def _connect_signals(self):
        self.state.rule_selected.connect(self._on_rule_selected)

    # ── 加载规则 ──

    def load_rule(self, rule_name: str):
        """双击规则库中的规则 → 加载到编辑区"""
        from table_check.core.rule_base import registry
        rule = registry.get(rule_name)
        if rule is None:
            return

        self.rule_name_input.setText(rule.description)

        # 判断规则类型，切到对应 tab
        self.tabs.setCurrentIndex(0)  # 默认预置 tab
        self.preset_editor.set_rule(rule_name)

    def _on_rule_selected(self, rule_name: str):
        if rule_name:
            self.load_rule(rule_name)

    # ── 动作 ──

    def _on_test(self):
        """根据当前 tab 执行不同的测试逻辑"""
        rule_name = self.state.current_rule_name
        config = self.state.current_rule_config

        # 更新 config
        tab_idx = self.tabs.currentIndex()
        if tab_idx == 0:
            config = self.preset_editor.get_config()
            rule_name = self.preset_editor.get_rule_name()
        elif tab_idx == 1:
            result = self.expr_editor.get_config_and_rule()
            if result:
                rule_name, config = result
            else:
                QMessageBox.warning(self, "提示", "请先配置表达式条件")
                return
        elif tab_idx == 2:
            result = self.python_editor.get_config_and_rule()
            if result:
                rule_name, config = result
            else:
                QMessageBox.warning(self, "提示", "请先输入 Python 表达式")
                return

        if not rule_name:
            QMessageBox.warning(self, "提示", "请选择或配置一条规则")
            return

        self.state.current_rule_name = rule_name
        self.state.current_rule_config = config or {}

        try:
            self.state.run_single_rule(rule_name, config or {})
        except Exception as e:
            QMessageBox.warning(self, "测试失败", str(e))

    def _on_save(self):
        """保存到'我的规则'"""
        name = self.rule_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入规则名称")
            return

        rule_name = self.state.current_rule_name
        config = self.state.current_rule_config

        tab_idx = self.tabs.currentIndex()
        if tab_idx == 0:
            config = self.preset_editor.get_config()
            rule_name = self.preset_editor.get_rule_name()

        # 通过 main_window 访问 rule_library
        from PySide6.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'rule_library'):
                widget.rule_library.add_user_rule(name, rule_name, config)
                self.state.status_message.emit(f"规则 '{name}' 已保存")
                return

    def _on_add_to_chain(self):
        """将当前配置好的规则加入链"""
        rule_name = self.state.current_rule_name
        config = self.state.current_rule_config
        name = self.rule_name_input.text().strip() or rule_name

        tab_idx = self.tabs.currentIndex()
        if tab_idx == 0:
            config = self.preset_editor.get_config()
            rule_name = self.preset_editor.get_rule_name()
        elif tab_idx == 1:
            result = self.expr_editor.get_config_and_rule()
            if result:
                rule_name, config = result
        elif tab_idx == 2:
            result = self.python_editor.get_config_and_rule()
            if result:
                rule_name, config = result

        if not rule_name:
            QMessageBox.warning(self, "提示", "请先配置一条规则")
            return

        step = ChainStep(
            step_index=len(self.state.chain_steps) + 1,
            step_name=name,
            rule_name=rule_name,
            config=config or {},
            mode="validate",
        )
        self.rule_add_to_chain.emit(step)
        self.state.status_message.emit(f"已加入链: {name}")