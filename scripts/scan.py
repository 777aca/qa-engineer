"""通用 Web 探索扫描入口 —— 支持按档位（L0–L4）+ 平台（pc/mobile/both）触发。

用法：
    python scripts/scan.py --url <URL> [--level L0|L1|L2|L3|L4] [--platform pc|mobile|both]
                           [--out-dir samples/out/<name>]

示例：
    # 最快：L0 冒烟
    python scripts/scan.py --url https://example.com --level L0

    # 默认：L2 闭环 + PC
    python scripts/scan.py --url https://example.com

    # 移动端 + 精细
    python scripts/scan.py --url https://m.example.com --level L3 --platform mobile

    # 两个平台都跑一遍（各产出一份 findings.json）
    python scripts/scan.py --url https://example.com --level L2 --platform both

产出：
    <out-dir>/<platform>/findings.json  —— bug 候选
    <out-dir>/<platform>/*.png          —— 截图证据
    <out-dir>/<platform>/network_log.json, console_log.json, page_errors.json, dom_info.json
    <out-dir>/bugs.yaml                 —— 合并后的 Bug 汇总（可喂 bugs_to_xlsx.py）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

from scan_lib.common import (
    ScanContext, attach_listeners, dump_context, viewport_for, MOBILE_UA,
)
from scan_lib.registry import checks_for_level


def run_single(url: str, level: str, platform: str, out_dir: pathlib.Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        kwargs = {"ignore_https_errors": True, "viewport": viewport_for(platform)}
        if platform == "mobile":
            kwargs.update({
                "user_agent": MOBILE_UA,
                "is_mobile": True,
                "has_touch": True,
                "device_scale_factor": 2,
            })
        ctx_b = browser.new_context(**kwargs)
        page = ctx_b.new_page()
        ctx = ScanContext(
            url=url, level=level, platform=platform,
            out_dir=out_dir, page=page, browser_context=ctx_b,
        )
        attach_listeners(ctx)

        for fn in checks_for_level(level):
            name = getattr(fn, "__name__", "<check>")
            try:
                fn(ctx)
            except Exception as e:
                print(f"[WARN] {name} 抛异常：{type(e).__name__}: {e}", file=sys.stderr)

        dump_context(ctx)
        browser.close()
        return [f.__dict__ for f in ctx.findings]


def write_bugs_yaml(all_bugs: list[dict], url: str, level: str, platform: str, path: pathlib.Path):
    data = {
        "project": f"explore-{url.split('//')[-1].split('/')[0]}",
        "target": url,
        "mode": "explore-url",
        "level": level,
        "platform": platform,
        "explorer": "claude-qa",
        "scanned_at": dt.date.today().isoformat(),
        "bugs": all_bugs,
    }
    try:
        import yaml
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    except ImportError:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Web 探索扫描（按档位 + 平台）")
    parser.add_argument("--url", required=True)
    parser.add_argument("--level", default="L2", choices=["L0", "L1", "L2", "L3", "L4"])
    parser.add_argument("--platform", default="pc", choices=["pc", "mobile", "both"])
    parser.add_argument("--out-dir", default=None,
                        help="输出根目录，默认 samples/out/scan-<时间戳>")
    args = parser.parse_args()

    out_root = pathlib.Path(
        args.out_dir
        or f"samples/out/scan-{dt.datetime.now():%Y%m%d-%H%M%S}"
    ).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    platforms = ["pc", "mobile"] if args.platform == "both" else [args.platform]
    all_bugs: list[dict] = []

    for plat in platforms:
        print(f"\n=== 跑 {args.level} / {plat} ===")
        bugs = run_single(args.url, args.level, plat, out_root / plat)
        all_bugs.extend(bugs)
        print(f"  本轮发现 {len(bugs)} 条")

    bugs_yaml = out_root / "bugs.yaml"
    write_bugs_yaml(all_bugs, args.url, args.level, args.platform, bugs_yaml)
    print(f"\n===== 扫描完成 =====")
    print(f"档位：{args.level}    平台：{args.platform}    共发现 {len(all_bugs)} 条")
    print(f"输出根目录：{out_root}")
    print(f"Bug 清单：{bugs_yaml}")
    print(f"生成 Excel：python scripts/bugs_to_xlsx.py {bugs_yaml}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
