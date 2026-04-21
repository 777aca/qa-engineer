# qa-engineer

> 面向测试工程师的 Claude Code Skill —— 覆盖用例设计、API / UI E2E / 性能 / App 自动化、Bug 定位与规范报告。

一个按**测试层级**（而非开发技术栈）组织的专业工作流技能包。无论被测系统用 Vue、React、Next、Nuxt、UniApp（前端），还是 PHP、Java、Go、Python（后端），亦或 Flutter App，都能开箱即用。

## ✨ 为什么是"测试层级"而不是"技术栈"

作为测试工程师，绝大多数工作是**黑盒/灰盒**的：

- UI E2E 测试对 Vue / React / Next / Nuxt **一视同仁**（Playwright 不关心前端框架）
- API 接口测试对 PHP / Java / Go / Python **一视同仁**（HTTP + JSON 不分后端）
- 压测工具打的是接口，**不看后端实现**

所以本 Skill 按 **测试动作的层级** 组织，一个 Skill 覆盖全部上述场景。

## 📦 Skill 结构

```
qa-engineer/
├── SKILL.md                          # 入口：启动协议 + 工作流决策树 + 核心原则
├── references/                       # 按需加载，节省上下文
│   ├── test-design.md                # 用例设计方法论（等价类/边界值/判定表/场景法/状态迁移/正交法）
│   ├── bug-report.md                 # Bug 定位 + 规范报告模板
│   ├── api-testing.md                # API 接口测试（后端栈无关）
│   ├── ui-e2e-playwright.md          # UI E2E 自动化（前端栈无关）
│   ├── performance-testing.md        # 性能压测（Locust / k6 / JMeter）
│   ├── app-testing.md                # App 测试（Appium + Flutter integration_test）
│   └── output-formats.md             # 各种产出格式（xlsx/xmind/docx/pptx）的生成方法
├── scripts/                          # 可复用脚本
│   ├── new_test_case.py              # 生成标准化测试用例 Markdown
│   ├── new_bug_report.py             # 生成规范 Bug 报告骨架
│   ├── api_smoke.py                  # YAML 驱动的接口批量冒烟
│   ├── cases_to_xlsx.py              # 用例 YAML/JSON → 规范 Excel（可导入禅道/TestLink）
│   └── cases_to_xmind.py             # 用例 YAML/JSON → 真正的 .xmind 文件
└── samples/                          # 示例数据
    └── sample_cases.yaml             # 5 条示例用例，可直接用于验证脚本
```

## 🤝 启动协议（Skill 的使用方式）

本 Skill 在触发后，**会主动询问你一份结构化清单**（而不是自作主张地开干），清单包含：

1. **任务类型**（单选）：用例设计 / API 测试 / UI E2E / 性能压测 / App 自动化 / Bug 报告 / 测试计划 / 报告撰写
2. **可用材料**（多选）：PRD / 接口文档 / URL+账号 / 截图录屏 / Bug 现象 / 代码片段 / 历史用例 / 什么都没有
3. **产出格式**（多选）：Markdown / Excel (.xlsx) / XMind (.xmind) / XMind 大纲 / Word (.docx) / PPT (.pptx) / 自动化脚本

你勾选后 Claude 再开始工作。只有在**纯咨询问题**（如"什么是边界值法"）或**你明确说了"不用问"**时才跳过。

## 📋 支持的产出格式

| 格式 | 用途 | 实现方式 |
|------|-----|---------|
| **Markdown** | 对话中直接展示、git 版本化 | 原生 |
| **Excel (.xlsx)** | 团队评审、禅道/TestLink 导入 | `scripts/cases_to_xlsx.py`（含禅道格式） |
| **XMind (.xmind)** | 评审演示、个人理清思路 | `scripts/cases_to_xmind.py`（双击打开） |
| **XMind 大纲** | 零依赖，可粘贴 XMind/幕布/MindMaster | Markdown 层级 |
| **Word (.docx)** | 正式测试方案/计划/报告 | 调用 `document-skills:docx` |
| **PPT (.pptx)** | 团队汇报、迭代总结 | 调用 `document-skills:pptx` |

详见 [`references/output-formats.md`](./references/output-formats.md)。

## 🎯 触发场景

当您的 Prompt 中包含以下意图时，Claude 会自动调用该 Skill：

- 设计测试用例、编写测试计划、测试方案、覆盖率分析
- 编写/调试自动化脚本（Playwright / Cypress / Selenium / Appium / pytest / Locust / k6 等）
- API 接口冒烟、契约测试、Schema 校验
- 撰写 Bug 报告、分析失败日志、定位缺陷
- 性能压测、基准测试、瓶颈分析
- App 自动化（原生 / Flutter / UniApp / 小程序）

