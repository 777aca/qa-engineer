"""L4 全面：L3 + 安全黑盒 + a11y 深度 + 网络专项。"""
from __future__ import annotations

import json
import re
from .common import ScanContext

LOGIN_BTN_RE = re.compile(r"登\s*录|登\s*陆|登\s*入|login|sign\s*in", re.I)


def _looks_like_login(ctx: ScanContext) -> bool:
    return any((i.get("type") == "password") for i in ctx.dom_info.get("inputs", []))


def check_xss(ctx: ScanContext):
    if not _looks_like_login(ctx):
        return
    ctx.goto()
    page = ctx.page
    payload = "<script>window.__xss_hit__=1</script>"
    inputs = page.locator("input").all()
    if len(inputs) >= 2:
        inputs[0].fill(payload)
        inputs[1].fill(payload)
    if len(inputs) >= 3:
        inputs[2].fill("test")
    try:
        page.get_by_role("button", name=LOGIN_BTN_RE).first.click(timeout=2000)
        page.wait_for_timeout(1500)
    except Exception:
        pass
    hit = page.evaluate("window.__xss_hit__ || null")
    if hit:
        ctx.record(
            id="BUG-L4-XSS",
            title="用户名/密码字段反射 XSS（payload 被执行）",
            category="FORM-04", module="登录",
            severity="S1", priority="P0",
            steps=["在用户名填 <script>window.__xss_hit__=1</script>", "提交"],
            expected="输入被转义或过滤，脚本不执行",
            actual=f"window.__xss_hit__ = {hit}",
            evidence=[{"type": "screenshot", "path": ctx.shot("L4_xss")}],
            suggestion="前端 textContent 回显；后端回显接口 HTML 转义",
            tags=["security", "xss"],
        )


def check_cookie_flags(ctx: ScanContext):
    ctx.goto()
    ctx.page.wait_for_timeout(600)
    cookies = ctx.browser_context.cookies()
    bad = [
        c for c in cookies
        if c.get("httpOnly") is False or c.get("secure") is False
    ]
    if cookies and bad:
        ctx.record(
            id="BUG-L4-COOKIE-FLAGS",
            title=f"{len(bad)}/{len(cookies)} 个 cookie 缺 HttpOnly/Secure",
            category="SEC-02", module="安全",
            severity="S2", priority="P1",
            steps=["打开页面", "查看 Cookies"],
            expected="会话 cookie 应带 HttpOnly + Secure + SameSite",
            actual=json.dumps(
                [{"name": c["name"], "httpOnly": c["httpOnly"], "secure": c["secure"]}
                 for c in bad],
                ensure_ascii=False,
            ),
            suggestion="Set-Cookie: xxx; HttpOnly; Secure; SameSite=Lax",
            tags=["security", "cookie"],
        )


def check_a11y(ctx: ScanContext):
    dom = ctx.dom_info
    inputs = dom.get("inputs", [])
    if not inputs:
        return
    missing = [i for i in inputs if not i.get("aria_label") and not i.get("name")]
    if dom.get("labels_count", 0) == 0 and missing:
        ctx.record(
            id="BUG-L4-A11Y-LABEL",
            title=f"{len(missing)} 个 input 既无 <label> 也无 aria-label",
            category="A11Y-02", module="可访问性",
            severity="S3", priority="P2",
            steps=["屏幕阅读器读页面"],
            expected="每个 input 配 <label> 或 aria-label",
            actual="只有 placeholder",
            tags=["a11y"],
        )
    imgs = dom.get("images_without_alt", [])
    if imgs:
        ctx.record(
            id="BUG-L4-A11Y-ALT",
            title=f"{len(imgs)} 张 <img> 缺 alt",
            category="A11Y-01", module="可访问性",
            severity="S4", priority="P3",
            steps=["扫描 DOM 所有 <img>"],
            expected="装饰图 alt=''，内容图写描述",
            actual=f"无 alt: {imgs[:3]}",
            tags=["a11y"],
        )


def check_sensitive_storage(ctx: ScanContext):
    """localStorage 中是否明文存了敏感信息。"""
    ctx.goto()
    storage = ctx.page.evaluate(
        "() => Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k)]))"
    )
    suspicious = {
        k: (v[:60] + "…") if v and len(v) > 60 else v
        for k, v in storage.items()
        if k.lower() in ("token", "access_token", "password", "pwd", "secret")
        or (v and "Bearer " in str(v))
    }
    if suspicious:
        ctx.record(
            id="BUG-L4-STORAGE-SECRET",
            title="localStorage 中疑似存储敏感凭证",
            category="SEC-01", module="安全",
            severity="S2", priority="P1",
            status="待验证",
            steps=["打开页面", "DevTools → Application → Local Storage"],
            expected="敏感凭证应存 HttpOnly cookie",
            actual=json.dumps(suspicious, ensure_ascii=False),
            suggestion="token 搬去 HttpOnly cookie；确需前端可读的先短期 + 刷新机制",
            tags=["security"],
        )


CHECKS = [
    check_xss,
    check_cookie_flags,
    check_a11y,
    check_sensitive_storage,
]
