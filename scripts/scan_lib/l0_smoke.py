"""L0：验证实际加载结果；启发式发现保留为待验证。"""
from __future__ import annotations

from .common import CheckSpec, Outcome, ScanContext


def check_page_loads(ctx: ScanContext) -> Outcome:
    ctx.shot("initial")
    if not ctx.dom_info.get("title"):
        ctx.record(id="BUG-NOTITLE", title="页面标题为空", category="UI-01", module="首屏",
                   severity="S3", priority="P2", actual="document.title 为空",
                   evidence=[{"type": "dom", "content": "document.title 为空"}])
        return Outcome("NeedsReview", "页面可访问，但标题为空，需要核实产品要求")
    return Outcome("Pass", "文档加载成功，页面主体可见；不据 HTML 长度推断白屏")


def check_no_page_errors(ctx: ScanContext) -> Outcome:
    errors = ctx.page_errors + [str(item["text"]) for item in ctx.console_log if item["type"] == "error"]
    if errors:
        ctx.record(id="BUG-CONSOLE", title="页面出现异常或错误日志", category="UI-01", module="首屏",
                   severity="S2", priority="P1", actual="\n".join(errors[:5]),
                   evidence=[{"type": "console", "content": error} for error in errors[:5]])
        return Outcome("NeedsReview", "捕获到错误日志，需结合实际功能确认影响")
    return Outcome("Pass", "页面就绪检查点未捕获错误日志；不代表后续交互无异常")


def check_core_resources(ctx: ScanContext) -> Outcome:
    bad = [item for item in ctx.network_log
           if (item["status"] == -1 or item["status"] >= 400)
           and item["resource_type"] in ("script", "stylesheet", "image", "font")]
    if bad:
        ctx.record(id="BUG-RESOURCE", title="页面资源加载失败", category="NET-01", module="首屏",
                   severity="S2", priority="P1", actual=f"失败资源数：{len(bad)}",
                   evidence=[{"type": "network", "content": str(item)} for item in bad[:5]])
        return Outcome("NeedsReview", "存在失败资源，是否影响核心功能需复核")
    return Outcome("Pass", "观察窗口内未发现失败的脚本、样式、图片或字体请求")


CHECKS = [
    CheckSpec("page-load", "首屏可访问", "L0", check_page_loads, expected=["文档加载成功且主体可见"]),
    CheckSpec("page-errors", "首屏错误日志", "L0", check_no_page_errors, expected=["就绪检查点无未处理错误"]),
    CheckSpec("resources", "首屏资源请求", "L0", check_core_resources, expected=["观察窗口内资源正常加载"]),
]
