#!/usr/bin/env python3
"""
api_smoke.py —— API 批量冒烟测试脚本

从 YAML/JSON 配置文件读入接口列表，依次请求并断言状态码、响应时间、可选业务字段。
从完整 Skill 目录运行；复制使用时同时保留 data_contract.py 和 scan_lib/redaction.py。

配置文件示例（smoke.yaml）：
    base_url: https://staging.example.com
    default_timeout: 5
    auth:
      type: bearer
      token_env: API_TOKEN
    cases:
      - name: health check
        method: GET
        path: /health
        expect_status: 200
        max_ms: 300
      - name: get profile
        method: GET
        path: /api/user/profile
        expect_status: 200
        expect_json:
          code: 0
        max_ms: 500
      - name: list products
        method: GET
        path: /api/products?page=1
        expect_status: 200
        max_ms: 800

依赖：
    pip install requests pyyaml

用法：
    python api_smoke.py smoke.yaml
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from data_contract import DataError, load_document, object_map, text
from scan_lib.redaction import Redactor
from urllib.parse import urlsplit

try:
    import requests
except ImportError:
    print("请先安装依赖：pip install requests pyyaml", file=sys.stderr)
    raise


@dataclass
class CaseResult:
    name: str
    passed: bool
    status_code: int | None
    elapsed_ms: float
    reasons: list[str] = field(default_factory=list)


def load_config(path: str) -> dict[str, Any]:
    cfg = object_map(load_document(path), "config")
    address = text(cfg.get("base_url"), "base_url")
    parsed = urlsplit(address)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise DataError("base_url 必须是无内嵌凭据的 HTTP/HTTPS 地址")
    cases = cfg.get("cases")
    if not isinstance(cases, list) or not cases:
        raise DataError("cases 必须是非空列表，零用例不能视为通过")
    timeout = cfg.get("default_timeout", 5)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise DataError("default_timeout 必须是正数")
    for index, raw in enumerate(cases):
        case = object_map(raw, f"cases[{index}]")
        route = text(case.get("path"), f"cases[{index}].path")
        if not route.startswith("/") or route.startswith("//"):
            raise DataError(f"cases[{index}].path 必须是站内绝对路径")
        method = case.get("method", "GET")
        if not isinstance(method, str) or method.upper() not in {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}:
            raise DataError(f"cases[{index}].method 不受支持")
        if "name" in case:
            text(case["name"], f"cases[{index}].name")
        expected_status = case.get("expect_status", 200)
        if type(expected_status) is not int or not 100 <= expected_status <= 599:
            raise DataError(f"cases[{index}].expect_status 必须是有效 HTTP 状态码")
        for field_name in ("timeout", "max_ms"):
            value = case.get(field_name)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
                raise DataError(f"cases[{index}].{field_name} 必须是正数")
        if "expect_json" in case:
            object_map(case["expect_json"], f"cases[{index}].expect_json")
    if "auth" in cfg:
        cfg["auth"] = object_map(cfg["auth"], "auth")
        for field_name in ("token", "token_env", "value", "value_env", "header"):
            if field_name in cfg["auth"]:
                text(cfg["auth"][field_name], f"auth.{field_name}")
    return cfg


def build_headers(auth: dict[str, Any] | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if not auth:
        return headers
    if auth.get("type") == "bearer":
        token = auth.get("token") or os.environ.get(auth.get("token_env", ""), "")
        if not isinstance(token, str) or not token:
            raise DataError("缺少 bearer 认证凭据")
        headers["Authorization"] = f"Bearer {token}"
    elif auth.get("type") == "apikey":
        header = text(auth.get("header"), "auth.header")
        value = auth.get("value") or os.environ.get(auth.get("value_env", ""), "")
        if not isinstance(value, str) or not value:
            raise DataError("缺少 API key 认证凭据")
        headers[header] = value
    else:
        raise DataError("auth.type 必须为 bearer 或 apikey")
    return headers


def dict_subset_match(actual: Any, expected: dict[str, Any]) -> tuple[bool, str]:
    """仅校验 expected 中出现的字段。"""
    if not isinstance(actual, dict):
        return False, f"响应不是 JSON 对象，实际类型 {type(actual).__name__}"
    for k, v in expected.items():
        if k not in actual:
            return False, f"缺少字段 `{k}`"
        if actual[k] != v:
            return False, f"字段 `{k}` 期望 {v!r}，实际 {actual[k]!r}"
    return True, ""


def run_case(base_url: str, headers: dict[str, str], default_timeout: float, case: dict[str, Any]) -> CaseResult:
    name = case.get("name", case.get("path", "<unnamed>"))
    method = case.get("method", "GET").upper()
    url = base_url.rstrip("/") + case["path"]
    body = case.get("body")
    timeout = case.get("timeout", default_timeout)
    expect_status = case.get("expect_status", 200)
    max_ms = case.get("max_ms")
    expect_json = case.get("expect_json")

    t0 = time.perf_counter()
    try:
        resp = requests.request(method, url, json=body, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return CaseResult(name, False, None, elapsed_ms, [f"请求异常：{e}"])

    elapsed_ms = (time.perf_counter() - t0) * 1000
    reasons: list[str] = []

    if resp.status_code != expect_status:
        reasons.append(f"状态码期望 {expect_status}，实际 {resp.status_code}")

    if max_ms is not None and elapsed_ms > max_ms:
        reasons.append(f"响应 {elapsed_ms:.0f}ms 超过阈值 {max_ms}ms")

    if expect_json is not None:
        try:
            body_json = resp.json()
        except ValueError:
            reasons.append("响应不是合法 JSON")
        else:
            ok, msg = dict_subset_match(body_json, expect_json)
            if not ok:
                reasons.append(msg)

    return CaseResult(name, not reasons, resp.status_code, elapsed_ms, reasons)


def main() -> int:
    parser = argparse.ArgumentParser(description="API 批量冒烟测试")
    parser.add_argument("config", help="YAML/JSON 配置文件")
    parser.add_argument("--fail-fast", action="store_true", help="遇到首次失败立即中止")
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        base_url = cfg["base_url"]
        default_timeout = float(cfg.get("default_timeout", 5))
        headers = build_headers(cfg.get("auth"))
    except (DataError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    redactor = Redactor([value.removeprefix("Bearer ") for value in headers.values()])

    results: list[CaseResult] = []
    print(f"▶ 目标：{redactor.text(base_url)}")
    print(f"▶ 用例：{len(cfg.get('cases', []))} 条\n")

    for case in cfg.get("cases", []):
        r = run_case(base_url, headers, default_timeout, case)
        results.append(r)
        status = "PASS" if r.passed else "FAIL"
        code = r.status_code if r.status_code is not None else "---"
        print(f"[{status}] {code} {r.elapsed_ms:6.0f}ms  {redactor.text(r.name)}")
        for reason in r.reasons:
            print(f"       └─ {redactor.text(reason)}")
        if args.fail_fast and not r.passed:
            break

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"\n合计：{passed}/{total} 通过")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
