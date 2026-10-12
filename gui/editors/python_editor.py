"""
Layer③ 自定义 Python 表达式编辑器
===================================
允许用户编写 pandas 布尔表达式，用 eval 沙箱安全执行。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QLineEdit,
)
from PySide6.QtCore import Qt

from gui.app import AppState


class PythonEditor(QWidget):
    """自定义 Python 表达式编辑器 — Layer③"""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 说明
        hint = QLabel(
            "编写一个 pandas 表达式，用于检查当前表格的行是否合规。\n"
            "可用变量: <b>df</b> — 当前表格的 pandas DataFrame\n"
            "返回: <b>布尔 Series</b> (True=有问题, False=正常) 或返回一个错误行的子 DataFrame。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(hint)

        # 当前列名提示
        self.col_hint = QLabel()
        self.col_hint.setWordWrap(True)
        self.col_hint.setStyleSheet("color: #44a; font-size: 11px; font-family: Consolas, monospace;")
        layout.addWidget(self.col_hint)

        # 代码区域
        self.code_editor = QTextEdit()
        self.code_editor.setPlaceholderText(
            "# 示例: 检查 price 是否为负数\n"
            "# bad = df['price'] < 0\n"
            "# bad  # 最后一行是返回值\n\n"
            "# 示例: 检查 type==2 时 desc 是否为空\n"
            "# mask = (df['type'] == 2) & df['desc'].isna()\n"
            "# mask\n"
        )
        self.code_editor.setStyleSheet(
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;"
        )
        self.code_editor.setTabStopDistance(20)
        layout.addWidget(self.code_editor, 1)

        # 错误提示
        layout.addWidget(QLabel("错误提示信息:"))
        self.error_msg = QLineEdit()
        self.error_msg.setPlaceholderText("当表达式返回 True 时显示的错误信息...")
        layout.addWidget(self.error_msg)

        # 监听表格切换更新列名提示
        self.state.table_loaded.connect(self._update_col_hint)
        self._update_col_hint()

    def _update_col_hint(self, _=None):
        cols = self.state.get_column_names()
        if cols:
            refs = ", ".join([f"df['{c}']" for c in cols[:8]])
            more = "..." if len(cols) > 8 else ""
            self.col_hint.setText(f"可用列: {refs}{more}")
        else:
            self.col_hint.setText("（未加载表格）")

    def get_config_and_rule(self):
        """获取配置和规则名。返回 (rule_name, config) 或 None。"""
        code = self.code_editor.toPlainText().strip()
        if not code:
            return None

        from table_check.core.rule_base import registry
        rule_name = "expression_check"

        config = {
            "code": code,
            "error_message": self.error_msg.text().strip() or "自定义校验未通过",
        }
        return rule_name, config