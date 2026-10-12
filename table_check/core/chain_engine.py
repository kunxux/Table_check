"""
链式调度引擎
============
将多个规则串联成一条"校验流水线"。
每个步骤可以是 validate（产出错误列表）或 transform（产出新表），
后续步骤可以引用前面步骤产出的中间表。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .rule_base import BaseRule, RuleResult, registry
from .table_loader import TableLoader


# ──────────────────────────────────────────────
# ChainStep — 链中的一个步骤
# ──────────────────────────────────────────────

@dataclass
class ChainStep:
    """链式校验中的一个步骤定义。

    Attributes:
        step_index: 序号（从 1 开始）
        step_name: 人类可读的步骤名（会出现在报告里）
        rule_name: 要执行的规则名（必须在 registry 中已注册）
        config: 规则的参数（列名、阈值等）
        mode: 'validate' 或 'transform'
        input_tables: 该步骤依赖的输入表引用（可以是文件名、或前序步骤产出的表名）
        output_table: transform 模式下产出的中间表名，供后续步骤引用
    """
    step_index: int
    step_name: str
    rule_name: str
    config: Dict[str, Any] = field(default_factory=dict)
    mode: str = "validate"          # "validate" | "transform"
    input_tables: List[str] = field(default_factory=list)
    output_table: Optional[str] = None


# ──────────────────────────────────────────────
# ChainResult — 链的执行结果
# ──────────────────────────────────────────────

@dataclass
class ChainResult:
    """整条链执行完毕后的汇总结果"""
    chain_name: str
    steps: List[ChainStep]
    step_results: List[Optional[RuleResult]]
    final_dataframes: Dict[str, pd.DataFrame] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        for r in self.step_results:
            if r is not None and r.status == "fail":
                return False
        return True

    @property
    def total_errors(self) -> int:
        return sum(
            r.failed_rows
            for r in self.step_results
            if r is not None and r.status == "fail"
        )

    def summary(self) -> str:
        lines = [f"校验链: {self.chain_name}"]
        for i, (step, sr) in enumerate(zip(self.steps, self.step_results)):
            icon = "✅" if sr and sr.is_pass else "❌" if sr and sr.status == "fail" else "⚠️"
            detail = sr.summary if sr else "未执行"
            lines.append(f"  {icon} 步骤 {i+1} [{step.step_name}]: {detail}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# ChainValidator — 链式调度器
# ──────────────────────────────────────────────

class ChainValidator:
    """链式校验的执行引擎。

    用法:
        chain = ChainValidator("道具校验链")

        # 注册输入表
        chain.register_table("道具表", df_items)
        chain.register_table("掉落表", df_drops)

        # 添加步骤
        chain.add_step(ChainStep(1, "非空检查", "not_null",
            config={"table": "道具表", "columns": ["id", "name"]}))

        chain.add_step(ChainStep(2, "外键检查", "foreign_key",
            config={"source_table": "掉落表", "source_column": "item_id",
                    "target_table": "道具表", "target_column": "id"}))

        # 执行
        result = chain.run()
        print(result.summary())
    """

    def __init__(self, name: str = "unnamed_chain"):
        self.name = name
        self.steps: List[ChainStep] = []
        self._table_cache: Dict[str, pd.DataFrame] = {}   # {表名: DataFrame}

    # ── 表注册 ──

    def register_table(self, name: str, df: pd.DataFrame):
        """注册一张表到链内缓存（可以是文件名或逻辑名）。"""
        self._table_cache[name] = df

    def register_tables_from_files(self, file_map: Dict[str, str]):
        """批量从文件加载并注册。

        Args:
            file_map: {"逻辑表名": "文件路径"}
        """
        for name, path in file_map.items():
            self._table_cache[name] = TableLoader.load(path)

    # ── 步骤管理 ──

    def add_step(self, step: ChainStep):
        """追一个步骤到链尾。"""
        self.steps.append(step)

    def add_step_simple(
        self,
        name: str,
        rule_name: str,
        config: dict,
        mode: str = "validate",
    ):
        """快捷添加一个步骤（自动分配序号）。"""
        idx = len(self.steps) + 1
        self.steps.append(ChainStep(
            step_index=idx,
            step_name=name,
            rule_name=rule_name,
            config=config,
            mode=mode,
        ))

    # ── 表解析 ──

    def _resolve_table(self, table_ref: str) -> pd.DataFrame:
        """解析表引用：先在缓存中找，再尝试作为文件路径加载。"""
        # 1. 缓存命中
        if table_ref in self._table_cache:
            return self._table_cache[table_ref]

        # 2. 尝试作为文件路径
        path = Path(table_ref)
        if path.exists() and path.suffix.lower() in (".xlsx", ".xls", ".csv"):
            df = TableLoader.load(str(path))
            self._table_cache[path.stem] = df
            return df

        # 3. 尝试在工作目录下找
        cwd_path = Path.cwd() / table_ref
        if cwd_path.exists():
            df = TableLoader.load(str(cwd_path))
            self._table_cache[cwd_path.stem] = df
            return df

        raise KeyError(
            f"无法解析表引用 '{table_ref}'：不在缓存中，也不是有效的文件路径。"
            f" 缓存中的表: {list(self._table_cache.keys())}"
        )

    # ── 步骤执行 ──

    def execute_step(self, step: ChainStep) -> Optional[RuleResult]:
        """执行单个步骤。"""
        rule: Optional[BaseRule] = registry.get(step.rule_name)
        if rule is None:
            return RuleResult(
                rule_name=step.rule_name,
                status="error",
                summary=f"规则 '{step.rule_name}' 未注册。可用规则: {[r['name'] for r in registry.list_all()]}",
            )

        try:
            if step.mode == "validate":
                return self._execute_validate(step, rule)
            elif step.mode == "transform":
                return self._execute_transform(step, rule)
            else:
                return RuleResult(
                    rule_name=step.rule_name,
                    status="error",
                    summary=f"未知的执行模式: {step.mode}",
                )
        except Exception as e:
            import traceback
            return RuleResult(
                rule_name=step.rule_name,
                status="error",
                summary=f"执行异常: {e}\n{traceback.format_exc(limit=3)}",
            )

    def _execute_validate(self, step: ChainStep, rule: BaseRule) -> RuleResult:
        """执行校验模式"""
        # 确定主表
        table_ref = step.config.get("table") or step.config.get("source_table")
        if not table_ref and step.input_tables:
            table_ref = step.input_tables[0]
        if not table_ref:
            return RuleResult(rule_name=step.rule_name, status="error",
                              summary="未指定校验表（config.table 或 config.source_table）")

        df = self._resolve_table(table_ref)

        # 如果 config 中有 target_table 引用，先 resolve 再传入
        config = dict(step.config)
        # 解析常见的目标表引用参数
        for key in ("target_df", "expected_df", "other_df", "target_table"):
            if key in config and isinstance(config[key], str):
                try:
                    resolved = self._resolve_table(config[key])
                    # 同时填充规则预期的 key
                    if key == "target_table":
                        config["target_df"] = resolved
                    else:
                        config[key] = resolved
                except KeyError:
                    pass  # 保持字符串，让规则内部处理

        return rule.validate(df, **config)

    def _execute_transform(self, step: ChainStep, rule: BaseRule) -> RuleResult:
        """执行转换模式"""
        # 收集所有输入表
        dfs = {}
        for ref in step.input_tables:
            try:
                dfs[ref] = self._resolve_table(ref)
            except KeyError:
                pass

        # 也把 config 中的文件引用 resolve
        config = dict(step.config)
        for key in ("source", "target_df", "expected_df", "other_df"):
            if key in config and isinstance(config[key], str):
                try:
                    dfs[config[key]] = self._resolve_table(config[key])
                except KeyError:
                    pass

        result_df = rule.transform(dfs, **config)

        # 如果指定了 output_table，缓存结果供后续步骤使用
        if step.output_table and isinstance(result_df, pd.DataFrame):
            self._table_cache[step.output_table] = result_df

        return RuleResult(
            rule_name=step.rule_name,
            status="pass",
            total_rows=len(result_df) if isinstance(result_df, pd.DataFrame) else 0,
            transformed_df=result_df if isinstance(result_df, pd.DataFrame) else None,
            summary=(
                f"生成表 '{step.output_table}': "
                f"{len(result_df)} 行 x {len(result_df.columns)} 列"
                if isinstance(result_df, pd.DataFrame)
                else "转换完成"
            ),
        )

    # ── 整条链执行 ──

    def run(self) -> ChainResult:
        """依次执行链中的全部步骤。"""
        step_results: List[Optional[RuleResult]] = []
        for step in self.steps:
            result = self.execute_step(step)
            step_results.append(result)

        return ChainResult(
            chain_name=self.name,
            steps=self.steps,
            step_results=step_results,
            final_dataframes=self._table_cache,
        )