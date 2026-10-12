"""
第2层 · 表内校验规则
====================
在同一张表内对不同列进行关系验证和业务逻辑检查：
  - column_compare:   列间比较（A列 >= B列）
  - conditional_req:  条件依赖（A列=X 时 B列必填）
  - unique_check:     唯一性校验
  - composite_key:    组合键唯一校验
"""

import pandas as pd
from ..core.rule_base import BaseRule, RuleResult, registry


# ═══════════════════════════════════════════════
# 1. 列间比较
# ═══════════════════════════════════════════════

class ColumnCompareRule(BaseRule):
    name = "column_compare"
    description = "列间比较：验证同一行中两列的值是否满足指定关系（> / >= / < / <= / == / !=）"
    category = "表内校验"

    # 支持的操作符
    OPS = {
        ">":  lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<":  lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        comparisons = params.get("comparisons", [])
        # [{"left": "max_hp", "op": ">=", "right": "min_hp"}, ...]
        errors = []

        for comp in comparisons:
            left = comp["left"]
            right = comp["right"]
            op = comp.get("op", ">=")
            op_func = self.OPS.get(op)

            if op_func is None:
                continue
            if left not in df.columns or right not in df.columns:
                continue

            for idx, row in df.iterrows():
                a, b = row[left], row[right]
                if pd.isna(a) or pd.isna(b):
                    continue
                if not op_func(a, b):
                    errors.append({
                        "行号": int(idx) + 2,
                        "列名": f"{left} vs {right}",
                        "当前值": f"{left}={a}, {right}={b}",
                        "错误类型": "列间关系错误",
                        "规则说明": f"[{left}] {op} [{right}]，但 {a} {op} {b} 不成立",
                    })

        failed = len(errors)
        total = len(df) * len(comparisons)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=total,
            passed_rows=total - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"检查 {len(comparisons)} 对列关系，发现 {failed} 个错误",
        )


registry.register(ColumnCompareRule())


# ═══════════════════════════════════════════════
# 2. 条件依赖
# ═══════════════════════════════════════════════

class ConditionalRequiredRule(BaseRule):
    name = "conditional_required"
    description = "条件依赖校验：当 A 列满足某个条件时，B/C…列必须已填写"
    category = "表内校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        conditions = params.get("conditions", [])
        # [{"if_column": "type", "if_value": 1, "then_columns": ["name", "desc"]}]
        errors = []

        for cond in conditions:
            if_col = cond["if_column"]
            if_val = cond.get("if_value")
            then_cols = cond.get("then_columns", [])

            if if_col not in df.columns:
                continue

            for idx, row in df.iterrows():
                trigger = row[if_col]

                # 判断触发条件
                triggered = False
                if if_val is not None:
                    triggered = (trigger == if_val)
                else:
                    # 未指定 if_value：只要 A 列非空就触发
                    triggered = not pd.isna(trigger) and trigger != ""

                if not triggered:
                    continue

                for t_col in then_cols:
                    if t_col not in df.columns:
                        continue
                    if pd.isna(row[t_col]) or row[t_col] == "":
                        errors.append({
                            "行号": int(idx) + 2,
                            "列名": t_col,
                            "当前值": "(空)",
                            "触发条件": f"{if_col}={trigger}",
                            "错误类型": "条件必填缺失",
                            "规则说明": f"当 [{if_col}]={trigger} 时，[{t_col}] 必填",
                        })

        failed = len(errors)
        total = len(df) * len(conditions)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=total,
            passed_rows=total - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"检查 {len(conditions)} 个条件依赖，发现 {failed} 个缺失",
        )


registry.register(ConditionalRequiredRule())


# ═══════════════════════════════════════════════
# 3. 唯一性校验
# ═══════════════════════════════════════════════

class UniqueRule(BaseRule):
    name = "unique_check"
    description = "唯一性校验：检查指定列的值是否在全表中唯一（常用于 ID 列）"
    category = "表内校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        columns = params.get("columns", [])
        errors = []

        for col in columns:
            if col not in df.columns:
                continue
            dup_mask = df[col].duplicated(keep=False) & df[col].notna()
            dup_values = set(df.loc[dup_mask, col])

            for val in dup_values:
                dup_rows = df[df[col] == val]
                for idx in dup_rows.index:
                    errors.append({
                        "行号": int(idx) + 2, "列名": col,
                        "当前值": str(val),
                        "出现次数": len(dup_rows),
                        "错误类型": "重复值",
                        "规则说明": f"[{col}] 应唯一，值 '{val}' 出现 {len(dup_rows)} 次",
                    })

        failed = len(errors)
        total = len(df) * len(columns)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=total,
            passed_rows=total - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"检查 {len(columns)} 列唯一性，发现 {failed} 个重复",
        )


registry.register(UniqueRule())


# ═══════════════════════════════════════════════
# 4. 组合键唯一校验
# ═══════════════════════════════════════════════

class CompositeKeyRule(BaseRule):
    name = "composite_key"
    description = "组合键唯一校验：检查多列的组合值是否唯一"
    category = "表内校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        key_columns = params.get("key_columns", [])
        valid_cols = [c for c in key_columns if c in df.columns]

        if not valid_cols:
            return RuleResult(rule_name=self.name, status="pass",
                              summary="未指定有效的组合键列")

        dup_mask = df.duplicated(subset=valid_cols, keep=False)
        errors = []

        for idx in df[dup_mask].index:
            key_vals = {c: df.loc[idx, c] for c in valid_cols}
            errors.append({
                "行号": int(idx) + 2,
                "列名": str(valid_cols),
                "当前值": str(key_vals),
                "错误类型": "组合键重复",
                "规则说明": f"({', '.join(valid_cols)}) 组合应唯一",
            })

        failed = len(errors)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=len(df),
            passed_rows=len(df) - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"检查组合键 {valid_cols}，发现 {failed} 个重复行",
        )


registry.register(CompositeKeyRule())