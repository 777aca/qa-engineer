"""L3：仅对实际存在的交互作判断；未知业务规则不猜测。"""
from __future__ import annotations

import re
from playwright.sync_api import expect, TimeoutError as PlaywrightTimeout
from .common import CheckSpec, Outcome, ScanContext, responsive_breakpoints


def check_long_input(ctx: ScanContext) -> Outcome:
    return Outcome("Skipped", "长度上限必须来自需求或接口契约，请在业务场景配置边界值")


def check_trim(ctx: ScanContext) -> Outcome:
    return Outcome("Skipped", "是否去空格由业务规则决定，不根据输入框显示值推断提交行为")


def check_enter_key(ctx: ScanContext) -> Outcome:
    return Outcome("Skipped", "请通过 press + 业务结果断言配置键盘提交流程，不假定必须存在验证码框")


def check_password_toggle(ctx: ScanContext) -> Outcome:
    toggle = ctx.page.get_by_role("button", name=re.compile(r"显示密码|隐藏密码|show password|hide password", re.I))
    password = ctx.page.locator("input[type=password]:visible")
    if toggle.count() != 1 or password.count() != 1:
        return Outcome("Skipped", "未唯一识别到密码显隐按钮，不进行坐标猜测")
    handle = password.element_handle()
    assert handle is not None
    toggle.click()
    try:
        ctx.page.wait_for_function("(el) => el.type === 'text'", arg=handle, timeout=3000)
    except PlaywrightTimeout:
        raise AssertionError("点击已识别的密码显隐按钮后，原字段未切换为 text") from None
    return Outcome("Pass", "实际存在的密码显隐按钮将字段切换为可见文本")


def check_responsive(ctx: ScanContext) -> Outcome:
    try:
        for width, height, tag in responsive_breakpoints(ctx.platform):
            ctx.page.set_viewport_size({"width": width, "height": height})
            expect(ctx.page.locator("body")).to_be_visible()
            ctx.shot(f"responsive-{tag}")
        return Outcome("NeedsReview", "已采集所选平台断点截图，需视觉复核；截图不等于布局通过")
    finally:
        from .common import viewport_for
        ctx.page.set_viewport_size(viewport_for(ctx.platform))


CHECKS = [
    CheckSpec("length-boundary", "输入长度边界", "L3", check_long_input),
    CheckSpec("trim", "空格处理规则", "L3", check_trim),
    CheckSpec("enter-submit", "键盘提交", "L3", check_enter_key),
    CheckSpec("password-toggle", "密码显隐", "L3", check_password_toggle, active=True),
    CheckSpec("responsive", "响应式截图复核", "L3", check_responsive),
]
