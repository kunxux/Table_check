"""
Layer① 预置规则编辑器
======================
从 registry 读取规则的 config_schema，动态生成配置表单。
支持：非空校验、类型校验、范围校验、枚举校验、正则校验 等。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QPushButton, QScrollArea, QFormLayout, QGroupBox,
)
from PySide6.QtCore import Qt, Signal

from gui.app import AppState
from gui.widgets.column_selector import ColumnSelector
from gui.widgets.range_editor import RangeEditor
from table_check.core.rule_base import registry


class PresetEditor(QWidget):
    """预置规则编辑器 — Layer①"""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._current_rule_name = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 规则选择下拉框
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("选择规则:"))
        self.rule_combo = QComboBox()
        self.rule_combo.setMinimumWidth(180)
        self.rule_combo.currentTextChanged.connect(self._on_rule_changed)
        sel_row.addWidget(self.rule_combo, 1)
        layout.addLayout(sel_row)

        # 规则描述
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #555; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(self.desc_label)

        # 滚动区 — 动态表单
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.form_container = QWidget()
        self.form_layout = QVBoxLayout(self.form_container)
        self.form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.form_container)
        layout.addWidget(self.scroll, 1)

        # 填充规则列表
        self._populate_rule_combo()

    def _populate_rule_combo(self):
        self.rule_combo.clear()
        for r in registry.list_all():
            self.rule_combo.addItem(f"[{r['category']}] {r['name']}", r["name"])

    # ── 规则切换 → 重建表单 ──

    def _on_rule_changed(self, text: str):
        rule_name = self.rule_combo.currentData()
        if not rule_name:
            return
        self._current_rule_name = rule_name
        self._build_form(rule_name)

    def set_rule(self, rule_name: str):
        """外部调用：设置当前规则"""
        idx = self.rule_combo.findData(rule_name)
        if idx >= 0:
            self.rule_combo.setCurrentIndex(idx)
        else:
            self._current_rule_name = rule_name
            self._build_form(rule_name)

    def _build_form(self, rule_name: str):
        """根据规则类型动态构建配置表单"""
        # 清除旧表单
        while self.form_layout.count():
            w = self.form_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        rule = registry.get(rule_name)
        if rule is None:
            return

        self.desc_label.setText(f"📝 {rule.description}")

        # 根据规则名分发到不同的表单构建器
        builder_map = {
            "not_null": self._build_not_null_form,
            "type_check": self._build_type_check_form,
            "range_check": self._build_range_check_form,
            "enum_check": self._build_enum_check_form,
            "regex_check": self._build_regex_check_form,
            "unique_check": self._build_not_null_form,   # 复用列选择
            "composite_key": self._build_not_null_form,
            "column_compare": self._build_column_compare_form,
            "conditional_required": self._build_conditional_form,
            "foreign_key": self._build_fk_form,
            "fk_consistency": self._build_fk_form,
            "cross_compare": self._build_cross_compare_form,
            "pk_diff": self._build_pk_diff_form,
            "full_diff": self._build_pk_diff_form,
        }

        builder = builder_map.get(rule_name)
        if builder:
            builder()
        else:
            # 通用：显示配置说明
            gb = QGroupBox("配置参数")
            fl = QFormLayout(gb)
            fl.addRow(QLabel("此规则暂无专用编辑器，请在 JSON 配置中手动填写参数"))
            self.form_layout.addWidget(gb)

    # ═══════════════════════════════════════════
    # 各类规则的表单构建器
    # ═══════════════════════════════════════════

    def _build_not_null_form(self):
        """非空校验 / 唯一性 / 组合键 → 列多选"""
        gb = QGroupBox("选择要检查的列")
        layout = QVBoxLayout(gb)
        self.col_selector = ColumnSelector(self.state)
        layout.addWidget(self.col_selector)
        self.form_layout.addWidget(gb)

    def _build_type_check_form(self):
        """类型校验 → 列 + 期望类型"""
        gb = QGroupBox("配置列的类型期望")
        layout = QVBoxLayout(gb)

        cols = self.state.get_column_names()
        type_opts = ["int", "float", "str", "bool"]
        self._type_fields = {}  # {col_name: QComboBox}

        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.addWidget(QLabel("列名"), 0, 0)
        grid.addWidget(QLabel("期望类型"), 0, 1)
        for i, col in enumerate(cols, 1):
            grid.addWidget(QLabel(col), i, 0)
            cb = QComboBox()
            cb.addItems(type_opts)
            grid.addWidget(cb, i, 1)
            self._type_fields[col] = cb

        layout.addLayout(grid)
        self.form_layout.addWidget(gb)

    def _build_range_check_form(self):
        """范围校验 → RangeEditor"""
        gb = QGroupBox("配置列的范围")
        layout = QVBoxLayout(gb)
        self.range_editor = RangeEditor(self.state)
        layout.addWidget(self.range_editor)
        self.form_layout.addWidget(gb)

    def _build_enum_check_form(self):
        """枚举校验 → 列 + 允许值"""
        gb = QGroupBox("配置枚举值")
        layout = QVBoxLayout(gb)

        cols = self.state.get_column_names()
        self._enum_col_combo = QComboBox()
        self._enum_col_combo.addItems(cols)
        layout.addWidget(QLabel("检查列:"))
        layout.addWidget(self._enum_col_combo)

        layout.addWidget(QLabel("允许值 (逗号分隔，如: 1,2,3,4):"))
        self._enum_values_input = QLineEdit()
        layout.addWidget(self._enum_values_input)

        self.form_layout.addWidget(gb)

    def _build_regex_check_form(self):
        """正则校验 → 列 + 正则"""
        gb = QGroupBox("配置正则表达式")
        layout = QVBoxLayout(gb)

        cols = self.state.get_column_names()
        self._regex_col_combo = QComboBox()
        self._regex_col_combo.addItems(cols)
        layout.addWidget(QLabel("检查列:"))
        layout.addWidget(self._regex_col_combo)

        layout.addWidget(QLabel("正则表达式:"))
        self._regex_input = QLineEdit()
        self._regex_input.setPlaceholderText("例如: ^[A-Z]\\d{4}$")
        layout.addWidget(self._regex_input)

        self.form_layout.addWidget(gb)

    def _build_column_compare_form(self):
        """列间比较 → 左列 + 操作符 + 右列"""
        gb = QGroupBox("列间比较")
        layout = QVBoxLayout(gb)

        cols = self.state.get_column_names()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("左列:"))
        self._cmp_left = QComboBox()
        self._cmp_left.addItems(cols)
        row1.addWidget(self._cmp_left)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("操作符:"))
        self._cmp_op = QComboBox()
        self._cmp_op.addItems([">=", ">", "<=", "<", "==", "!="])
        row2.addWidget(self._cmp_op)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("右列:"))
        self._cmp_right = QComboBox()
        self._cmp_right.addItems(cols)
        row3.addWidget(self._cmp_right)
        layout.addLayout(row3)

        self.form_layout.addWidget(gb)

    def _build_conditional_form(self):
        """条件依赖"""
        gb = QGroupBox("条件依赖")
        layout = QVBoxLayout(gb)

        cols = self.state.get_column_names()

        layout.addWidget(QLabel("当以下列满足条件:"))
        self._cond_if_col = QComboBox()
        self._cond_if_col.addItems(cols)
        layout.addWidget(self._cond_if_col)

        layout.addWidget(QLabel("值等于:"))
        self._cond_if_val = QLineEdit()
        layout.addWidget(self._cond_if_val)

        layout.addWidget(QLabel("则以下列必填 (逗号分隔):"))
        self._cond_then_cols = QLineEdit()
        self._cond_then_cols.setPlaceholderText("例如: desc, note")
        layout.addWidget(self._cond_then_cols)

        self.form_layout.addWidget(gb)

    def _build_fk_form(self):
        """外键校验"""
        gb = QGroupBox("外键配置")
        layout = QVBoxLayout(gb)

        src_cols = self.state.get_column_names()

        layout.addWidget(QLabel("源列 (当前表的列):"))
        self._fk_source_col = QComboBox()
        self._fk_source_col.addItems(src_cols)
        layout.addWidget(self._fk_source_col)

        layout.addWidget(QLabel("目标表文件路径 (留空则使用已加载的):"))
        self._fk_target_path = QLineEdit()
        self._fk_target_path.setPlaceholderText("例如: 道具表.xlsx")
        layout.addWidget(self._fk_target_path)

        layout.addWidget(QLabel("目标列名:"))
        self._fk_target_col = QLineEdit()
        self._fk_target_col.setPlaceholderText("例如: id")
        layout.addWidget(self._fk_target_col)

        self.form_layout.addWidget(gb)

    def _build_pk_diff_form(self):
        """主键对比 / 全表对比"""
        gb = QGroupBox("对比配置")
        layout = QVBoxLayout(gb)

        layout.addWidget(QLabel("主键列:"))
        self._pk_key_col = QLineEdit("id")
        layout.addWidget(self._pk_key_col)

        layout.addWidget(QLabel("对比表文件路径 (与当前表对比):"))
        self._pk_target_path = QLineEdit()
        self._pk_target_path.setPlaceholderText("例如: 规划表.xlsx")
        layout.addWidget(self._pk_target_path)

        layout.addWidget(QLabel("对比列 (逗号分隔，留空则比较所有共同列):"))
        self._pk_compare_cols = QLineEdit()
        layout.addWidget(self._pk_compare_cols)

        self.form_layout.addWidget(gb)

    def _build_cross_compare_form(self):
        """跨表列值比较"""
        gb = QGroupBox("跨表列值比较")
        layout = QVBoxLayout(gb)

        layout.addWidget(QLabel("关联列 (逗号分隔):"))
        self._x_join_on = QLineEdit()
        self._x_join_on.setPlaceholderText("例如: id")
        layout.addWidget(self._x_join_on)

        layout.addWidget(QLabel("对比列对 ('A表列=B表列'，逗号分隔):"))
        self._x_compare_pairs = QLineEdit()
        self._x_compare_pairs.setPlaceholderText("例如: price=price, count=count")
        layout.addWidget(self._x_compare_pairs)

        layout.addWidget(QLabel("对比表文件路径:"))
        self._x_target_path = QLineEdit()
        layout.addWidget(self._x_target_path)

        self.form_layout.addWidget(gb)

    # ── 获取配置 ──

    def get_rule_name(self) -> str:
        return self._current_rule_name

    def get_config(self) -> dict:
        """根据当前表单内容构造 config 字典"""
        rule_name = self._current_rule_name

        if rule_name in ("not_null", "unique_check", "composite_key"):
            if hasattr(self, 'col_selector'):
                cols = self.col_selector.get_selected_columns()
                return {"columns": cols, "key_columns": cols} if rule_name == "composite_key" else {"columns": cols}

        if rule_name == "type_check":
            if hasattr(self, '_type_fields'):
                column_types = {col: cb.currentText() for col, cb in self._type_fields.items()}
                return {"column_types": column_types}

        if rule_name == "range_check":
            if hasattr(self, 'range_editor'):
                return {"ranges": self.range_editor.get_ranges()}

        if rule_name == "enum_check":
            if hasattr(self, '_enum_col_combo'):
                col = self._enum_col_combo.currentText()
                raw = self._enum_values_input.text()
                try:
                    values = [int(v.strip()) for v in raw.split(",") if v.strip()]
                except ValueError:
                    values = [v.strip() for v in raw.split(",") if v.strip()]
                return {"enums": {col: values}}

        if rule_name == "regex_check":
            if hasattr(self, '_regex_col_combo'):
                col = self._regex_col_combo.currentText()
                pattern = self._regex_input.text()
                return {"patterns": {col: pattern}}

        if rule_name == "column_compare":
            if hasattr(self, '_cmp_left'):
                return {"comparisons": [{
                    "left": self._cmp_left.currentText(),
                    "op": self._cmp_op.currentText(),
                    "right": self._cmp_right.currentText(),
                }]}

        if rule_name == "conditional_required":
            if hasattr(self, '_cond_if_col'):
                then_cols = [c.strip() for c in self._cond_then_cols.text().split(",") if c.strip()]
                return {"conditions": [{
                    "if_column": self._cond_if_col.currentText(),
                    "if_value": self._cond_if_val.text(),
                    "then_columns": then_cols,
                }]}

        if rule_name in ("foreign_key", "fk_consistency"):
            if hasattr(self, '_fk_source_col'):
                target_path = self._fk_target_path.text().strip()
                target_col = self._fk_target_col.text().strip()
                config = {
                    "source_column": self._fk_source_col.currentText(),
                    "target_column": target_col,
                }
                if target_path:
                    config["target_df"] = target_path
                return config

        if rule_name in ("pk_diff", "full_diff"):
            if hasattr(self, '_pk_key_col'):
                target_path = self._pk_target_path.text().strip()
                compare_text = self._pk_compare_cols.text().strip()
                config = {
                    "key_column": self._pk_key_col.text().strip() or "id",
                }
                if compare_text:
                    config["compare_columns"] = [c.strip() for c in compare_text.split(",") if c.strip()]
                if target_path:
                    config["expected_df" if rule_name == "pk_diff" else "other_df"] = target_path
                return config

        if rule_name == "cross_compare":
            if hasattr(self, '_x_join_on'):
                join_on = [c.strip() for c in self._x_join_on.text().split(",") if c.strip()]
                pairs_text = self._x_compare_pairs.text().strip()
                pairs = []
                for p in pairs_text.split(","):
                    parts = p.strip().split("=")
                    if len(parts) == 2:
                        pairs.append({"a_col": parts[0].strip(), "b_col": parts[1].strip()})
                config = {"join_on": join_on, "compare_pairs": pairs}
                target_path = self._x_target_path.text().strip()
                if target_path:
                    config["other_df"] = target_path
                return config

        return {}