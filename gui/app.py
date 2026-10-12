"""
全局应用状态
============
单例 QObject，持有当前加载的数据、选中的规则、编辑中的链等。
通过 Qt Signal 通知所有面板状态变更。
"""

from typing import Dict, List, Optional, Any

import pandas as pd
from PySide6.QtCore import QObject, Signal

from table_check.core.table_loader import TableLoader, TableInfo
from table_check.core.rule_base import RuleResult
from table_check.core.chain_engine import ChainStep


class AppState(QObject):
    """全局单例状态对象。

    所有面板通过访问 app_state.xxx 来读取数据，
    通过连接 app_state.signals.xxx 来响应数据变更。
    """

    # ── 信号定义 ──
    table_loaded = Signal(str)          # 表格加载完成，参数: 表名
    rule_selected = Signal(str)         # 规则库中选中规则，参数: rule_name
    chain_changed = Signal()            # 链步骤变化
    check_finished = Signal(object)     # 校验完成，参数: RuleResult 或 ChainResult
    status_message = Signal(str)        # 状态栏消息

    def __init__(self):
        super().__init__()

        # ── 表格数据 ──
        self.dataframes: Dict[str, pd.DataFrame] = {}    # {表名: df}
        self.table_infos: Dict[str, TableInfo] = {}      # {表名: TableInfo}
        self.current_table: Optional[str] = None         # 当前活动表名
        self.current_file: Optional[str] = None          # 当前文件路径
        self.available_sheets: List[str] = []             # 当前文件的 Sheet 列表

        # ── 规则与链 ──
        self.current_rule_name: Optional[str] = None
        self.current_rule_config: Dict[str, Any] = {}
        self.chain_steps: List[ChainStep] = []

        # ── 最近结果 ──
        self.last_result: Optional[Any] = None  # RuleResult 或 ChainResult
        self.last_errors: List[Dict] = []

    # ── 表格操作 ──

    def load_table(self, file_path: str, sheet_name: str = None) -> str:
        """加载表格文件，返回表名。"""
        # 获取所有 Sheet（仅 Excel）
        self.available_sheets = TableLoader.list_sheets(file_path)

        # 未指定 Sheet 时默认第一个
        actual_sheet = sheet_name
        if actual_sheet is None and self.available_sheets:
            actual_sheet = self.available_sheets[0]

        df = TableLoader.load(file_path, actual_sheet)
        info = TableLoader.analyze(file_path, actual_sheet)
        name = info.name

        self.dataframes[name] = df
        self.table_infos[name] = info
        self.current_table = name
        self.current_file = file_path

        self.table_loaded.emit(name)
        self.status_message.emit(
            f"已加载 {name} — {info.total_rows} 行 x {info.total_columns} 列"
        )
        return name

    def switch_sheet(self, sheet_name: str):
        """切换到同一文件的其他 Sheet"""
        if not self.current_file:
            return
        self.load_table(self.current_file, sheet_name)

    def get_current_df(self) -> Optional[pd.DataFrame]:
        if self.current_table:
            return self.dataframes.get(self.current_table)
        return None

    def get_current_info(self) -> Optional[TableInfo]:
        if self.current_table:
            return self.table_infos.get(self.current_table)
        return None

    def get_column_names(self, table_name: str = None) -> List[str]:
        name = table_name or self.current_table
        if name and name in self.dataframes:
            return list(self.dataframes[name].columns)
        return []

    # ── 规则操作 ──

    def select_rule(self, rule_name: str):
        self.current_rule_name = rule_name
        self.current_rule_config = {}
        self.rule_selected.emit(rule_name)

    def set_rule_config(self, config: dict):
        self.current_rule_config = config

    # ── 链操作 ──

    def add_chain_step(self, step: ChainStep):
        self.chain_steps.append(step)
        self.chain_changed.emit()

    def remove_chain_step(self, index: int):
        if 0 <= index < len(self.chain_steps):
            self.chain_steps.pop(index)
            self.chain_changed.emit()

    def clear_chain(self):
        self.chain_steps.clear()
        self.chain_changed.emit()

    def move_chain_step(self, from_idx: int, to_idx: int):
        if 0 <= from_idx < len(self.chain_steps) and 0 <= to_idx < len(self.chain_steps):
            step = self.chain_steps.pop(from_idx)
            self.chain_steps.insert(to_idx, step)
            # 重新编号
            for i, s in enumerate(self.chain_steps):
                s.step_index = i + 1
            self.chain_changed.emit()

    # ── 执行 ──

    def run_single_rule(self, rule_name: str, config: dict) -> RuleResult:
        from table_check.core.rule_base import registry
        rule = registry.get(rule_name)
        if rule is None:
            raise ValueError(f"规则 '{rule_name}' 未注册")
        df = self.get_current_df()
        if df is None:
            raise ValueError("没有加载的表格")

        # 解析 config 中的表引用
        resolved_config = dict(config)
        for key in ("target_df", "expected_df", "other_df", "target_table"):
            if key in resolved_config and isinstance(resolved_config[key], str):
                ref = resolved_config[key]
                if ref in self.dataframes:
                    resolved_config["target_df" if key == "target_table" else key] = self.dataframes[ref]

        result = rule.validate(df, **resolved_config)
        self.last_result = result
        self.last_errors = result.errors
        self.check_finished.emit(result)
        return result

    def run_chain(self) -> Any:
        from table_check.core.chain_engine import ChainValidator
        chain = ChainValidator("UI链")

        # 注册所有已加载的表格
        for name, df in self.dataframes.items():
            chain.register_table(name, df)

        # 添加步骤
        for step in self.chain_steps:
            chain.add_step(step)

        result = chain.run()
        self.last_result = result
        self.last_errors = []
        for r in result.step_results:
            if r:
                self.last_errors.extend(r.errors)
        self.check_finished.emit(result)
        return result