#!/usr/bin/env python3
"""
new_bug_report.py —— 生成规范 Bug 报告 Markdown 骨架

用法：
    python new_bug_report.py "<Bug 标题>" [--severity S1|S2|S3|S4] [--priority P0|P1|P2|P3] [--output FILE]

示例：
    python new_bug_report.py "已完成订单申请退款后页面白屏" --severity S2 --priority P1
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys


TEMPLATE = """# [Bug] {title}

## 基础信息

- **报告人**：<!-- 姓名 -->
- **发现时间**：{found_at}
- **严重度**：{severity}
- **优先级**：{priority}
- **所属模块**：<!-- 下单 / 支付 / 登录 / ... -->
- **关联需求**：<!-- PRD-xxx / JIRA-xxx -->

## 环境

- **被测版本**：<!-- v1.2.3 (git commit abc1234) -->
- **环境**：<!-- staging / https://staging.example.com -->
- **浏览器/设备**：<!-- Chrome 138 / iPhone 15 Pro iOS 18 -->
- **账号**：<!-- test@example.com -->
- **网络**：<!-- WiFi / 4G / 慢网 -->

## 复现步骤

1.
2.
3.

## 期望结果

-

## 实际结果

-

## 必现 / 偶现

- [ ] 必现（N/N）
- [ ] 偶现（描述复现率）

## 附件

- screenshot-01.png
- console.log
- network.har
- backend.log (trace_id=)

## 可能原因（可选，供开发定位参考）

-

## Fix 后建议的验证方式

1.
2.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Bug 报告 Markdown 骨架")
    parser.add_argument("title", help="Bug 一句话标题（在什么条件下、什么功能、什么异常）")
    parser.add_argument("--severity", choices=["S1", "S2", "S3", "S4"], default="S2")
    parser.add_argument("--priority", choices=["P0", "P1", "P2", "P3"], default="P1")
    parser.add_argument("--output", default=None, help="输出文件路径，默认打印到 stdout")
    args = parser.parse_args()

    content = TEMPLATE.format(
        title=args.title,
        severity=args.severity,
        priority=args.priority,
        found_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M %z").strip(),
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