## 🚀 安装与使用

### 方式 1：本地 Skill 目录（个人使用）

复制整个目录到 Claude Code 的 skills 路径：

```bash
# macOS / Linux
cp -r qa-engineer ~/.claude/skills/

# Windows
xcopy /E /I qa-engineer %USERPROFILE%\.claude\skills\qa-engineer
```

### 方式 2：打包为 .skill 分发

使用 Anthropic 官方 `skill-creator` 提供的打包脚本：

```bash
python /path/to/skill-creator/scripts/package_skill.py ./qa-engineer ./dist
```

产出 `dist/qa-engineer.skill`（zip 格式），可分发给团队成员。

### 方式 3：直接使用 scripts（脱离 Skill 框架）

仓库内的 `scripts/` 目录可独立使用：

```bash
# 1. 生成测试用例模板
python scripts/new_test_case.py 登录 "正确邮箱密码登录成功" --priority P0 --output tc-login-001.md

# 2. 生成 Bug 报告骨架
python scripts/new_bug_report.py "已完成订单申请退款后页面白屏" --severity S2 --priority P1 --output bug-001.md

# 3. YAML 驱动的接口冒烟
python scripts/api_smoke.py smoke.yaml

# 4. 批量用例 YAML → 规范 Excel
python scripts/cases_to_xlsx.py samples/sample_cases.yaml -o output/订单测试用例.xlsx
#   禅道导入格式：
python scripts/cases_to_xlsx.py samples/sample_cases.yaml --format zentao -o output/订单_禅道.xlsx

# 5. 批量用例 YAML → XMind 思维导图
python scripts/cases_to_xmind.py samples/sample_cases.yaml -o output/订单测试用例.xmind
```

脚本 4 和 5 使用统一的 YAML 格式（见 `samples/sample_cases.yaml`），保证相同数据源可产出多种格式。

## 📋 工作流决策树

拿到任务后，按下表加载对应 reference：

| 任务类型 | 典型关键词 | 加载文件 |
|---------|-----------|---------|
| 需求分析、用例设计、测试计划 | "设计用例"、"测试方案"、"覆盖率" | `references/test-design.md` |
| HTTP/REST/GraphQL 接口测试 | "接口测试"、"API 冒烟"、"Postman" | `references/api-testing.md` |
| 浏览器 E2E / UI 自动化 | "Playwright"、"Selenium"、"Cypress" | `references/ui-e2e-playwright.md` |
| 压测、性能、基准 | "Locust"、"k6"、"JMeter"、"QPS" | `references/performance-testing.md` |
| 移动 App 自动化 | "Appium"、"Flutter 测试"、"小程序自动化" | `references/app-testing.md` |
| Bug 定位、失败分析、报告 | "Bug 报告"、"复现"、"定位" | `references/bug-report.md` |

一次任务常跨多层（例如"写登录 E2E，失败后提 Bug"），可组合加载多个 reference。

## 🧭 核心原则

1. **永远先明确"验证什么"**：输入、期望输出、验收标准三要素齐备才动手
2. **用例要有层次**：Happy Path + 边界值 + 异常路径 + 状态迁移 + 并发/幂等 + 兼容性
3. **自动化三要求**：可读 + 稳定（禁硬等待）+ 快速（数据走 API）
4. **Bug 报告可复现 + 有证据**：标题、环境、步骤、期望、实际、附件、严重度、优先级

## 📚 详细内容

各 reference 文档为独立章节，可直接阅读学习：

- [用例设计方法论](./references/test-design.md) — 7 种设计方法 + 用例模板 + 测试计划模板
- [Bug 报告规范](./references/bug-report.md) — 分层排查清单、严重度/优先级、复现偶现 Bug 的技巧
- [API 接口测试](./references/api-testing.md) — pytest + requests 骨架、Postman/Newman、契约校验
- [UI E2E 自动化](./references/ui-e2e-playwright.md) — Playwright 首选，PO 模式、选择器策略、反脆弱
- [性能压测](./references/performance-testing.md) — Locust / k6 / JMeter 对比 + 场景建模 + 瓶颈定位
- [App 自动化](./references/app-testing.md) — Appium 通用 + Flutter 专属方案 + 小程序/UniApp/H5 混合
- [产出格式指南](./references/output-formats.md) — Markdown / xlsx / xmind / docx / pptx 的生成策略

## 🤝 贡献

欢迎 PR 补充：
- 更多测试场景（安全测试、可访问性、国际化等）
- 其他工具模板（Karate、RestAssured、Tauri 测试等）
- 行业专属测试规范（金融、医疗、车联网等）

## 📄 License

MIT © 2026
