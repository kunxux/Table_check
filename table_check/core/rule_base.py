"""
规则基类与注册中心
==================
所有校验规则继承 BaseRule，通过 RuleRegistry 统一注册管理。
每个规则有两个核心方法：validate（校验）和 transform（数据转换）。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd


# ──────────────────────────────────────────────
# RuleResult — 规则执行结果
# ──────────────────────────────────────────────

@dataclass
class RuleResult:
    """单条规则的执行结果

    Attributes:
        rule_name: 规则名称（与注册名一致）
        status: 'pass' / 'fail' / 'error'
        total_rows: 涉及的总行数
        passed_rows: 通过的行数
        failed_rows: 失败的行数
        errors: 错误详情列表，每条是一个 dict
        transformed_df: transform 模式下的输出 DataFrame
        summary: 一行可读的摘要
    """
    rule_name: str
    status: str = "pass"
    total_rows: int = 0
    passed_rows: int = 0
    failed_rows: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    transformed_df: Optional[pd.DataFrame] = None
    summary: str = ""

    @property
    def is_pass(self) -> bool:
        return self.status == "pass"

    def to_dataframe(self) -> pd.DataFrame:
        """将内置的 errors 列表转成 DataFrame，方便写 Excel 报告"""
        if not self.errors:
            return pd.DataFrame()
        return pd.DataFrame(self.errors)


# ──────────────────────────────────────────────
# BaseRule — 规则基类
# ──────────────────────────────────────────────

class BaseRule:
    """所有校验规则的抽象基类。

    子类只需提供:
      - name / description / category 三个类属性
      - validate(df, **params) → RuleResult
      - transform(df, **params) → pd.DataFrame（可选，仅聚合/清洗类规则需要）
    """

    name: str = "base_rule"
    description: str = "未定义说明"
    category: str = "通用"  # 原子校验 | 表内校验 | 跨表校验 | 聚合 | 对比

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        """校验入口。传入 DataFrame 和配置参数，返回 RuleResult。"""
        raise NotImplementedError(f"{self.name}.validate() 未实现")

    def transform(self, dfs: dict, **params) -> pd.DataFrame:
        """数据转换入口。传入 {"表名": DataFrame} 字典，返回新的 DataFrame。

        注意：参数签名与 validate 不同 —— transform 接收多张表。
        """
        raise NotImplementedError(f"{self.name}.transform() 未实现")

    def get_config_schema(self) -> Dict[str, Any]:
        """返回规则所需配置参数的 JSON Schema 描述，供 UI 自动生成表单。"""
        return {}

    def __repr__(self):
        return f"<Rule {self.name}: {self.description}>"


# ──────────────────────────────────────────────
# RuleRegistry — 规则注册中心（单例）
# ──────────────────────────────────────────────

class RuleRegistry:
    """全局规则注册中心，单例模式。

    所有规则通过 import 时自动调用 register() 注册进来，
    后续代码通过 registry.get(name) 按名查找。
    """

    def __init__(self):
        self._rules: Dict[str, BaseRule] = {}

    def register(self, rule: BaseRule) -> None:
        """注册一条规则。重复注册会覆盖旧定义。"""
        self._rules[rule.name] = rule

    def get(self, name: str) -> Optional[BaseRule]:
        """按名称获取规则实例。"""
        return self._rules.get(name)

    def list_all(self) -> List[Dict[str, str]]:
        """列出已注册的全部规则（名称、说明、分类）。"""
        return [
            {"name": r.name, "description": r.description, "category": r.category}
            for r in self._rules.values()
        ]

    def list_by_category(self, category: str) -> List[Dict[str, str]]:
        """按分类列出规则。"""
        return [
            {"name": r.name, "description": r.description}
            for r in self._rules.values()
            if r.category == category
        ]

    def get_categories(self) -> List[str]:
        """获取所有规则分类。"""
        seen = set()
        cats = []
        for r in self._rules.values():
            if r.category not in seen:
                seen.add(r.category)
                cats.append(r.category)
        return cats

    def __len__(self):
        return len(self._rules)

    def __contains__(self, name: str) -> bool:
        return name in self._rules


# 全局单例
registry = RuleRegistry()