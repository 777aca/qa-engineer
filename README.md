# qa-engineer

面向测试工程师的 Agent Skill，提供用例设计、API/UI 自动化、探索测试、性能/App 测试参考及缺陷报告工作流。

作者：波波啾

## 能力与边界

- 按测试层级加载资料，复用用户已经给出的范围、档位、平台和授权。
- 默认保留用例清单；探索任务默认交付用例表与 Bug 表，用户指定格式优先。
- 扫描器区分 Pass、Fail、Skipped、Blocked、Error 和 NeedsReview；零缺陷不等于全部通过。
- 内置页面检查和有限登录规则可直接运行；业务搜索、筛选、编辑、上传等流程通过声明式场景配置。
- L0–L4 是检查深度，不代表所有网站功能已覆盖。移动端使用 Chromium 模拟，不代表真机或 Safari 验证。
- 性能、原生 App、深度可访问性和安全审计有专用工作流参考；内置扫描器不自动完成这些专项。

## 安装

把整个目录放入宿主支持的 Skill 目录。例如 Claude Code：

```powershell
Copy-Item -Recurse . "$env:USERPROFILE/.claude/skills/qa-engineer"
```

需要运行 Python 脚本时，使用 Python 3.9+，建议安装到项目虚拟环境：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m playwright install chromium
```

只进行咨询、读取测试方法参考时不需要安装上述依赖。Word/PPT 等格式按宿主实际具备的文档工具生成；依赖不足时说明替代方案。

## 快速使用

以下命令在 Skill 根目录执行；也可以用完整脚本路径从其他目录调用。目标页面和操作必须属于用户已授权范围。

```powershell
# 只读首屏冒烟
python -X utf8 scripts/scan.py --url http://localhost:3000 --level L0

# 已获授权的业务场景；先按实际页面修改示例定位器
python -X utf8 scripts/scan.py --url http://localhost:3000 --level L2 --config samples/scenarios.yaml --allow-submit

# 从同一份数据生成不同格式
python -X utf8 scripts/cases_to_xlsx.py samples/sample_cases.yaml -o samples/out/cases.xlsx
python -X utf8 scripts/cases_to_xmind.py samples/sample_cases.yaml -o samples/out/cases.xmind
python -X utf8 scripts/bugs_to_xlsx.py samples/sample_bugs.yaml -o samples/out/bugs.xlsx
```

扫描默认输出到 samples/out/，包含用例与缺陷的 JSON/YAML/Excel、覆盖摘要和平台证据。退出码 0 为已执行范围通过，1 为失败或待复核，2 为阻塞、执行错误或没有有效执行结果。L1+ 未配置适用业务场景时明确报告业务覆盖阻塞。

详细的场景格式、登录态、权限参数、证据保护与测试方法见 [扫描器说明](docs/scan-runner.md)。

## 目录

| 目录/文件 | 用途 |
|---|---|
| SKILL.md | 精简入口、任务路由与必要约束 |
| references/ | 测试设计、API、UI、性能、App、探索、报告与导出方法 |
| scripts/scan.py、scripts/scan_lib/ | 独立状态的检查执行器与业务场景 |
| scripts/data_contract.py | 数据校验与旧字段兼容 |
| scripts/cases_to_xlsx.py、cases_to_xmind.py、bugs_to_xlsx.py | 标准报告转换器 |
| scripts/api_smoke.py | YAML/JSON 驱动的 API 冒烟 |
| scripts/new_test_case.py、new_bug_report.py | 单条用例和缺陷模板 |
| samples/ | 结构化示例及业务场景示例 |
| tests/ | 只访问本机临时页面的回归测试 |
| evals/ | Skill 真实任务行为评测用例 |
| docs/ | 使用说明与数据/执行契约 |

## 开发验证

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -X utf8 scripts/test.py
```

只跑无需浏览器的校验：`python -X utf8 scripts/test.py -m "not browser"`。测试使用假凭据、临时文件及回环地址，不访问真实业务系统。

发布前还应在干净会话运行 evals/evals.json 中的任务，对照旧版检查误报、遗漏、覆盖陈述和额外询问。自动化回归通过不能替代 Skill 行为评测。

## 参考资料

- [用例设计](references/test-design.md)
- [API 测试](references/api-testing.md)
- [UI E2E](references/ui-e2e-playwright.md)
- [性能测试](references/performance-testing.md)
- [App 测试](references/app-testing.md)
- [探索测试](references/exploratory-testing.md)
- [缺陷报告](references/bug-report.md)
- [产出格式](references/output-formats.md)

## License

MIT © 2026 波波啾
