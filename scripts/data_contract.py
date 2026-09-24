"""用例与缺陷的公共输入契约，错误信息不回显原始输入。"""
from __future__ import annotations

import json
from pathlib import Path

RESULTS = {"Pass", "Fail", "Blocked", "Skipped", "Error", "NeedsReview", "N/A"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
LEVELS = {"L0", "L1", "L2", "L3", "L4"}
PLATFORMS = {"pc", "mobile", "both"}
CASE_FIELDS = {"id", "title", "module", "sub_module", "priority", "preconditions", "steps", "expected",
               "case_type", "design_method", "tags", "related_req", "actual", "executor", "result",
               "level", "platform", "linked_bug", "evidence", "duration_ms"}
BUG_FIELDS = {"id", "title", "category", "module", "severity", "priority", "status", "reproducible",
              "steps", "expected", "actual", "evidence", "suggestion", "tags", "level", "platform"}


class DataError(ValueError):
    pass


def object_map(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise DataError(f"{location} 必须是字符串键的对象")
    return dict(value)


def text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"{location} 必须是非空字符串")
    return value


def load_document(path: str) -> object:
    raw = Path(path).read_text(encoding="utf-8-sig")
    if Path(path).suffix.lower() in (".yaml", ".yml"):
        import yaml
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError:
            raise DataError("输入不是合法 YAML，请检查文件格式") from None
    try:
        return json.loads(raw)
    except ValueError:
        raise DataError("输入不是合法 JSON，请检查文件格式") from None


def _enum(row: dict[str, object], key: str, options: set[str], location: str) -> None:
    if key in row and row[key] not in (None, ""):
        if not isinstance(row[key], str) or row[key] not in options:
            raise DataError(f"{location}.{key} 必须是 {' / '.join(sorted(options))}")


def _lines(value: object, location: str, required: bool = False) -> None:
    if isinstance(value, str) and (value.strip() or not required):
        return
    if isinstance(value, list) and (value or not required):
        if all(isinstance(item, str) and item.strip() for item in value):
            return
    raise DataError(f"{location} 必须是文本或非空文本组成的列表")


def _evidence(value: object, location: str) -> None:
    if not isinstance(value, list):
        raise DataError(f"{location} 必须是证据对象列表")
    for index, raw in enumerate(value):
        item = object_map(raw, f"{location}[{index}]")
        text(item.get("type"), f"{location}[{index}].type")
        if not any(isinstance(item.get(key), str) and item[key].strip() for key in ("content", "path", "snippet")):
            raise DataError(f"{location}[{index}] 缺少非空证据内容或路径")


def normalize_case(value: object, location: str = "case") -> dict[str, object]:
    row = object_map(value, location)
    if "precondition" in row:
        if "preconditions" in row and row["preconditions"] != row["precondition"]:
            raise DataError(f"{location} 的 precondition 与 preconditions 冲突")
        row["preconditions"] = row.pop("precondition")
    if set(row) - CASE_FIELDS:
        raise DataError(f"{location} 含未支持的字段，请检查字段拼写")
    for key in ("id", "title", "module", "priority"):
        text(row.get(key), f"{location}.{key}")
    for key in ("steps", "expected"):
        _lines(row.get(key), f"{location}.{key}", required=True)
    for key in ("preconditions", "tags", "linked_bug"):
        if key in row:
            _lines(row[key], f"{location}.{key}")
    for key, options in (("priority", PRIORITIES), ("result", RESULTS), ("level", LEVELS), ("platform", PLATFORMS)):
        _enum(row, key, options, location)
    if "evidence" in row:
        _evidence(row["evidence"], f"{location}.evidence")
    if "duration_ms" in row and (type(row["duration_ms"]) is not int or row["duration_ms"] < 0):
        raise DataError(f"{location}.duration_ms 必须是非负整数")
    return row


def normalize_document(value: object, kind: str = "cases") -> dict[str, object]:
    data = object_map(value, "document")
    if "schema_version" in data and (type(data["schema_version"]) is not int or data["schema_version"] != 1):
        raise DataError("document.schema_version 必须为 1")
    rows = data.get(kind)
    if not isinstance(rows, list):
        raise DataError(f"document.{kind} 必须是列表（允许空列表）")
    normalized: list[dict[str, object]] = []
    ids: set[str] = set()
    for index, value in enumerate(rows):
        location = f"{kind}[{index}]"
        row = normalize_case(value, location) if kind == "cases" else object_map(value, location)
        identifier = text(row.get("id"), f"{location}.id")
        if identifier in ids:
            raise DataError(f"{location}.id 重复")
        ids.add(identifier)
        if kind == "bugs":
            if set(row) - BUG_FIELDS:
                raise DataError(f"{location} 含未支持的字段，请检查字段拼写")
            for key in ("title", "module", "severity", "priority"):
                text(row.get(key), f"{location}.{key}")
            for key, options in (("severity", {"S1", "S2", "S3", "S4"}), ("priority", PRIORITIES),
                                 ("level", LEVELS), ("platform", PLATFORMS),
                                 ("status", {"已确认", "待验证"}),
                                 ("reproducible", {"必现", "偶现", "一次", "未复现"})):
                _enum(row, key, options, location)
            row.setdefault("status", "待验证")
            row.setdefault("reproducible", "一次")
            if "evidence" in row:
                _evidence(row["evidence"], f"{location}.evidence")
            if row["status"] == "已确认" and not row.get("evidence"):
                raise DataError(f"{location} 已确认缺陷必须提供 evidence")
        normalized.append(row)
    data[kind] = normalized
    return data


def sheet_title(value: object, default: str) -> str:
    return "".join("_" if char in "\\/*?:[]" else char for char in str(value or default))[:31] or default


def literal_cells(workbook) -> None:
    """报告里的测试输入以文本存储，避免 '=' 被当成公式。"""
    for sheet in workbook:
        for row in sheet:
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"
