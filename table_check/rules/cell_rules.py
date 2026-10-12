"""
第1层 · 原子校验规则
====================
对表格的单元格进行逐格检查：
  - not_null: 非空校验 → 漏填检测
  - type_check: 类型校验 → 类型错误检测
  - range_check: 范围校验 → 数值越界检测
  - enum_check: 枚举校验 → 非法枚举值检测
  - regex_check: 正则校验 → 格式错误检测
"""

import re
import pandas as pd
from ..core.rule_base import BaseRule, RuleResult, registry


# ═══════════════════════════════════════════════
# 1. 非空校验
# ═══════════════════════════════════════════════

class NotNullRule(BaseRule):
    name = "not_null"
    description = "非空校验：检查指定列是否存在空值（漏填检测）"
    category = "原子校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        columns = params.get("columns", list(df.columns))
        errors = []

        for col in columns:
            if col not in df.columns:
                continue
            null_mask = df[col].isna()
            for idx in df[null_mask].index:
                errors.append({
                    "行号": int(idx) + 2,
                    "列名": col,
                    "当前值": "(空)",
                    "错误类型": "漏填",
                    "规则说明": f"[{col}] 不能为空",
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
            summary=f"检查 {len(columns)} 列，发现 {failed} 个空值",
        )


registry.register(NotNullRule())


# ═══════════════════════════════════════════════
# 2. 类型校验
# ═══════════════════════════════════════════════

class TypeRule(BaseRule):
    name = "type_check"
    description = "类型校验：检查指定列的数据类型是否符合预期（int / float / str / bool）"
    category = "原子校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        column_types = params.get("column_types", {})  # {"列名": "int"}
        errors = []

        for col, expected in column_types.items():
            if col not in df.columns:
                continue
            for idx, val in df[col].items():
                if pd.isna(val):
                    continue  # 空值交给 not_null
                if not self._check_type(val, expected):
                    errors.append({
                        "行号": int(idx) + 2,
                        "列名": col,
                        "当前值": str(val),
                        "期望类型": expected,
                        "错误类型": "类型错误",
                        "规则说明": f"[{col}] 应为 {expected} 类型",
                    })

        failed = len(errors)
        total = len(df) * len(column_types)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=total,
            passed_rows=total - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"检查 {len(column_types)} 列类型，发现 {failed} 个类型错误",
        )

    @staticmethod
    def _check_type(val, expected: str) -> bool:
        try:
            if expected in ("int", "integer"):
                int(val)
            elif expected in ("float", "number"):
                float(val)
            elif expected in ("str", "string"):
                str(val)
            elif expected in ("bool", "boolean"):
                s = str(val).lower().strip()
                if s not in ("true", "false", "1", "0", "yes", "no"):
                    return False
            return True
        except (ValueError, TypeError):
            return False


registry.register(TypeRule())


# ═══════════════════════════════════════════════
# 3. 范围校验
# ═══════════════════════════════════════════════

class RangeRule(BaseRule):
    name = "range_check"
    description = "范围校验：检查数值列是否在 [min, max] 范围内"
    category = "原子校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        ranges = params.get("ranges", {})
        # {"列名": {"min": 1, "max": 999999}}
        errors = []

        for col, bounds in ranges.items():
            if col not in df.columns:
                continue
            low = bounds.get("min")
            high = bounds.get("max")

            for idx, val in df[col].items():
                if pd.isna(val):
                    continue
                try:
                    num = float(val)
                    if low is not None and num < low:
                        errors.append({
                            "行号": int(idx) + 2, "列名": col,
                            "当前值": val, "范围": f"[{low}, {high}]",
                            "错误类型": "超出下限",
                            "规则说明": f"[{col}] 最小值为 {low}，当前 {num}",
                        })
                    elif high is not None and num > high:
                        errors.append({
                            "行号": int(idx) + 2, "列名": col,
                            "当前值": val, "范围": f"[{low}, {high}]",
                            "错误类型": "超出上限",
                            "规则说明": f"[{col}] 最大值为 {high}，当前 {num}",
                        })
                except (ValueError, TypeError):
                    pass  # 非数值交由 type_check

        failed = len(errors)
        total = len(df) * len(ranges)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=total,
            passed_rows=total - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"检查 {len(ranges)} 列范围，发现 {failed} 个超限值",
        )


registry.register(RangeRule())


# ═══════════════════════════════════════════════
# 4. 枚举校验
# ═══════════════════════════════════════════════

class EnumRule(BaseRule):
    name = "enum_check"
    description = "枚举校验：检查列值是否在预定义的合法值列表中"
    category = "原子校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        enums = params.get("enums", {})  # {"列名": [1, 2, 3]}
        errors = []

        for col, allowed in enums.items():
            if col not in df.columns:
                continue
            allowed_set = set(allowed)

            for idx, val in df[col].items():
                if pd.isna(val):
                    continue
                if val not in allowed_set:
                    errors.append({
                        "行号": int(idx) + 2, "列名": col,
                        "当前值": str(val),
                        "允许值": str(allowed[:20]) + ("…" if len(allowed) > 20 else ""),
                        "错误类型": "枚举错误",
                        "规则说明": f"[{col}] 只能在 {allowed[:5]}… 中取值",
                    })

        failed = len(errors)
        total = len(df) * len(enums)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=total,
            passed_rows=total - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"检查 {len(enums)} 列枚举值，发现 {failed} 个异常",
        )


registry.register(EnumRule())


# ═══════════════════════════════════════════════
# 5. 正则校验
# ═══════════════════════════════════════════════

class RegexRule(BaseRule):
    name = "regex_check"
    description = "正则校验：检查列值是否匹配指定正则表达式（如 ID 格式校验）"
    category = "原子校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        patterns = params.get("patterns", {})  # {"列名": "^[A-Z]\\d{4}$"}
        errors = []

        for col, pattern in patterns.items():
            if col not in df.columns:
                continue
            regex = re.compile(pattern)

            for idx, val in df[col].items():
                if pd.isna(val):
                    continue
                if not regex.search(str(val)):
                    errors.append({
                        "行号": int(idx) + 2, "列名": col,
                        "当前值": str(val), "正则": pattern,
                        "错误类型": "格式错误",
                        "规则说明": f"[{col}] 应匹配 {pattern}",
                    })

        failed = len(errors)
        total = len(df) * len(patterns)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=total,
            passed_rows=total - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"检查 {len(patterns)} 列格式，发现 {failed} 个格式错误",
        )


registry.register(RegexRule())