#!/usr/bin/env python3
"""
new_test_case.py —— 生成标准化测试用例 Markdown 骨架

用法：
    python new_test_case.py <功能模块> <用例标题> [--priority P0|P1|P2|P3] [--output FILE]

示例：
    python new_test_case.py 登录 "正确邮箱密码登录成功" --priority P0
    python new_test_case.py 订单 "已完成订单不可再申请退款" --priority P1 --output tc-order-refund.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys


TEMPLATE = """# TC-{module_slug}-{serial} {title}

- **优先级**：{priority}
- **所属模块**：{module}
- **创建时间**：{created_at}
- **关联需求**：<!-- 填写 PRD/JIRA 编号 -->

## 前置条件

- <!-- 例如：已开通测试账号 test@example.com -->
- <!-- 例如：账户余额 > 100 元 -->

## 测试步骤

1. <!-- 一步一个动作 -->
2.
3.

## 预期结果

- <!-- 具体、可观察、可断言 -->
-

## 实际结果

<!-- 执行时填写；通过可留空 -->

## 结果

- [ ] Pass
- [ ] Fail
- [ ] Blocked

## 备注

<!-- 回归版本、特殊环境、限制条件等 -->
"""


def slugify(text: str) -> str:
    """把功能模块名转为安全的 slug。中文保留，用连字符分隔。"""
    text = text.strip()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^\w\u4e00-\u9fff-]", "", text)
    return text or "module"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成测试用例 Markdown 骨架")
    parser.add_argument("module", help="功能模块名，如 登录 / 订单")
    parser.add_argument("title", help="用例一句话标题")
    parser.add_argument("--priority", choices=["P0", "P1", "P2", "P3"], default="P1")
    parser.add_argument("--serial", default="001", help="用例编号，默认 001")
    parser.add_argument("--output", default=None, help="输出文件路径，默认打印到 stdout")
    args = parser.parse_args()

    content = TEMPLATE.format(
        module=args.module,
        module_slug=slugify(args.module),
        serial=args.serial,
        title=args.title,
        priority=args.priority,
        created_at=dt.date.today().isoformat(),
    )

    if args.output:
        path = pathlib.Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"已生成：{path}")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
