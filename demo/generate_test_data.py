"""
测试数据生成器
==============
生成模拟游戏配表数据，用于验证5层校验规则。
生成的表格：
  1. 道具表.xlsx      — 基础道具配置
  2. 掉落表.xlsx      — 怪物掉落配置（含错误数据）
  3. 掉落规划表.xlsx  — 策划的掉落规划（用于对比）
"""

import pandas as pd
from pathlib import Path


def generate(output_dir: str = None):
    """生成全部测试数据。

    Args:
        output_dir: 输出目录，默认为当前脚本所在目录下的 test_data/
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "test_data"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════
    # 1. 道具表（含部分错误：空值、类型错、超范围、重复ID）
    # ═══════════════════════════════════════════
    items = pd.DataFrame({
        "id":       [1001, 1002, 1003,    None, 1005, 1003, 1007, 1008],
        "name":     ["生命药水", "魔法药水", "铁剑", "布甲", None, "短弓", "火球术", "冰霜箭"],
        "type":     [1, 1, 2, 3, 3, 2, 4, 5],          # 5 是非法枚举
        "quality":  [1, 2, 2, 1, 3, "蓝", 1, 2],       # "蓝" 应为 int
        "price":    [100, 200, 500, 800, -100, 600, 300, 0],  # -100 越界
        "level":    [1, 1, 5, 10, 15, 8, 20, 12],
        "desc":     ["恢复HP", "恢复MP", "基础武器", "", None, "远程武器", "火系魔法", "冰系魔法"],
    })

    items.to_excel(output_dir / "道具表.xlsx", index=False, engine="openpyxl")
    print(f"✅ 道具表.xlsx — {len(items)} 行 x {len(items.columns)} 列")

    # ═══════════════════════════════════════════
    # 2. 掉落表（含外键丢失、重复、关联错误）
    # ═══════════════════════════════════════════
    drops = pd.DataFrame({
        "drop_id":      [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "monster_name": ["史莱姆", "哥布林", "骷髅兵", "巨龙", "幽灵", "史莱姆王", "石像鬼", "树精", "哥布林"],
        "item_id":      [1001, 1002, 1003, 9999, 1005, 1001, 1003, None, 8888],  # 9999/8888 外键丢失
        "drop_rate":    [0.5, 0.3, 0.1, 0.05, 0.2, 0.15, 0.08, 0.12, 0.25],
        "min_count":    [1, 1, 1, 1, 2, 1, 1, 1, 3],
        "max_count":    [3, 2, 1, 1, 5, 2, 2, 1, 10],    # 第4行 min>max
        "drop_level":   [1, 2, 5, 50, 10, 3, 8, 7, 12],
    })

    drops.to_excel(output_dir / "掉落表.xlsx", index=False, engine="openpyxl")
    print(f"✅ 掉落表.xlsx — {len(drops)} 行 x {len(drops.columns)} 列")

    # ═══════════════════════════════════════════
    # 3. 掉落规划表（与掉落表有差异，用于 pk_diff）
    # ═══════════════════════════════════════════
    plan = pd.DataFrame({
        "item_id":    [1001, 1002, 1003, 1005, 1007, 1008, 2001],  # 2001规划了但实际没有
        "plan_rate":  [0.6, 0.3, 0.15, 0.2, 0.1, 0.3, 0.05],
        "plan_count": [10, 8, 3, 5, 2, 5, 1],
        "plan_source": ["新手怪", "新手怪", "中级怪", "高级怪", "高级怪", "高级怪", "Boss"],
    })

    plan.to_excel(output_dir / "掉落规划表.xlsx", index=False, engine="openpyxl")
    print(f"✅ 掉落规划表.xlsx — {len(plan)} 行 x {len(plan.columns)} 列")

    print(f"\n📂 测试数据已生成到: {output_dir.resolve()}\n")
    return str(output_dir)


if __name__ == "__main__":
    generate()