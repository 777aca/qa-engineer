"""L3 精细：L2 + 边界值/等价类/响应式/键盘/交互细节。"""
from __future__ import annotations

from .common import ScanContext, responsive_breakpoints


def _looks_like_login(ctx: ScanContext) -> bool:
    return any((i.get("type") == "password") for i in ctx.dom_info.get("inputs", []))


def check_long_input(ctx: ScanContext):
    """超长输入：检查 maxlength 或截断。"""
    if not _looks_like_login(ctx):
        return
    ctx.goto()
    page = ctx.page
    inputs = page.locator("input").all()
    if len(inputs) < 2:
        return
    inputs[0].fill("a" * 2000)
    inputs[1].fill("b" * 2000)
    page.wait_for_timeout(300)
    u = inputs[0].input_value()
    p = inputs[1].input_value()
    if len(u) >= 2000 or len(p) >= 2000:
        ctx.record(
            id="BUG-L3-LONG",
            title="用户名/密码未限制长度，可输入 2000 字符",
            category="FORM-03", module="登录",
            severity="S3", priority="P2",
            steps=["打开登录页", "在用户名和密码框粘贴 2000 字"],
            expected="应有合理 maxlength（如 64/128）",
            actual=f"实际长度 user={len(u)}, pwd={len(p)}",
            suggestion="<input maxlength='64'> 或 JS 截断并给提示",
        )


def check_trim(ctx: ScanContext):
    """前后空格是否 trim。"""
    if not _looks_like_login(ctx):
        return
    ctx.goto()
    page = ctx.page
    inputs = page.locator("input").all()
    if not inputs:
        return
    inputs[0].fill("  admin  ")
    page.wait_for_timeout(200)
    v = inputs[0].input_value()
    if v.startswith(" ") or v.endswith(" "):
        ctx.record(
            id="BUG-L3-TRIM",
            title="用户名前后空格未 trim",
            category="FORM-02", module="登录",
            severity="S4", priority="P3",
            status="待验证",
            steps=["在用户名输入 '  admin  '"],
            expected="输入时或提交前自动 trim",
            actual=f"框内保留为 '{v}'",
            suggestion="提交前 .trim() 或 blur 时去空格",
        )


def check_enter_key(ctx: ScanContext):
    """按 Enter 应该等价于点击登录。"""
    if not _looks_like_login(ctx):
        return
    ctx.goto()
    page = ctx.page
    inputs = page.locator("input").all()
    if len(inputs) >= 3:
        inputs[0].fill("enter-u")
        inputs[1].fill("enter-p")
        inputs[2].fill("1234")
        start = len(ctx.network_log)
        try:
            inputs[2].press("Enter")
            page.wait_for_timeout(1500)
        except Exception:
            pass
        posts = [
            e for e in ctx.network_log[start:]
            if e["method"] == "POST" and ("/login" in e["url"] or "/auth" in e["url"])
        ]
        if not posts:
            ctx.record(
                id="BUG-L3-ENTER",
                title="验证码框按 Enter 不触发登录",
                category="FORM-10", module="登录",
                severity="S3", priority="P2",
                status="待验证",
                steps=["填完三个框", "在最后一个框按 Enter"],
                expected="Enter 等价于点登录按钮",
                actual="未观察到 /login POST",
                suggestion="用 <form> 包裹 + type='submit' 按钮",
                tags=["keyboard", "ux"],
            )


def check_password_toggle(ctx: ScanContext):
    """密码显隐按钮：用坐标点击密码框右端区域。"""
    if not _looks_like_login(ctx):
        return
    ctx.goto()
    page = ctx.page
    pwd = page.locator("input[type='password']").first
    if pwd.count() == 0:
        return
    pwd.fill("hello")
    box = pwd.bounding_box()
    if not box:
        return
    page.mouse.click(box["x"] + box["width"] - 20, box["y"] + box["height"] / 2)
    page.wait_for_timeout(400)
    cur_type = page.locator("input").nth(1).get_attribute("type")
    if cur_type == "password":
        ctx.record(
            id="BUG-L3-PWD-TOGGLE",
            title="密码显隐切换按钮无效",
            category="UI-06", module="登录",
            severity="S4", priority="P3",
            steps=["密码框输入任意字符", "点击右侧眼睛图标"],
            expected="type 在 password/text 间切换",
            actual="type 始终为 password",
            evidence=[{"type": "screenshot", "path": ctx.shot("L3_pwd_toggle")}],
            tags=["ux"],
        )


def check_responsive(ctx: ScanContext):
    """按所选平台跑响应式断点视觉扫描（只截图，不自动判断）。"""
    bc = ctx.browser_context
    for w, h, tag in responsive_breakpoints(ctx.platform):
        try:
            ctx.page.set_viewport_size({"width": w, "height": h})
            ctx.goto()
            ctx.page.wait_for_timeout(500)
            ctx.shot(f"L3_responsive_{tag}_{w}x{h}")
        except Exception:
            continue


CHECKS = [
    check_long_input,
    check_trim,
    check_enter_key,
    check_password_toggle,
    check_responsive,
]
