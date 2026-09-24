"""密码登录页的保守识别，不依赖输入框顺序。"""
from __future__ import annotations

import re
from playwright.sync_api import Locator
from .common import ScanContext

LOGIN_RE = re.compile(r"登\s*[录陆入]|login|sign\s*in", re.I)


def fields(ctx: ScanContext) -> tuple[Locator, Locator, Locator] | None:
    page = ctx.page
    password = page.locator("input[type=password]:visible")
    username = page.locator("input[autocomplete=username]:visible, input[type=email]:visible, input[type=tel]:visible, input[type=text]:visible, input:not([type]):visible")
    button = page.get_by_role("button", name=LOGIN_RE)
    if password.count() != 1 or username.count() != 1 or button.count() != 1:
        return None
    return username, password, button


def feedback(ctx: ScanContext) -> Locator:
    return ctx.page.locator(
        '[role=alert]:visible, [aria-invalid=true]:visible, '
        ':text-matches("请输入|不能为空|必填|required|invalid|错误|失败|网络|offline|network", "i"):visible'
    ).first
