"""L2：有限的登录异常检查；业务闭环由配置场景验证。"""
from __future__ import annotations

from playwright.sync_api import expect, TimeoutError as PlaywrightTimeout
from .common import CheckSpec, Outcome, ScanContext
from .login import fields, feedback


def check_empty_submit(ctx: ScanContext) -> Outcome:
    form = fields(ctx)
    if form is None:
        return Outcome("Skipped", "当前页面不适用密码登录空值检查")
    username, password, button = form
    username.fill("")
    password.fill("")
    if button.is_disabled():
        return Outcome("Pass", "空表单禁用提交按钮，有效阻止提交")
    button.click()
    if username.evaluate("(el) => !el.validity.valid") or password.evaluate("(el) => !el.validity.valid"):
        return Outcome("Pass", "浏览器原生约束阻止了空表单提交")
    try:
        expect(feedback(ctx)).to_be_visible(timeout=2000)
        return Outcome("Pass", "观察到可见校验反馈")
    except AssertionError:
        ctx.record(id="BUG-EMPTY-REVIEW", title="空值提交反馈需核实", category="FORM-01", module="登录",
                   severity="S3", priority="P2", actual="未识别到原生校验、禁用按钮或可见错误",
                   evidence=[{"type": "observation", "content": "空值提交后未识别到约定形式的反馈"}])
        return Outcome("NeedsReview", "可能采用其他反馈方式，需根据页面与需求复核")


def check_double_click(ctx: ScanContext) -> Outcome:
    return Outcome("Skipped", "重复请求不等于业务不幂等；请用业务场景核对最终记录数与状态")


def check_offline(ctx: ScanContext) -> Outcome:
    form = fields(ctx)
    if form is None:
        return Outcome("Skipped", "当前页面不适用密码登录断网检查")
    form[0].fill("qa-offline-user")
    form[1].fill("qa-offline-password")
    ctx.browser_context.set_offline(True)
    try:
        try:
            form[2].click(timeout=3000)
        except PlaywrightTimeout:
            return Outcome("Blocked", "离线场景提交控件不可操作")
        try:
            expect(feedback(ctx)).to_be_visible(timeout=3000)
        except AssertionError:
            return Outcome("NeedsReview", "离线提交后未识别到可见反馈，需要复核")
        if not any(item["status"] == -1 for item in ctx.network_log):
            return Outcome("Skipped", "未观察到网络请求失败，可能先被表单校验拦截")
        return Outcome("Pass", "离线请求失败后出现可见反馈")
    finally:
        ctx.browser_context.set_offline(False)


def check_refresh_preserves_state(ctx: ScanContext) -> Outcome:
    before = len(ctx.page_errors)
    response = ctx.page.reload(wait_until="domcontentloaded")
    assert response is None or response.status < 400, "刷新后文档请求失败"
    expect(ctx.page.locator(ctx.ready_selector or "body")).to_be_visible()
    if len(ctx.page_errors) > before:
        return Outcome("NeedsReview", "刷新后出现异常日志，需结合业务影响确认")
    return Outcome("Pass", "刷新后主体可见；业务数据是否保持由场景断言验证")


CHECKS = [
    CheckSpec("empty-submit", "登录空值校验", "L2", check_empty_submit, module="登录", active=True,
              applies=lambda ctx: fields(ctx) is not None),
    CheckSpec("idempotency", "业务幂等性", "L2", check_double_click),
    CheckSpec("offline", "登录离线反馈", "L2", check_offline, module="登录", active=True,
              applies=lambda ctx: fields(ctx) is not None),
    CheckSpec("refresh", "页面刷新", "L2", check_refresh_preserves_state),
]
