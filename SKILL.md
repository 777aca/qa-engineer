---
name: qa-engineer
description: 面向测试工程师的专业工作流技能，涵盖需求分析、测试用例设计、API 接口测试、UI E2E 自动化、性能压测、App 自动化、Bug 定位与规范报告。按测试层级（而非开发技术栈）组织，适用于 Vue/React/Next/Nuxt/UniApp 前端、PHP/Java/Go/Python 后端、Flutter App 等多种被测对象。当用户请求设计测试用例、编写测试计划、编写/调试自动化脚本（Playwright/pytest/Appium/Locust/k6 等）、撰写 Bug 报告、分析失败日志、定位缺陷、进行性能压测或接口冒烟时触发。
---

# QA Engineer Skill

## 概览

本技能面向**测试工程师**日常工作场景，按**测试层级**（而非开发技术栈）组织知识与模板。核心原则：
- **黑盒/灰盒视角优先**：大多数测试工作与被测系统的开发语言无关（Vue 或 React 的 UI 用同一套 Playwright；Java 或 Go 的后端用同一套 HTTP 断言）。
- **方法论 + 可复用产物**：既提供思考框架，也提供可直接套用的模板、脚本。
- **按需加载**：除非任务需要，不要一次性把所有 references 读入上下文。

## 测试工作流决策树

拿到任务后，先判断属于哪一类，再加载对应 reference：

| 任务类型 | 典型关键词 | 加载文件 |
|---------|-----------|---------|
| 需求分析、用例设计、测试计划 | "设计用例"、"测试方案"、"覆盖率分析"、"PRD 评审" | `references/test-design.md` |
| HTTP/REST/GraphQL 接口测试 | "接口测试"、"API 冒烟"、"Postman"、"pytest + requests" | `references/api-testing.md` |
| 浏览器 E2E / UI 自动化 | "Playwright"、"Selenium"、"Cypress"、"UI 自动化" | `references/ui-e2e-playwright.md` |
| 压测、性能、基准 | "Locust"、"k6"、"JMeter"、"QPS"、"压测" | `references/performance-testing.md` |
| 移动 App 自动化 | "Appium"、"Flutter 测试"、"小程序自动化" | `references/app-testing.md` |
| Bug 定位、失败分析、报告撰写 | "Bug 报告"、"复现"、"定位"、"失败日志分析" | `references/bug-report.md` |

一次任务常跨多层（例如"写一个登录 E2E，失败后要提 Bug"），可组合加载多个 reference。

## 核心原则（始终适用）

### 1. 永远先明确"验证什么"

在动手写用例或脚本前，必须先答清楚：
- **输入**：入参/前置状态/环境是什么？
- **期望输出**：应当返回什么数据、UI 呈现什么、副作用是什么？
- **验收标准**：用何种断言判定通过/失败？

拒绝"只点一下看看能不能跑"式用例——这叫"冒烟"不叫"测试"。

### 2. 用例要有层次，不要一把梭

对任何新功能，至少覆盖以下用例层次：
1. **主路径 Happy Path**（1~2 条）
2. **边界值**（每个数值字段必写）
3. **异常/错误路径**（空值、超长、非法字符、权限不足、网络故障）
4. **状态迁移**（如登录 → 登出 → 重新登录）
5. **并发/幂等**（适用接口/事务类）
6. **兼容性**（多浏览器、多分辨率、多 OS，仅在 UI/App 场景）

### 3. 自动化脚本必须"可读 + 稳定 + 快速"

- **可读**：用例名称即断言意图，避免 `test1`、`testLogin2`。推荐 `应当_在_条件下_返回_结果` 句式。
- **稳定**：禁止 `sleep(3000)` 硬等待，一律使用显式等待（元素可见、网络空闲、状态条件）。
- **快速**：优先走 API 完成前置数据构造，UI 只验证"用户视角"。不要用 UI 操作去填充 100 条测试数据。

### 4. Bug 报告必须"可复现 + 有证据"

任何 Bug 都应在报告中提供：标题（一句话结论）、环境、复现步骤、期望、实际、附件（截图/日志/HAR）、严重度与优先级。详见 `references/bug-report.md`。

## 通用执行流程

对于每一个测试任务，推荐按如下流程推进：

1. **理解被测对象**：读 PRD / 需求描述 / 接口文档，必要时问业务方确认歧义
2. **识别测试层级**：查上面的决策树，加载对应 reference
3. **设计用例**：输出用例清单（标题 + 优先级 + 预期），等待评审或直接动手
4. **执行/编码**：
   - 手工测试：按用例清单逐条执行
   - 自动化：基于对应 reference 中的模式编写脚本，放入项目 `tests/` 目录
5. **分析结果**：失败用例用 `references/bug-report.md` 撰写 Bug；通过则总结覆盖率与风险
6. **归档**：用例入库、脚本提交、报告交付

## 代码与产物放置约定

当用户项目中引入本技能产出的测试资产时，遵循：

- 自动化测试脚本 → `tests/` 或 `e2e/` 目录（遵循项目现有约定）
- 用例文档（Markdown）→ `docs/testing/` 或项目的 `discuss/` 目录
- Bug 报告（临时讨论）→ `discuss/bugs/`
- 测试日志 → 统一输出到 `logs/`（遵循用户 CLAUDE.md 约定）

严格遵守用户 CLAUDE.md 中的规则：
- 代码文件单文件不超过 1500 行（JS/TS）/ 2000 行（Java/Go/Rust/Python）
- 单目录文件不超过 10 个，超过则分子目录
- 禁用 CommonJS，优先 TypeScript
- Run & Debug 通过 `scripts/*.js` 脚本启停，不直接用 npm/pnpm/uv/python 命令

## Scripts 资源

本技能提供以下可复用脚本：

- `scripts/new_test_case.py`：根据功能名生成标准化的测试用例 Markdown 模板
- `scripts/new_bug_report.py`：生成符合规范的 Bug 报告骨架
- `scripts/api_smoke.py`：对一批接口做快速冒烟测试（可复制到项目自定义）

脚本仅为参考起点，使用时建议复制到项目内并按需改造，不要直接依赖 Skill 目录路径。

## References 资源

- `references/test-design.md` — 用例设计方法论（等价类、边界值、判定表、场景法、正交法、状态迁移）
- `references/bug-report.md` — Bug 定位技巧与规范报告模板
- `references/api-testing.md` — API 接口测试（与后端栈无关）
- `references/ui-e2e-playwright.md` — UI E2E 自动化（与前端栈无关，以 Playwright 为首选）
- `references/performance-testing.md` — 性能/压力测试（Locust、k6、JMeter 对比与模式）
- `references/app-testing.md` — 移动 App 测试（Appium 通用 + Flutter 专属）
