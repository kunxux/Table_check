"""
配置加载器
==========
从 JSON 配置文件加载校验链，支持文件引用和参数解析。
"""

import json
from pathlib import Path
from typing import Dict, List, Any

from ..core.chain_engine import ChainStep, ChainValidator
from ..core.table_loader import TableLoader


class ConfigLoader:
    """从 JSON 配置文件加载校验链

    JSON 配置结构示例:
    {
      "name": "道具掉落校验",
      "inputs": { "道具表": "items.xlsx", "掉落表": "drops.xlsx" },
      "chain": [
        {
          "step": 1,
          "name": "ID非空检查",
          "rule": "not_null",
          "mode": "validate",
          "config": { "table": "道具表", "columns": ["id", "name"] }
        },
        {
          "step": 2,
          "name": "外键检查",
          "rule": "foreign_key",
          "mode": "validate",
          "config": {
            "source_table": "掉落表",
            "source_column": "item_id",
            "target_table": "道具表",
            "target_column": "id"
          }
        }
      ]
    }
    """

    REQUIRED_TOP = ["name", "chain"]

    @staticmethod
    def validate(config: dict) -> List[str]:
        """校验配置文件完整性，返回错误列表。"""
        errors = []

        for field in ConfigLoader.REQUIRED_TOP:
            if field not in config:
                errors.append(f"顶层缺少必要字段: '{field}'")

        if "chain" in config:
            chain = config["chain"]
            if not isinstance(chain, list) or len(chain) == 0:
                errors.append("'chain' 必须是非空数组")
            else:
                for i, step in enumerate(chain):
                    if "rule" not in step:
                        errors.append(f"chain[{i}] 缺少 'rule' 字段")
                    mode = step.get("mode", "validate")
                    if mode not in ("validate", "transform"):
                        errors.append(f"chain[{i}] mode 必须是 'validate' 或 'transform'")

        return errors

    @staticmethod
    def load(config_path: str) -> ChainValidator:
        """从 JSON 文件加载并构建 ChainValidator。

        Args:
            config_path: JSON 配置文件路径

        Returns:
            已装配好全部步骤的 ChainValidator（尚未执行）
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 校验
        errors = ConfigLoader.validate(config)
        if errors:
            raise ValueError("配置文件有误:\n  - " + "\n  - ".join(errors))

        chain = ChainValidator(name=config["name"])

        # 加载输入表
        inputs = config.get("inputs", {})
        for name, file_path in inputs.items():
            resolved = _resolve_path(file_path, path.parent)
            df = TableLoader.load(resolved)
            chain.register_table(name, df)
            print(f"   📂 加载 [{name}] ← {resolved}  ({len(df)} 行)")

        # 构建链步骤
        for step_cfg in config["chain"]:
            step = ChainStep(
                step_index=step_cfg.get("step", 0),
                step_name=step_cfg.get("name", f"步骤{step_cfg.get('step',0)}"),
                rule_name=step_cfg["rule"],
                config=_resolve_file_refs(step_cfg.get("config", {}), path.parent),
                mode=step_cfg.get("mode", "validate"),
                input_tables=step_cfg.get("input_tables", []),
                output_table=step_cfg.get("output_table"),
            )
            chain.add_step(step)

        return chain

    @staticmethod
    def load_from_dict(config: dict) -> ChainValidator:
        """直接从 dict 构建 ChainValidator（供编程调用，不走 JSON 文件）。"""
        errors = ConfigLoader.validate(config)
        if errors:
            raise ValueError("配置有误:\n  - " + "\n  - ".join(errors))

        chain = ChainValidator(name=config["name"])

        inputs = config.get("inputs", {})
        for name, file_path in inputs.items():
            df = TableLoader.load(file_path)
            chain.register_table(name, df)

        for step_cfg in config["chain"]:
            step = ChainStep(
                step_index=step_cfg.get("step", 0),
                step_name=step_cfg.get("name", ""),
                rule_name=step_cfg["rule"],
                config=step_cfg.get("config", {}),
                mode=step_cfg.get("mode", "validate"),
                input_tables=step_cfg.get("input_tables", []),
                output_table=step_cfg.get("output_table"),
            )
            chain.add_step(step)

        return chain


def _resolve_path(file_path: str, base_dir: Path) -> str:
    """将相对路径解析为绝对路径。"""
    p = Path(file_path)
    if p.is_absolute():
        return str(p)
    resolved = base_dir / p
    if resolved.exists():
        return str(resolved)
    # 尝试当前目录
    cwd_resolved = Path.cwd() / p
    if cwd_resolved.exists():
        return str(cwd_resolved)
    return file_path  # 原样返回，让调用方报错


def _resolve_file_refs(config: dict, base_dir: Path) -> dict:
    """将配置中字符串值的文件路径解析出来（用于 target_df 等字段）。"""
    result = {}
    file_keys = {"target_df", "expected_df", "other_df"}

    for key, value in config.items():
        if key in file_keys and isinstance(value, str):
            resolved = _resolve_path(value, base_dir)
            result[key] = resolved
            result[f"{key}_name"] = Path(resolved).stem
        else:
            result[key] = value

    return result