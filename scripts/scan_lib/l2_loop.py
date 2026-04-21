"""L2 闭环：L1 + 关键异常分支 + 导航健壮性。"""
from __future__ import annotations

import re
from playwright.sync_api import TimeoutError as PWTimeoutError
from .common import ScanContext

LOGIN_BTN_RE = re.compile(r"登\s*录|登\s*陆|登\s*入|login|sign\s*in", re.I)


def _looks_like_login(ctx: ScanContext) -> bool:
    dom = ctx.dom_info
    return any((i.get("type") == "password") for i in dom.get("inputs", []))


def _fill_login(page, u="", p="", c=""):
    inputs = page.locator("input").all()
    if len(inputs) >= 2:
        inputs[0].fill(u)
        inputs[1].fill(p)
    if len(inputs) >= 3:
        inputs[2].fill(c)


def _click_login(page):
    page.get_by_role("button", name=LOGIN_BTN_RE).first.click(timeout=2000)


def check_empty_submit(ctx: ScanContext):
    """空值提交应该被拦截并给出反馈。"""
    if not _looks_like_login(ctx):
        return
    ctx.goto()
    page = ctx.page
    try:
        _click_login(page)
        page.wait_for_timeout(800)
    except PWTimeoutError:
        ctx.record(
            id="BUG-L2-EMPTY-BTN",
            title="登录按钮空值场景下无法被点击",
            category="FORM-01", module="登录",
            severity="S3", priority="P2",
            steps=["打开登录页", "三个输入框全空", "点击登录按钮"],
            expected="按钮可点击并触发前端校验",
            actual="按钮点击超时",
        )
        return
    toast = page.locator("text=/请输入|不能为空|必填|required/i").first
    if toast.count() == 0:
        ctx.record(
            id="BUG-L2-EMPTY-NOTIP",
            title="空值提交登录无任何可见提示",
            category="FORM-01", module="登录",
            severity="S3", priority="P2",
            steps=["打开登录页", "不输入任何内容", "点击登录按钮"],
            expected="应有'请输入...'类 toast 或字段级错误",
            actual="无 toast/校验提示",
            evidence=[{"type": "screenshot", "path": ctx.shot("L2_empty_submit")}],
            suggestion="表单添加必填校验 + 失败 toast",
        )


def check_double_click(ctx: ScanContext):
    """连点提交：检查是否幂等或按钮 disable。"""
    if not _looks_like_login(ctx):
        return
    ctx.goto()
    page = ctx.page
    _fill_login(page, "no-such-user", "wrong-pass", "1234")
    start = len(ctx.network_log)
    try:
        btn = page.get_by_role("button", name=LOGIN_BTN_RE).first
        for _ in range(5):
            btn.click(no_wait_after=True, timeout=1000)
        page.wait_for_timeout(1500)
    except Exception:
        pass
    login_posts = [
        e for e in ctx.network_log[start:]
        if e["method"] == "POST"
        and ("/login" in e["url"] or "/auth" in e["url"] or "/signin" in e["url"])
    ]
    if len(login_posts) >= 2:
        ctx.record(
            id="BUG-L2-DOUBLE",
            title=f"登录按钮连点 5 次产生 {len(login_posts)} 次提交",
            category="STATE-05", module="登录",
            severity="S2", priority="P1",
            steps=["填表单", "连点登录按钮 5 次", "看 Network"],
            expected="第一次点击后按钮立即 disabled，只 1 次请求",
            actual=f"共 {len(login_posts)} 次 POST",
            evidence=[{"type": "network",
                       "content": "; ".join(f"{c['status']} {c['url']}" for c in login_posts)}],
            suggestion="点击时立即 disable，等请求结束恢复",
            tags=["idempotency"],
        )


def check_offline(ctx: ScanContext):
    """断网时提交应给出'网络异常'提示。"""
    if not _looks_like_login(ctx):
        return
    ctx.goto()
    page = ctx.page
    bc = ctx.browser_context
    _fill_login(page, "offline-user", "offline-pass", "1234")
    bc.set_offline(True)
    try:
        _click_login(page)
        page.wait_for_timeout(2500)
    except Exception:
        pass
    err_toast = page.locator("text=/网络|失败|请重试|错误|network|offline/i").first
    if err_toast.count() == 0:
        ctx.record(
            id="BUG-L2-OFFLINE",
            title="断网时点击登录无任何错误提示",
            category="NET-02", module="登录",
            severity="S3", priority="P2",
            status="待验证",
            steps=["填表单", "切离线", "点击登录"],
            expected="显示'网络异常，请重试'类 toast",
            actual="请求失败但无用户可见反馈",
            evidence=[{"type": "screenshot", "path": ctx.shot("L2_offline")}],
            suggestion="统一拦截 axios/fetch 错误，弹 toast",
        )
    bc.set_offline(False)


def check_refresh_preserves_state(ctx: ScanContext):
    """刷新登录页后不应白屏或丢状态（登录页本身状态少，主要验证刷新不炸）。"""
    ctx.goto()
    page = ctx.page
    pre_errs = len(ctx.page_errors)
    page.reload(wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1500)
    if len(ctx.page_errors) > pre_errs:
        ctx.record(
            id="BUG-L2-RELOAD-ERR",
            title="F5 刷新后页面抛出异常",
            category="STATE-01", module="首屏",
            severity="S2", priority="P1",
            steps=[f"打开 {ctx.url}", "按 F5"],
            expected="刷新后不抛异常",
            actual="\n".join(ctx.page_errors[pre_errs:pre_errs+3]),
        )


CHECKS = [
    check_empty_submit,
    check_double_click,
    check_offline,
    check_refresh_preserves_state,
]
