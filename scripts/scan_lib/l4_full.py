"""L4：有明确边界的安全与可访问性检查，不宣称完整审计。"""
from __future__ import annotations

import re
from .common import CheckSpec, Outcome, ScanContext
from .login import fields
from .redaction import SENSITIVE


def check_xss(ctx: ScanContext) -> Outcome:
    form = fields(ctx)
    if form is None:
        return Outcome("Skipped", "当前页面不适用密码登录输入探针")
    ctx.page.evaluate("window.__qa_xss_hit__ = false")
    form[0].fill("<script>window.__qa_xss_hit__=true</script>")
    form[1].fill("qa-test-password")
    form[2].click()
    if ctx.page.evaluate("window.__qa_xss_hit__ === true"):
        ctx.record(id="BUG-XSS", title="输入探针在页面中执行", category="SEC-01", module="安全",
                   severity="S1", priority="P0", status="已确认",
                   actual="观察到本次探针的执行标记",
                   evidence=[{"type": "runtime", "content": "window.__qa_xss_hit__ === true"}])
        return Outcome("Fail", "已观察到本次脚本探针执行")
    return Outcome("NeedsReview", "当前检查点未观察到探针执行；单一输入不能证明无 XSS")


def check_cookie_flags(ctx: ScanContext) -> Outcome:
    cookies = ctx.browser_context.cookies()
    session = [cookie for cookie in cookies if re.search(r"session|auth|token|sid", cookie["name"], re.I)]
    bad = [{"name": cookie["name"], "httpOnly": cookie["httpOnly"], "secure": cookie["secure"]}
           for cookie in session if not cookie["httpOnly"] or not cookie["secure"]]
    if bad:
        ctx.record(id="BUG-COOKIE", title="疑似会话 Cookie 的保护属性需核实", category="SEC-02", module="安全",
                   severity="S2", priority="P1", actual=f"候选数量：{len(bad)}",
                   evidence=[{"type": "cookie_attributes", "content": str(bad)}])
        return Outcome("NeedsReview", "按名称识别的会话 Cookie 缺少保护属性，需核实用途和环境")
    return Outcome("Pass" if session else "Skipped",
                   "已识别的会话 Cookie 具备 HttpOnly/Secure" if session else "未识别到会话 Cookie")


def check_a11y(ctx: ScanContext) -> Outcome:
    ctx.refresh_dom()
    inputs = ctx.dom_info.get("inputs", [])
    missing = [item for item in inputs if item["type"] not in ("hidden", "submit", "button", "reset", "image") and not item["accessible"]]
    images = ctx.dom_info.get("images_without_alt", [])
    if missing or images:
        ctx.record(id="BUG-A11Y", title="可访问名称或图片替代文本需复核", category="A11Y-01", module="可访问性",
                   severity="S3", priority="P2",
                   actual=f"未识别名称的输入控件 {len(missing)} 个；未声明 alt 的图片 {len(images)} 张",
                   evidence=[{"type": "dom", "content": f"inputs={len(missing)}, images={len(images)}"}])
        return Outcome("NeedsReview", "发现基础可访问性候选；需结合语义与人工检查确认")
    return Outcome("Pass", "基础 DOM 检查未发现候选；不代表通过全部 WCAG 检查")


def check_sensitive_storage(ctx: ScanContext) -> Outcome:
    # 只读取键名，凭据值不进入 Python、日志、截图说明或报告。
    keys = ctx.page.evaluate("() => Object.keys(localStorage)")
    suspicious = [key for key in keys if SENSITIVE.search(key)]
    if suspicious:
        ctx.record(id="BUG-STORAGE", title="浏览器存储中存在敏感命名字段", category="SEC-01", module="安全",
                   severity="S2", priority="P1", actual=f"疑似敏感字段 {len(suspicious)} 个；未采集其值",
                   evidence=[{"type": "storage_keys", "content": ", ".join(suspicious)}])
        return Outcome("NeedsReview", "需核实字段用途、凭据生命周期和威胁模型")
    return Outcome("Pass", "未发现敏感命名字段；未读取或判断任意存储值")


CHECKS = [
    CheckSpec("xss-probe", "登录输入脚本探针", "L4", check_xss, module="安全", active=True, security=True,
              applies=lambda ctx: fields(ctx) is not None),
    CheckSpec("cookie-flags", "会话 Cookie 属性", "L4", check_cookie_flags, module="安全"),
    CheckSpec("basic-a11y", "基础可访问性", "L4", check_a11y, module="可访问性"),
    CheckSpec("storage-keys", "敏感存储字段", "L4", check_sensitive_storage, module="安全"),
]
