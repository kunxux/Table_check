"""
报告生成器
==========
将链式校验结果输出为格式化的 Excel 报告。
报告包含:
  - 检查总览 sheet（每步一行，汇总通过/失败/错误数）
  - 错误详情 sheet（每步一个，展示具体的错误行号、列名、当前值）
  - 中间数据 sheet（transform 步骤产出的表）
"""

from pathlib import Path
from typing import List, Optional

import pandas as pd

from .rule_base import RuleResult
from .chain_engine import ChainResult


class ReportGenerator:
    """Excel 报告生成器"""

    # ── 样式常量（供 openpyxl 扩展使用）──
    HEADER_FILL = "4472C4"       # 深蓝背景
    PASS_FILL = "C6EFCE"         # 绿色（通过）
    FAIL_FILL = "FFC7CE"         # 红色（失败）
    ERROR_FILL = "FFEB9C"        # 黄色（异常）

    @staticmethod
    def generate(chain_result: ChainResult, output_path: str) -> str:
        """
        将链执行结果写入一个多 sheet 的 Excel 文件。

        Args:
            chain_result: 链执行结果
            output_path: 输出 xlsx 路径

        Returns:
            归一化后的绝对路径
        """
        output_path = Path(output_path)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # ── Sheet 1: 检查总览 ──
            ReportGenerator._write_summary_sheet(writer, chain_result)
            # ── Sheet 2..N: 每步的错误详情 ──
            ReportGenerator._write_error_sheets(writer, chain_result)
            # ── 中间/最终数据表 ──
            ReportGenerator._write_data_sheets(writer, chain_result)

        return str(output_path.resolve())

    @staticmethod
    def generate_single(result: RuleResult, output_path: str) -> str:
        """生成单规则校验报告（不通过链，直接校验）"""
        output_path = Path(output_path)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # 总览
            summary_data = [{
                "规则名称": result.rule_name,
                "状态": result.status,
                "总行数": result.total_rows,
                "通过行数": result.passed_rows,
                "失败行数": result.failed_rows,
                "摘要": result.summary,
            }]
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="检查总览", index=False)

            # 错误详情
            if result.errors:
                df_errors = result.to_dataframe()
                df_errors.to_excel(writer, sheet_name="错误详情", index=False)

        return str(output_path.resolve())

    # ── 内部方法 ──

    @staticmethod
    def _write_summary_sheet(writer, chain_result: ChainResult):
        """生成总览 sheet"""
        rows = []
        for i, (step, result) in enumerate(
            zip(chain_result.steps, chain_result.step_results)
        ):
            if result is None:
                continue
            rows.append({
                "步骤序号": step.step_index,
                "步骤名称": step.step_name,
                "规则名称": result.rule_name,
                "执行模式": step.mode,
                "状态": result.status,
                "总行数": result.total_rows,
                "通过行数": result.passed_rows if result.status in ("pass", "fail") else "",
                "失败行数": result.failed_rows if result.status == "fail" else 0,
                "摘要": result.summary,
            })

        if rows:
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name="检查总览", index=False)

    @staticmethod
    def _write_error_sheets(writer, chain_result: ChainResult):
        """为每个有错误的步骤生成一个错误详情 sheet"""
        for step, result in zip(chain_result.steps, chain_result.step_results):
            if result is None or not result.errors:
                continue

            df_errors = result.to_dataframe()
            if df_errors.empty:
                continue

            # Excel sheet 名最长 31 个字符
            base = f"步骤{step.step_index}-{step.step_name}"
            sheet_name = _sanitize_sheet_name(base)

            df_errors.to_excel(writer, sheet_name=sheet_name, index=False)

    @staticmethod
    def _write_data_sheets(writer, chain_result: ChainResult):
        """将缓存中的数据表写出（transform 产生的中间表 / 最终表）"""
        for table_name, df in chain_result.final_dataframes.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            sheet_name = _sanitize_sheet_name(f"数据_{table_name}")
            # 限制列数避免 sheet 过大
            df_to_write = df if len(df.columns) <= 50 else df.iloc[:, :50]
            df_to_write.to_excel(writer, sheet_name=sheet_name, index=False)


def _sanitize_sheet_name(name: str) -> str:
    """清洗 Sheet 名，使其符合 Excel 规范（≤31 字符，不包含非法字符）。"""
    # 移除 Excel 不允许的字符
    for ch in r"[]:*?/\\":
        name = name.replace(ch, "-")
    return name[:31]