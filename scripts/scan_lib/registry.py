"""把档位 -> check 列表映射起来，严格递进（Ln 包含 L0..L(n-1)）。"""
from __future__ import annotations

from . import l0_smoke, l1_happy, l2_loop, l3_detail, l4_full

LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4"]

_LEVEL_CHECKS = {
    "L0": l0_smoke.CHECKS,
    "L1": l1_happy.CHECKS,
    "L2": l2_loop.CHECKS,
    "L3": l3_detail.CHECKS,
    "L4": l4_full.CHECKS,
}


def checks_for_level(level: str):
    """返回该档位应执行的 check 列表（含所有下档的 check）。"""
    if level not in LEVEL_ORDER:
        raise ValueError(f"未知档位 {level}")
    merged = []
    for lv in LEVEL_ORDER:
        merged.extend(_LEVEL_CHECKS[lv])
        if lv == level:
            break
    return merged
