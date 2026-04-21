"""L0 冒烟：只回答'环境能不能测'。零交互。"""
from __future__ import annotations

from .common import ScanContext


def _scan_dom(ctx: ScanContext):
    page = ctx.page
    ctx.dom_info = {
        "title": page.title(),
        "url": page.url,
        "inputs": [
            {
                "type": el.get_attribute("type"),
                "placeholder": el.get_attribute("placeholder"),
                "name": el.get_attribute("name"),
                "aria_label": el.get_attribute("aria-label"),
                "maxlength": el.get_attribute("maxlength"),
                "autocomplete": el.get_attribute("autocomplete"),
            }
            for el in page.locator("input").all()
        ],
        "buttons": [
            {"text": (el.text_content() or "").strip(),
             "aria_label": el.get_attribute("aria-label")}
            for el in page.locator("button").all()
        ],
        "images_without_alt": page.evaluate(
            "Array.from(document.querySelectorAll('img')).filter(i=>!i.alt).map(i=>i.src)"
        ),
        "labels_count": page.locator("label").count(),
        "has_form_tag": page.locator("form").count() > 0,
        "html_len": len(page.content()),
    }


def check_page_loads(ctx: ScanContext):
    """页面能打开、无白屏、无 pageerror。"""
    ctx.goto()
    _scan_dom(ctx)
    ctx.shot("L0_initial")

    if not ctx.dom_info["title"]:
        ctx.record(
            id="BUG-L0-NOTITLE", title="页面 <title> 为空",
            category="UI-01", module="首屏",
            severity="S3", priority="P2",
            steps=[f"打开 {ctx.url}"],
            expected="<title> 有有意义的描述",
            actual="title 空",
        )

    if ctx.dom_info["html_len"] < 500:
        ctx.record(
            id="BUG-L0-WHITE", title="首屏 HTML 过短（疑似白屏）",
            category="UI-01", module="首屏",
            severity="S1", priority="P0",
            steps=[f"打开 {ctx.url}"],
            expected="首屏内容完整渲染",
            actual=f"document.documentElement.outerHTML 长度 = {ctx.dom_info['html_len']}",
            evidence=[{"type": "screenshot", "path": ctx.shot("L0_white_suspicion")}],
            suggestion="查看 JS 是否报错；检查核心 bundle 是否 404",
        )


def check_no_page_errors(ctx: ScanContext):
    """pageerror / console.error 零容忍。"""
    if ctx.page_errors:
        ctx.record(
            id="BUG-L0-PAGEERR",
            title=f"首屏抛出 {len(ctx.page_errors)} 个未捕获异常",
            category="UI-01", module="首屏",
            severity="S1", priority="P0",
            steps=[f"打开 {ctx.url}", "观察 DevTools Console"],
            expected="无 pageerror",
            actual="\n".join(ctx.page_errors[:5]),
            evidence=[{"type": "console", "content": e} for e in ctx.page_errors[:3]],
            suggestion="按首个错误栈反推组件，先修",
        )
    err_console = [c for c in ctx.console_log if c.get("type") == "error"]
    if err_console:
        ctx.record(
            id="BUG-L0-CONSOLE-ERR",
            title=f"首屏产生 {len(err_console)} 条 console.error",
            category="UI-01", module="首屏",
            severity="S2", priority="P1",
            steps=[f"打开 {ctx.url}", "观察 Console"],
            expected="无 error 级别日志",
            actual="\n".join(c["text"] for c in err_console[:5]),
            status="待验证",
        )


def check_core_resources(ctx: ScanContext):
    """首屏加载的 JS/CSS/图片有无 4xx/5xx。"""
    bad = [
        e for e in ctx.network_log
        if (e["status"] >= 400 or e["status"] == -1)
        and ("/assets/" in e["url"] or e["url"].endswith((".js", ".css", ".png", ".svg", ".jpg", ".woff2")))
    ]
    if bad:
        ctx.record(
            id="BUG-L0-RES-FAIL",
            title=f"{len(bad)} 个核心静态资源加载失败",
            category="NET-01", module="首屏",
            severity="S1", priority="P0",
            steps=[f"打开 {ctx.url}", "观察 Network 面板"],
            expected="核心资源全部 2xx",
            actual="\n".join(f"{e['status']} {e['url']}" for e in bad[:5]),
            suggestion="检查 CDN/部署；可能是构建 hash 对不上",
        )


# ---- 档位注册 ----

CHECKS = [check_page_loads, check_no_page_errors, check_core_resources]
