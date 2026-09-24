"""声明式业务场景：输入严格校验，不执行配置中的任意代码。"""
from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Locator, expect
from data_contract import DataError, LEVELS, load_document, object_map, text
from .common import CheckSpec, Outcome, ScanContext

ASSERTIONS = {"expect_visible", "expect_hidden", "expect_text", "expect_value", "expect_count", "expect_url"}
ACTIONS = {"goto", "reload", "fill", "fill_env", "click", "press", "select", "upload"} | ASSERTIONS
ACTIVE = {"click", "press", "select", "upload", "fill", "fill_env"}


@dataclass
class ScenarioConfig:
    checks: list[CheckSpec] = field(default_factory=list)
    ready_selector: str | None = None
    allowed_origins: set[str] = field(default_factory=set)
    secret_envs: set[str] = field(default_factory=set)


def origin(url: str) -> str:
    try:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise ValueError()
    except ValueError:
        raise DataError("目标地址必须是无内嵌凭据的合法 HTTP/HTTPS URL") from None
    return f"{parts.scheme}://{parts.hostname}:{port}"


def _target(value: object, location: str) -> dict[str, object]:
    target = object_map(value, location)
    keys = set(target)
    if keys == {"role", "name"}:
        text(target["role"], location + ".role")
        text(target["name"], location + ".name")
    elif keys in ({"label"}, {"test_id"}, {"css"}):
        text(next(iter(target.values())), location)
    else:
        raise DataError(f"{location} 使用 role+name、label、test_id 或 css 之一")
    return target


def locate(ctx: ScanContext, target: dict[str, object]) -> Locator:
    if "role" in target:
        return ctx.page.get_by_role(target["role"], name=target["name"], exact=True)
    if "label" in target:
        return ctx.page.get_by_label(target["label"], exact=True)
    if "test_id" in target:
        return ctx.page.get_by_test_id(target["test_id"])
    return ctx.page.locator(target["css"])


def describe(step: dict[str, object]) -> str:
    shown = dict(step)
    if step["action"] == "fill_env":
        shown["value"] = f"环境变量 {step['value']}（不记录值）"
    return json.dumps(shown, ensure_ascii=False)


def _execute(ctx: ScanContext, steps: list[dict[str, object]], allowed: set[str]) -> Outcome:
    for step in steps:
        action = step["action"]
        value = step.get("value")
        if action == "goto":
            url = urljoin(ctx.url, value)
            if origin(url) not in allowed:
                return Outcome("Blocked", "场景导航超出已配置的目标域名")
            response = ctx.page.goto(url, wait_until="domcontentloaded")
            assert response is None or response.status < 400, "场景导航返回 HTTP 错误"
        elif action == "reload":
            response = ctx.page.reload(wait_until="domcontentloaded")
            assert response is None or response.status < 400, "场景刷新返回 HTTP 错误"
        elif action == "expect_url":
            expect(ctx.page).to_have_url(urljoin(ctx.url, value))
        else:
            control = locate(ctx, step["target"])
            if action == "fill_env":
                secret = os.environ.get(value)
                if not secret:
                    return Outcome("Blocked", f"缺少场景所需环境变量：{value}")
                ctx.redactor.remember(secret)
                control.fill(secret)
            elif action == "fill":
                control.fill(value)
            elif action == "click":
                control.click()
            elif action == "press":
                control.press(value)
            elif action == "select":
                control.select_option(value)
            elif action == "upload":
                control.set_input_files(value)
            elif action == "expect_visible":
                expect(control).to_be_visible()
            elif action == "expect_hidden":
                expect(control).to_be_hidden()
            elif action == "expect_text":
                expect(control).to_have_text(value)
            elif action == "expect_value":
                expect(control).to_have_value(value)
            elif action == "expect_count":
                expect(control).to_have_count(value)
    return Outcome("Pass", "配置的业务场景及末尾结果断言全部通过")


