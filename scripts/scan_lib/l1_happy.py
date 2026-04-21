"""L1 主流程：走核心正向路径。

主流程"是什么"通常取决于被测系统，本模块提供通用骨架 +
登录页专项（能识别到登录页时自动跑）。

如果用户提供了测试账号，会尝试登录后截图首页；
否则只验证"登录页元素齐全 + 登录按钮可点击"。
"""
from __future__ import annotations

import os
import re
from .common import ScanContext

LOGIN_BTN_RE = re.compile(r"登\s*录|登\s*陆|登\s*入|login|sign\s*in", re.I)


def _looks_like_login(ctx: ScanContext) -> bool:
    dom = ctx.dom_info
    if not dom:
        return False
    has_password = any((i.get("type") == "password") for i in dom.get("inputs", []))
    has_login_btn = any(
        "登录" in (b.get("text") or "") or "login" in (b.get("text") or "").lower()
        for b in dom.get("buttons", [])
    )
    return has_password or has_login_btn


def check_login_page_elements(ctx: ScanContext):
    """登录页核心三件套：用户名、密码、提交按钮齐全可见。"""
    if not _looks_like_login(ctx):
        return
    page = ctx.page
    text_inputs = page.locator("input[type='text'], input:not([type])").count()
    pwd = page.locator("input[type='password']").count()
    if text_inputs < 1 or pwd < 1:
        ctx.record(
            id="BUG-L1-LOGIN-FORM",
            title=f"登录表单不完整（text={text_inputs}, password={pwd}）",
            category="UI-01", module="登录",
            severity="S1", priority="P0",
            steps=[f"打开 {ctx.url}"],
            expected="至少 1 个文本框 + 1 个密码框",
            actual=f"text={text_inputs}, password={pwd}",
        )


def check_login_flow_if_creds(ctx: ScanContext):
    """有 SGIP_USER / SGIP_PASS 环境变量时，尝试登录看能否进入主页。"""
    if not _looks_like_login(ctx):
        return
    user = os.environ.get("TEST_USER") or os.environ.get("SGIP_USER")
    pwd = os.environ.get("TEST_PASS") or os.environ.get("SGIP_PASS")
    if not user or not pwd:
        # 没账号就在 findings 里留一条 info，但不算 bug
        return

    page = ctx.page
    ctx.goto()
    inputs = page.locator("input").all()
    if len(inputs) >= 2:
        inputs[0].fill(user)
        inputs[1].fill(pwd)
        # 验证码通常自动识别不了 —— L1 不处理，只尝试点登录
    try:
        btn = page.get_by_role("button", name=LOGIN_BTN_RE)
        btn.first.click(timeout=3000)
        page.wait_for_timeout(3000)
    except Exception:
        pass

    if page.url == ctx.url or "/login" in page.url:
        ctx.record(
            id="BUG-L1-LOGIN-FAIL",
            title="使用提供的测试账号登录失败或未跳转",
            category="STATE-01", module="登录",
            severity="S2", priority="P1",
            status="待验证",
            reproducible="偶现",
            steps=[
                "打开登录页",
                "填入测试账号密码",
                "点击登录",
            ],
            expected="跳转到首页/主工作台",
            actual=f"3 秒后仍在 {page.url}",
            evidence=[{"type": "screenshot", "path": ctx.shot("L1_login_result")}],
            suggestion="若因验证码必须人工输入，请人工登录后用 storage state 方式跑",
        )
    else:
        ctx.shot("L1_home_after_login")


CHECKS = [check_login_page_elements, check_login_flow_if_creds]
