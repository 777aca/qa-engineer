"""每项检查使用独立浏览器上下文，保留失败、阻塞与未覆盖状态。"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Browser, Route
from .common import CheckResult, CheckSpec, Finding, Outcome, ScanContext, attach_listeners, dump_context, viewport_for
from .redaction import Redactor
from .scenarios import origin


@dataclass
class RunOptions:
    allow_submit: bool = False
    allow_security_tests: bool = False
    storage_state: str | None = None
    ready_selector: str | None = None
    trace: bool = False
    ignore_https_errors: bool = False
    timeout_ms: int = 10000
    allowed_origins: set[str] = field(default_factory=set)


@dataclass
class RunReport:
    checks: list[CheckResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        counts = Counter(item.result for item in self.checks)
        return {"total": len(self.checks), "counts": dict(counts),
                "completed": sum(counts[key] for key in ("Pass", "Fail", "NeedsReview")),
                "exit_code": self.exit_code()}

    def exit_code(self) -> int:
        if not self.checks or any(item.result in ("Blocked", "Error") for item in self.checks):
            return 2
        if any(item.result in ("Fail", "NeedsReview") for item in self.checks):
            return 1
        return 0 if any(item.result == "Pass" for item in self.checks) else 2


def execute_checks(browser: Browser, url: str, platform: str, out_dir: Path,
                   specs: list[CheckSpec], options: RunOptions, redactor: Redactor) -> RunReport:
    report = RunReport()
    unavailable: str | None = None
    allowed = options.allowed_origins or {origin(url)}
    for spec in specs:
        started = time.monotonic()
        ctx: ScanContext | None = None
        browser_context = None
        loaded = False
        outcome = Outcome("Error", "检查未完成")
        try:
            if unavailable:
                outcome = Outcome("Blocked", "目标环境不可用，依赖检查未执行")
            else:
                kwargs = dict(viewport=viewport_for(platform), ignore_https_errors=options.ignore_https_errors,
                              service_workers="block")
                if platform == "mobile":
                    kwargs.update(is_mobile=True, has_touch=True, device_scale_factor=2,
                                  user_agent=f"Mozilla/5.0 (Linux; Android 13; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser.version} Mobile Safari/537.36")
                if options.storage_state:
                    kwargs["storage_state"] = options.storage_state
                browser_context = browser.new_context(**kwargs)
                browser_context.set_default_timeout(options.timeout_ms)
                if options.trace:
                    browser_context.tracing.start(screenshots=False, snapshots=True, sources=False)
                page = browser_context.new_page()
                ctx = ScanContext(url, spec.level, platform, out_dir, page, browser_context,
                                  redactor=redactor, check_id=spec.id, ready_selector=options.ready_selector)

                def guard(route: Route) -> None:
                    request = route.request
                    try:
                        outside = (request.is_navigation_request() or request.method not in ("GET", "HEAD", "OPTIONS")) and origin(request.url) not in allowed
                    except ValueError:
                        outside = True
                    writing = request.method not in ("GET", "HEAD", "OPTIONS") and not options.allow_submit
                    if outside or writing:
                        ctx.blocked_requests.append("超出域名范围的导航或写入请求" if outside else "未授权的非只读请求")
                        route.abort()
                    else:
                        route.continue_()

                browser_context.route("**/*", guard)
                attach_listeners(ctx)
                ctx.goto(options.timeout_ms)
                loaded = True
                if spec.applies is not None and not spec.applies(ctx):
                    outcome = Outcome("Skipped", "当前页面不适用此检查")
                elif spec.security and not options.allow_security_tests:
                    outcome = Outcome("Blocked", "主动安全探针需要已授权范围及 --allow-security-tests")
                elif spec.active and not options.allow_submit:
                    outcome = Outcome("Blocked", "交互场景需要已授权范围及 --allow-submit")
                else:
                    outcome = spec.run(ctx)
                if not isinstance(outcome, Outcome):
                    raise TypeError("检查必须返回明确的 Outcome，不允许以 None 表示通过")
        except AssertionError as exc:
            outcome = Outcome("Fail" if loaded else "Error", redactor.text(str(exc)))
            if ctx and loaded:
                ctx.record(id=f"BUG-{spec.id}", title=spec.title + "：断言未满足", category="ASSERT", module=spec.module,
                           severity="S2", priority="P1", status="已确认", steps=spec.steps,
                           expected="；".join(spec.expected), actual=outcome.reason,
                           evidence=[{"type": "assertion", "content": outcome.reason}])
        except Exception as exc:
            outcome = Outcome("Error", f"{type(exc).__name__}: {redactor.text(str(exc))}")
        finally:
            if ctx:
                if ctx.blocked_requests:
                    outcome = Outcome("Blocked", "；".join(sorted(set(ctx.blocked_requests))))
                    ctx.findings.clear()
                if not loaded and outcome.status in ("Error", "Blocked"):
                    unavailable = outcome.reason
                if outcome.status in ("Fail", "Error", "NeedsReview"):
                    ctx.shot("result")
                if any(item["type"] == "capture_error" for item in ctx.evidence):
                    outcome = Outcome("Error", "所需截图采集失败，保留其他已取得的证据")
                try:
                    dump_context(ctx)
                except OSError:
                    outcome = Outcome("Error", "证据文件写入失败")
                if options.trace:
                    try:
                        if outcome.status in ("Fail", "Error", "NeedsReview"):
                            private = out_dir / "private-traces"
                            private.mkdir(exist_ok=True)
                            browser_context.tracing.stop(path=str(private / f"{spec.id}.zip"))
                        else:
                            browser_context.tracing.stop()
                    except Exception:
                        outcome = Outcome("Error", "Trace 保存失败")
                for finding in ctx.findings:
                    finding.steps = finding.steps or list(spec.steps)
                    finding.expected = finding.expected or "；".join(spec.expected)
                report.findings.extend(ctx.findings)
            if browser_context is not None:
                try:
                    browser_context.close()
                except Exception:
                    outcome = Outcome("Error", "浏览器上下文清理失败")
            report.checks.append(CheckResult(
                id=f"{spec.id}-{platform}", title=spec.title, module=spec.module,
                level=spec.level, platform=platform, result=outcome.status, actual=redactor.text(outcome.reason),
                steps=spec.steps, expected=spec.expected, preconditions=spec.preconditions,
                linked_bug=[finding.id for finding in ctx.findings] if ctx else [],
                evidence=ctx.evidence if ctx else [], duration_ms=int((time.monotonic() - started) * 1000),
            ))
    return report
