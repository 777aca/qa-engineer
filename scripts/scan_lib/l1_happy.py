"""L1：识别密码登录；登录成功必须有配置的业务断言。"""
from __future__ import annotations

import os
from playwright.sync_api import expect
from .common import CheckSpec, Outcome, ScanContext
from .login import fields


def check_login_page_elements(ctx: ScanContext) -> Outcome:
    form = fields(ctx)
    if form is None:
        return Outcome("Skipped", "不是可唯一识别的密码登录表单；验证码、SSO 等交给业务场景")
    for control in form:
        expect(control).to_be_visible()
    return Outcome("Pass", "账号、密码和提交控件可见；账号支持 email/tel/text")


def check_login_flow_if_creds(ctx: ScanContext) -> Outcome:
    form = fields(ctx)
    if form is None:
        return Outcome("Skipped", "当前页面不适用通用密码登录检查")
    user, password = os.environ.get("TEST_USER"), os.environ.get("TEST_PASS")
    success = os.environ.get("TEST_LOGIN_SUCCESS_SELECTOR")
    if not user or not password:
        return Outcome("Blocked", "缺少 TEST_USER / TEST_PASS；也可配置已登录场景与 storage state")
    if not success:
        return Outcome("Blocked", "缺少 TEST_LOGIN_SUCCESS_SELECTOR，不能仅凭 URL 跳转判定成功")
    ctx.redactor.remember(user)
    ctx.redactor.remember(password)
    form[0].fill(user)
    form[1].fill(password)
    form[2].click()
    expect(ctx.page.locator(success)).to_be_visible(timeout=10000)
    return Outcome("Pass", "提交后已观察到配置的登录成功元素")


CHECKS = [
    CheckSpec("login-elements", "密码登录控件", "L1", check_login_page_elements, module="登录"),
    CheckSpec("login-flow", "密码登录主流程", "L1", check_login_flow_if_creds, module="登录",
              active=True, applies=lambda ctx: fields(ctx) is not None,
              expected=["出现 TEST_LOGIN_SUCCESS_SELECTOR 指定的成功元素"]),
]
