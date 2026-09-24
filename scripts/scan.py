"""按档位与平台执行页面检查和声明式业务场景，并导出实际覆盖记录。

退出码：0=已执行检查通过；1=存在失败或待复核项；2=输入/环境错误、阻塞或未执行。
仅运行内置规则不能证明完成业务闭环；L1+ 需要 --config 中的业务场景。
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import json
from dataclasses import asdict
from pathlib import Path
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("缺少 Playwright，请安装 requirements.txt 和 Chromium 浏览器。", file=sys.stderr)
    raise SystemExit(2)

from data_contract import DataError
from scan_lib.common import CheckResult, CheckSpec, Outcome, write_json
from scan_lib.redaction import Redactor
from scan_lib.registry import checks_for_level
from scan_lib.runner import RunOptions, RunReport, execute_checks
from scan_lib.scenarios import load_scenarios


def run_single(url: str, level: str, platform: str, out_dir: Path,
               options: RunOptions | None = None, scenarios: list[CheckSpec] | None = None,
               redactor: Redactor | None = None) -> RunReport:
    options = options or RunOptions()
    redactor = redactor or Redactor()
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = list(checks_for_level(level)) + list(scenarios or [])
    if level != "L0" and not scenarios:
        specs.append(CheckSpec("business-coverage", "业务主流程覆盖", "L1",
                               lambda ctx: Outcome("Blocked", "未配置业务场景，不能声称完成主流程或闭环")))
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                report = execute_checks(browser, url, platform, out_dir, specs, options, redactor)
            finally:
                browser.close()
    except Exception as exc:
        report = RunReport(checks=[CheckResult(
            id=f"environment-{platform}", title="浏览器启动或运行环境", module="环境",
            level=level, platform=platform, result="Error",
            actual=f"{type(exc).__name__}: {redactor.text(str(exc))}",
            steps=["启动浏览器"], expected=["浏览器可以正常执行检查"],
        )])
    write_json(out_dir / "findings.json", [asdict(item) for item in report.findings], redactor)
    write_json(out_dir / "checks.json", [asdict(item) for item in report.checks], redactor)
    write_json(out_dir / "summary.json", report.summary(), redactor)
    return report


def export_report(report: RunReport, url: str, level: str, platform: str,
                  root: Path, redactor: Redactor) -> None:
    import yaml
    from cases_to_xlsx import build_workbook as cases_workbook
    from bugs_to_xlsx import build_workbook as bugs_workbook

    metadata = {"schema_version": 1, "project": "Web 探索测试", "target": redactor.text(url), "mode": "explore-url",
                "level": level, "platform": platform, "explorer": "qa-engineer",
                "scanned_at": dt.datetime.now().astimezone().isoformat()}
    bugs = redactor.clean({**metadata, "bugs": [asdict(item) for item in report.findings]})
    cases = redactor.clean({**metadata, "cases": [asdict(item) for item in report.checks]})
    write_json(root / "summary.json", report.summary(), redactor)
    for name, data in (("bugs", bugs), ("test-cases", cases)):
        write_json(root / f"{name}.json", data, redactor)
        (root / f"{name}.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    cases_workbook(cases, "standard").save(root / "test-cases.xlsx")
    bugs_workbook(bugs).save(root / "bug-report.xlsx")


def main() -> int:
    parser = argparse.ArgumentParser(description="Web 检查与业务场景执行；默认 L2 / PC")
    parser.add_argument("--url", required=True)
    parser.add_argument("--level", default="L2", choices=["L0", "L1", "L2", "L3", "L4"])
    parser.add_argument("--platform", default="pc", choices=["pc", "mobile", "both"])
    parser.add_argument("--out-dir", help="默认 samples/out/scan-<时间戳>")
    parser.add_argument("--config", help="声明式业务场景 YAML/JSON")
    parser.add_argument("--storage-state", help="本地登录态文件；每项检查独立加载")
    parser.add_argument("--allow-submit", action="store_true", help="在已授权范围执行交互和非只读请求")
    parser.add_argument("--allow-security-tests", action="store_true", help="在已授权范围执行主动安全探针")
    parser.add_argument("--trace", action="store_true", help="保存失败 Trace（含原始 DOM/网络数据，仅本地保管）")
    parser.add_argument("--ignore-https-errors", action="store_true", help="显式允许测试环境无效证书")
    parser.add_argument("--timeout-ms", type=int, default=10000)
    args = parser.parse_args()
    redactor = Redactor([os.environ.get(name, "") for name in ("TEST_USER", "TEST_PASS")])
    try:
        if not 1 <= args.timeout_ms <= 120000:
            raise DataError("--timeout-ms 必须介于 1 和 120000")
        config = load_scenarios(args.config, args.url, args.level)
        for name in config.secret_envs:
            redactor.remember(os.environ.get(name, ""))
        if args.storage_state and not Path(args.storage_state).is_file():
            raise DataError("--storage-state 文件不存在")
        if args.storage_state:
            try:
                state = json.loads(Path(args.storage_state).read_text(encoding="utf-8-sig"))
                for cookie in state.get("cookies", []):
                    redactor.remember(cookie["value"])
                for entry in state.get("origins", []):
                    for item in entry.get("localStorage", []):
                        redactor.remember(item["value"])
            except (ValueError, TypeError, AttributeError, KeyError):
                raise DataError("--storage-state 不是合法的浏览器登录态文件") from None
        options = RunOptions(
            allow_submit=args.allow_submit, allow_security_tests=args.allow_security_tests,
            storage_state=args.storage_state, ready_selector=config.ready_selector,
            trace=args.trace, ignore_https_errors=args.ignore_https_errors,
            timeout_ms=args.timeout_ms, allowed_origins=config.allowed_origins,
        )
        root = Path(args.out_dir or f"samples/out/scan-{dt.datetime.now():%Y%m%d-%H%M%S-%f}").resolve()
        root.mkdir(parents=True, exist_ok=True)
        combined = RunReport()
        for platform in (["pc", "mobile"] if args.platform == "both" else [args.platform]):
            report = run_single(args.url, args.level, platform, root / platform, options, config.checks, redactor)
            combined.checks.extend(report.checks)
            combined.findings.extend(report.findings)
            print(f"{platform}: {report.summary()}")
        export_report(combined, args.url, args.level, args.platform, root, redactor)
        print(f"输出：{root}")
        print("请结合 summary.json 中的状态与覆盖记录判断结果，零条缺陷不等于全部通过。")
        return combined.exit_code()
    except (DataError, OSError, ImportError) as exc:
        print(f"执行未完成：{redactor.text(str(exc))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
