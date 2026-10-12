"""
Layer② 可视表达式规则编辑器
=============================
通过选择 列 + 操作符 + 值 来构建检查条件，无需写代码。
支持 AND/OR 组合多个条件。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QScrollArea,
)
from PySide6.QtCore import Qt

from gui.app import AppState
from gui.widgets.condition_builder import ConditionBuilder


class ExpressionEditor(QWidget):
    """可视表达式规则编辑器 — Layer②"""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 说明
        hint = QLabel(
            "通过选择 列 + 操作符 + 值 来构建检查条件。"
            "所有条件用 AND 或 OR 连接。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(hint)

        # 条件构建器
        self.cond_builder = ConditionBuilder(self.state)
        layout.addWidget(self.cond_builder, 1)

        # 表达式预览
        layout.addWidget(QLabel("生成的 pandas 表达式预览:"))
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(70)
        self.preview.setStyleSheet(
            "background-color: #f5f5f5; font-family: Consolas, monospace; font-size: 12px;"
        )
        layout.addWidget(self.preview)

        # 错误提示
        layout.addWidget(QLabel("错误提示信息:"))
        self.error_msg = QLineEdit()
        self.error_msg.setPlaceholderText("当条件不满足时显示的错误信息...")
        layout.addWidget(self.error_msg)

        # 实时更新预览
        self.cond_builder.conditions_changed.connect(self._update_preview)

    def _update_preview(self):
        """实时更新表达式预览"""
        conds = self.cond_builder.get_conditions()
        if not conds:
            self.preview.setPlainText("(尚未配置条件)")
            return

        lines = []
        for i, cond in enumerate(conds):
            col = cond.get("column", "?")
            op = cond.get("operator", "?")
            val = cond.get("value", "?")
            connector = cond.get("connector", "AND")

            if op in ("为空", "不为空"):
                lines.append(f"df['{col}'].isna()  ← {'AND' if connector=='AND' else 'OR'}")
            elif op == "in":
                lines.append(f"df['{col}'].isin({val})  {'AND' if connector=='AND' else 'OR'}")
            else:
                lines.append(f"(df['{col}'] {op} {val})  {connector}")

        expr = "\n".join(lines)
        self.preview.setPlainText(expr)

    def get_config_and_rule(self):
        """获取配置和规则名。返回 (rule_name, config) 或 None。"""
        conds = self.cond_builder.get_conditions()
        if not conds:
            return None

        # 使用 expression_check 规则（如果注册了）
        from table_check.core.rule_base import registry
        if "expression_check" in registry:
            rule_name = "expression_check"
        else:
            rule_name = "expression_check"  # 兜底，会报未注册

        config = {
            "conditions": conds,
            "error_message": self.error_msg.text().strip() or "表达式校验未通过",
        }
        return rule_name, config