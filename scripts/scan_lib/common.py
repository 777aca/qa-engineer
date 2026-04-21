"""扫描库的公共部分：浏览器 setup、记录器、viewport 预设、platform 适配。"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable


# -------- viewport / UA 预设 --------

PC_VIEWPORTS = {
    "base": {"width": 1280, "height": 800},
    "large": {"width": 1920, "height": 1080},
}
MOBILE_VIEWPORTS = {
    "base": {"width": 375, "height": 667},
    "iphone14": {"width": 390, "height": 844},
    "tablet": {"width": 768, "height": 1024},
}
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def viewport_for(platform: str, kind: str = "base") -> dict:
    if platform == "mobile":
        return MOBILE_VIEWPORTS.get(kind, MOBILE_VIEWPORTS["base"])
    return PC_VIEWPORTS.get(kind, PC_VIEWPORTS["base"])


def responsive_breakpoints(platform: str) -> list[tuple[int, int, str]]:
    """L3+ 响应式断点。返回 (w, h, tag) 列表。"""
    if platform == "mobile":
        return [(375, 667, "mobile-base"), (390, 844, "iphone14"), (768, 1024, "tablet")]
    return [(1280, 800, "pc-base"), (1920, 1080, "pc-large")]


# -------- Finding 数据结构 --------

@dataclass
class Finding:
    id: str
    title: str
    category: str
    module: str
    severity: str
    priority: str
    status: str = "已确认"
    reproducible: str = "必现"
    steps: list[str] = field(default_factory=list)
    expected: str = ""
    actual: str = ""
    evidence: list[dict] = field(default_factory=list)
    suggestion: str = ""
    tags: list[str] = field(default_factory=list)
    level: str = "L2"
    platform: str = "pc"


# -------- 扫描上下文 --------

@dataclass
class ScanContext:
    """每次扫描共享的状态。check 函数通过它读 page、记结果。"""
    url: str
    level: str
    platform: str
    out_dir: pathlib.Path
    page: Any = None
    browser_context: Any = None
    findings: list[Finding] = field(default_factory=list)
    network_log: list[dict] = field(default_factory=list)
    console_log: list[dict] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    dom_info: dict = field(default_factory=dict)

    def record(self, **kwargs):
        kwargs.setdefault("level", self.level)
        kwargs.setdefault("platform", self.platform)
        self.findings.append(Finding(**kwargs))

    def shot(self, name: str) -> str:
        """截图到 out_dir 并返回相对路径字符串（用于 evidence）。"""
        p = self.out_dir / f"{name}.png"
        try:
            self.page.screenshot(path=str(p), full_page=True)
        except Exception:
            pass
        try:
            return str(p.relative_to(pathlib.Path.cwd())).replace("\\", "/")
        except ValueError:
            return str(p)

    def goto(self, timeout_ms: int = 20000, networkidle_ms: int = 10000):
        self.page.goto(self.url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            self.page.wait_for_load_state("networkidle", timeout=networkidle_ms)
        except Exception:
            pass


# -------- page 监听钩子 --------

def attach_listeners(ctx: ScanContext):
    p = ctx.page
    p.on("console", lambda m: ctx.console_log.append({"type": m.type, "text": m.text, "ts": time.time()}))
    p.on("pageerror", lambda e: ctx.page_errors.append(str(e)))
    p.on("response", lambda r: ctx.network_log.append({
        "status": r.status, "method": r.request.method, "url": r.url,
        "ok": r.ok, "ct": r.headers.get("content-type", ""),
    }))
    p.on("requestfailed", lambda r: ctx.network_log.append({
        "status": -1, "method": r.method, "url": r.url,
        "failure": (r.failure or ""), "ok": False, "ct": "",
    }))


# -------- 持久化 --------

def dump_context(ctx: ScanContext):
    (ctx.out_dir / "findings.json").write_text(
        json.dumps([f.__dict__ for f in ctx.findings], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ctx.out_dir / "network_log.json").write_text(
        json.dumps(ctx.network_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ctx.out_dir / "console_log.json").write_text(
        json.dumps(ctx.console_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ctx.out_dir / "page_errors.json").write_text(
        json.dumps(ctx.page_errors, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ctx.out_dir / "dom_info.json").write_text(
        json.dumps(ctx.dom_info, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# -------- Check 函数签名 --------

Check = Callable[[ScanContext], None]