def load_scenarios(path: str | None, base_url: str, level: str) -> ScenarioConfig:
    result = ScenarioConfig(allowed_origins={origin(base_url)})
    if path is None:
        return result
    data = object_map(load_document(path), "config")
    if set(data) - {"schema_version", "ready_selector", "allowed_origins", "scenarios"}:
        raise DataError("config 存在未知字段")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise DataError("config.schema_version 必须为 1")
    if "ready_selector" in data:
        result.ready_selector = text(data["ready_selector"], "config.ready_selector")
    origins = data.get("allowed_origins", [])
    if not isinstance(origins, list):
        raise DataError("config.allowed_origins 必须是 URL 列表")
    result.allowed_origins.update(origin(text(item, "allowed_origins[]")) for item in origins)
    rows = data.get("scenarios")
    if not isinstance(rows, list):
        raise DataError("config.scenarios 必须是列表")
    ids: set[str] = set()
    for index, raw in enumerate(rows):
        where = f"scenarios[{index}]"
        row = object_map(raw, where)
        if set(row) - {"id", "title", "module", "level", "steps", "preconditions"}:
            raise DataError(f"{where} 存在未知字段")
        identifier = text(row.get("id"), where + ".id")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", identifier) or identifier in ids:
            raise DataError(f"{where}.id 必须唯一且仅包含字母数字、下划线或连字符")
        ids.add(identifier)
        title = text(row.get("title"), where + ".title")
        module = text(row.get("module"), where + ".module")
        minimum = row.get("level", "L1")
        if minimum not in sorted(LEVELS):
            raise DataError(f"{where}.level 必须为 L0–L4")
        preconditions = row.get("preconditions", [])
        if not isinstance(preconditions, list) or not all(isinstance(item, str) for item in preconditions):
            raise DataError(f"{where}.preconditions 必须是文本列表")
        raw_steps = row.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise DataError(f"{where}.steps 必须是非空列表")
        steps: list[dict[str, object]] = []
        for position, raw_step in enumerate(raw_steps):
            loc = f"{where}.steps[{position}]"
            step = object_map(raw_step, loc)
            action = text(step.get("action"), loc + ".action")
            if action not in ACTIONS or set(step) - {"action", "target", "value"}:
                raise DataError(f"{loc} 的 action 或字段不受支持")
            if action not in ("goto", "reload", "expect_url"):
                step["target"] = _target(step.get("target"), loc + ".target")
            elif "target" in step:
                raise DataError(f"{loc} 不接受 target")
            if action == "expect_count":
                value = step.get("value")
                if type(value) is not int or value < 0:
                    raise DataError(f"{loc}.value 必须为非负整数")
            elif action not in ("reload", "click", "expect_visible", "expect_hidden"):
                if action in ("fill", "expect_text", "expect_value") and isinstance(step.get("value"), str):
                    pass
                else:
                    text(step.get("value"), loc + ".value")
                if action in ("goto", "expect_url") and origin(urljoin(base_url, step["value"])) not in result.allowed_origins:
                    raise DataError(f"{loc} 的 URL 不在 allowed_origins 中")
                if action == "upload":
                    file = (Path(path).resolve().parent / step["value"]).resolve()
                    if not file.is_file():
                        raise DataError(f"{loc} 的上传文件不存在")
                    step["value"] = str(file)
                if action == "fill_env":
                    result.secret_envs.add(step["value"])
            elif "value" in step:
                raise DataError(f"{loc} 不接受 value")
            steps.append(step)
        if steps[-1]["action"] not in ASSERTIONS:
            raise DataError(f"{where} 必须以业务结果断言结束")
        if int(minimum[1]) > int(level[1]):
            continue
        result.checks.append(CheckSpec(
            id=f"scenario-{identifier}", title=title, level=minimum, module=module,
            run=lambda ctx, plan=steps: _execute(ctx, plan, result.allowed_origins),
            steps=[describe(step) for step in steps],
            expected=[describe(step) for step in steps if step["action"] in ASSERTIONS],
            preconditions=preconditions, active=any(step["action"] in ACTIVE for step in steps),
        ))
    return result
