#!/usr/bin/env python3
"""
cases_to_xmind.py —— 把结构化用例数据转成 .xmind 思维导图文件

产出 XMind ZEN 2020+ 格式（zip 打包的 JSON），可直接双击用 XMind 打开，
也可导入 MindMaster / EdrawMind / 幕布 等大多数脑图软件。

层级结构：
    项目根节点
    └─ 模块
       └─ 子模块
          └─ [Pxx] 用例标题
             ├─ 前置条件
             ├─ 步骤
             └─ 预期

优先级颜色标记：
    P0 = 红色 / P1 = 橙色 / P2 = 黄色 / P3 = 蓝色

用法：
    python cases_to_xmind.py <cases.yaml|cases.json> [-o output.xmind]

依赖：
    仅需标准库（zipfile/json）。YAML 输入需要 pyyaml。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import uuid
import zipfile
from typing import Any


# 优先级 → XMind 官方颜色 marker ID（XMind ZEN 2020+ 支持的内置 marker）
PRIORITY_MARKER = {
    "P0": "priority-1",
    "P1": "priority-2",
    "P2": "priority-3",
    "P3": "priority-4",
}


def _id() -> str:
    return uuid.uuid4().hex


def load_cases(path: str) -> dict[str, Any]:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            print("请先安装依赖：pip install pyyaml", file=sys.stderr)
            raise
        return yaml.safe_load(text)
    return json.loads(text)


def _make_node(title: str, children: list[dict] | None = None,
               markers: list[str] | None = None) -> dict:
    """创建一个 XMind 节点。"""
    node: dict[str, Any] = {
        "id": _id(),
        "title": title,
    }
    if markers:
        node["markers"] = [{"markerId": m} for m in markers]
    if children:
        node["children"] = {"attached": children}
    return node


def build_case_node(case: dict[str, Any]) -> dict:
    """把单条用例转为 XMind 子树。"""
    priority = case.get("priority", "P2")
    title = f"[{priority}] {case.get('title', case.get('id', 'unnamed'))}"

    children: list[dict] = []

    # ID / 需求关联（作为备注信息，放到同一层级）
    meta_items: list[dict] = []
    if case.get("id"):
        meta_items.append(_make_node(f"ID：{case['id']}"))
    if case.get("related_req"):
        meta_items.append(_make_node(f"需求：{case['related_req']}"))
    if case.get("design_method"):
        meta_items.append(_make_node(f"设计方法：{case['design_method']}"))
    if meta_items:
        children.append(_make_node("基本信息", meta_items))

    # 前置条件
    preconditions = case.get("preconditions")
    if preconditions:
        if isinstance(preconditions, (list, tuple)):
            children.append(_make_node(
                "前置条件",
                [_make_node(str(p)) for p in preconditions]
            ))
        else:
            children.append(_make_node(f"前置条件：{preconditions}"))

    # 步骤
    steps = case.get("steps")
    if steps:
        if isinstance(steps, (list, tuple)):
            children.append(_make_node(
                "步骤",
                [_make_node(f"{i+1}. {s}") for i, s in enumerate(steps)]
            ))
        else:
            children.append(_make_node(f"步骤：{steps}"))

    # 预期
    expected = case.get("expected")
    if expected:
        if isinstance(expected, (list, tuple)):
            children.append(_make_node(
                "预期",
                [_make_node(str(e)) for e in expected]
            ))
        else:
            children.append(_make_node(f"预期：{expected}"))

    # 标签
    tags = case.get("tags")
    if tags:
        tag_str = ", ".join(str(t) for t in tags) if isinstance(tags, (list, tuple)) else str(tags)
        children.append(_make_node(f"标签：{tag_str}"))

    markers = [PRIORITY_MARKER[priority]] if priority in PRIORITY_MARKER else None
    return _make_node(title, children, markers=markers)


def group_by(items: list[dict], key: str) -> dict[str, list[dict]]:
    """按指定字段分组，保持出现顺序。"""
    groups: dict[str, list[dict]] = {}
    for it in items:
        k = it.get(key) or "（其他）"
        groups.setdefault(k, []).append(it)
    return groups


def build_content(data: dict[str, Any]) -> list[dict]:
    """构建 XMind content.json 的顶层结构。"""
    project = data.get("project", "测试用例")
    version = data.get("version", "")
    root_title = f"{project} {version}".strip()

    cases = data.get("cases", [])

    # 两级分组：module → sub_module
    module_groups = group_by(cases, "module")
    module_nodes: list[dict] = []
    for module_name, module_cases in module_groups.items():
        sub_groups = group_by(module_cases, "sub_module")
        if len(sub_groups) == 1 and "（其他）" in sub_groups:
            # 无子模块
            sub_nodes = [build_case_node(c) for c in module_cases]
        else:
            sub_nodes = []
            for sub_name, sub_cases in sub_groups.items():
                sub_nodes.append(_make_node(
                    sub_name,
                    [build_case_node(c) for c in sub_cases]
                ))
        module_nodes.append(_make_node(module_name, sub_nodes))

    root_topic = _make_node(root_title, module_nodes)

    sheet = {
        "id": _id(),
        "title": "用例",
        "rootTopic": root_topic,
    }
    return [sheet]


def build_manifest() -> dict:
    return {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
            "manifest.json": {},
        }
    }


def build_metadata(project: str) -> dict:
    return {
        "creator": {
            "name": "qa-engineer skill / cases_to_xmind.py",
            "version": "1.0.0",
        },
        "activeSheetId": "",
        "dataStructureVersion": "2",
    }


def write_xmind(data: dict[str, Any], output: pathlib.Path) -> None:
    content = build_content(data)
    manifest = build_manifest()
    metadata = build_metadata(data.get("project", "测试用例"))

    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        z.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="把结构化用例转成 .xmind 思维导图")
    parser.add_argument("input", help="输入文件：cases.yaml 或 cases.json")
    parser.add_argument("-o", "--output", default=None,
                        help="输出 .xmind 路径；默认 <project>.xmind")
    args = parser.parse_args()

    data = load_cases(args.input)

    if args.output:
        out_path = pathlib.Path(args.output)
    else:
        project = data.get("project", "testcases")
        out_path = pathlib.Path(f"{project}.xmind")

    write_xmind(data, out_path)

    case_count = len(data.get("cases", []))
    print(f"已生成：{out_path}")
    print(f"用例数：{case_count}")
    print("提示：双击可直接用 XMind 打开（ZEN 2020+）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
