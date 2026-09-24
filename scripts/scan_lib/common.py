"""扫描状态、明确的检查结果和经过脱敏的证据采集。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from playwright.sync_api import BrowserContext, Page, expect

from .redaction import Redactor

Status = Literal["Pass", "Fail", "Skipped", "Blocked", "Error", "NeedsReview"]


def viewport_for(platform: str) -> dict[str, int]:
    return {"width": 375, "height": 667} if platform == "mobile" else {"width": 1280, "height": 800}


def responsive_breakpoints(platform: str) -> list[tuple[int, int, str]]:
    return ([(375, 667, "mobile"), (390, 844, "mobile-large"), (768, 1024, "tablet")]
            if platform == "mobile" else [(1280, 800, "pc"), (1920, 1080, "pc-large")])


@dataclass
class Outcome:
    status: Status
    reason: str


@dataclass
class Finding:
    id: str
    title: str
    category: str
    module: str
    severity: str
    priority: str
    status: str = "待验证"
    reproducible: str = "一次"
    steps: list[str] = field(default_factory=list)
    expected: str = ""
    actual: str = ""
    evidence: list[dict[str, object]] = field(default_factory=list)
    suggestion: str = ""
    tags: list[str] = field(default_factory=list)
    level: str = "L2"
    platform: str = "pc"


@dataclass
class CheckResult:
    id: str
    title: str
    module: str
    level: str
    platform: str
    result: Status
    actual: str
    steps: list[str]
    expected: list[str]
    priority: str = "P2"
    preconditions: list[str] = field(default_factory=list)
    linked_bug: list[str] = field(default_factory=list)
    evidence: list[dict[str, object]] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class CheckSpec:
    id: str
    title: str
    level: str
    run: Callable[[ScanContext], Outcome]
    module: str = "页面检查"
    steps: list[str] = field(default_factory=lambda: ["打开目标页面并执行检查"])
    expected: list[str] = field(default_factory=lambda: ["满足本检查描述的可观察行为"])
    preconditions: list[str] = field(default_factory=list)
    active: bool = False
    security: bool = False
    applies: Callable[[ScanContext], bool] | None = None


@dataclass
class ScanContext:
    url: str
    level: str
    platform: str
    out_dir: Path
    page: Page
    browser_context: BrowserContext
    redactor: Redactor = field(default_factory=Redactor)
    check_id: str = "check"
    ready_selector: str | None = None
    findings: list[Finding] = field(default_factory=list)
    network_log: list[dict[str, object]] = field(default_factory=list)
    console_log: list[dict[str, object]] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    evidence: list[dict[str, object]] = field(default_factory=list)
    blocked_requests: list[str] = field(default_factory=list)
    dom_info: dict[str, object] = field(default_factory=dict)

    def record(self, **kwargs) -> None:
        kwargs.setdefault("level", self.level)
        kwargs.setdefault("platform", self.platform)
        kwargs["id"] = f"{kwargs['id']}-{self.platform}"
        if kwargs.get("status") == "已确认" and not kwargs.get("evidence"):
            kwargs["status"] = "待验证"
        self.findings.append(Finding(**kwargs))

    def shot(self, name: str) -> str:
        path = self.out_dir / f"{self.check_id}-{name}.png"
        try:
            self.page.screenshot(path=str(path), full_page=True,
                                 mask=[self.page.locator("input, textarea, [data-qa-sensitive]")]
                                 + [self.page.get_by_text(secret, exact=False) for secret in self.redactor.secrets])
        except Exception:
            self.evidence.append({"type": "capture_error", "content": "截图失败，无图片证据"})
            return ""
        self.evidence.append({"type": "screenshot", "path": str(path)})
        return str(path)

    def goto(self, timeout_ms: int = 15000) -> None:
        response = self.page.goto(self.url, wait_until="domcontentloaded", timeout=timeout_ms)
        if response is not None and response.status >= 400:
            raise TargetUnavailable(f"目标文档返回 HTTP {response.status}")
        expect(self.page.locator(self.ready_selector or "body")).to_be_visible(timeout=timeout_ms)
        self.refresh_dom()

    def refresh_dom(self) -> None:
        self.dom_info = self.page.evaluate(r"""() => ({
            title: document.title,
            visible_text: document.body?.innerText.trim().length || 0,
            inputs: [...document.querySelectorAll('input')].map(i => ({
                type: i.type, name: i.name, placeholder: i.placeholder,
                accessible: !!(i.labels?.length || i.getAttribute('aria-label') ||
                    (i.getAttribute('aria-labelledby') || '').split(/\s+/).some(id => document.getElementById(id)?.textContent.trim()))
            })),
            images_without_alt: [...document.images].filter(i => !i.hasAttribute('alt') &&
                !['presentation', 'none'].includes(i.getAttribute('role')) && i.getAttribute('aria-hidden') !== 'true')
                .map(i => i.src),
            links: [...document.querySelectorAll('a[href]')].slice(0, 100).map(a => ({text: a.innerText, href: a.href})),
            buttons: [...document.querySelectorAll('button')].slice(0, 100).map(b => ({text: b.innerText, disabled: b.disabled}))
        })""")


class TargetUnavailable(RuntimeError):
    pass


def attach_listeners(ctx: ScanContext) -> None:
    ctx.page.on("console", lambda message: ctx.console_log.append({"type": message.type, "text": ctx.redactor.text(message.text)}))
    ctx.page.on("pageerror", lambda error: ctx.page_errors.append(ctx.redactor.text(str(error))))
    ctx.page.on("response", lambda response: ctx.network_log.append({
        "status": response.status, "method": response.request.method,
        "url": ctx.redactor.text(response.url), "resource_type": response.request.resource_type,
    }))
    ctx.page.on("requestfailed", lambda request: ctx.network_log.append({
        "status": -1, "method": request.method, "url": ctx.redactor.text(request.url),
        "resource_type": request.resource_type, "failure": ctx.redactor.text(request.failure or ""),
    }))


def write_json(path: Path, data: object, redactor: Redactor) -> None:
    path.write_text(json.dumps(redactor.clean(data), ensure_ascii=False, indent=2), encoding="utf-8")


def dump_context(ctx: ScanContext) -> None:
    data = {"network": ctx.network_log, "console": ctx.console_log,
            "page_errors": ctx.page_errors, "dom": ctx.dom_info, "evidence": ctx.evidence}
    write_json(ctx.out_dir / f"{ctx.check_id}-evidence.json", data, ctx.redactor)
