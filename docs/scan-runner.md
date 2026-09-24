# 扫描器与业务场景

扫描器使用 Python 3.9+ 和 Playwright Chromium。保留 L0–L4 与 pc/mobile/both；内置规则覆盖页面基础行为、有限的密码登录检查、响应式取证和部分安全/可访问性候选。业务流程通过可配置场景验证，不能仅凭运行高档位宣称完成全站测试。

## 安装与运行

在 Skill 根目录运行；从其他项目调用时将脚本、配置和输出路径换成完整路径：

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python -X utf8 scripts/scan.py --url http://localhost:3000 --level L0
```

已有授权允许在该测试环境提交交互时：

```powershell
python -X utf8 scripts/scan.py --url http://localhost:3000 --level L2 --platform pc --config samples/scenarios.yaml --allow-submit
```

示例场景使用“搜索”“名称”等标签和 test_id；先观察实际页面，再调整配置。它不是所有网站通用的现成用例。

## 参数与权限

| 参数 | 行为 |
|---|---|
| --level | 默认 L2；只执行该档位及更低档位的适用检查和场景 |
| --platform | 默认 pc；both 分别执行并保留独立结果 |
| --config | 业务场景 JSON/YAML，执行前整体校验 |
| --out-dir | 默认 samples/out/scan-时间戳；用户项目的输出目录可显式传入 |
| --storage-state | Playwright 本地登录态文件，各检查独立加载；不写回此文件 |
| --allow-submit | 把已有交互/请求授权传给执行器；允许 fill/click/press/select/upload 和非只读请求 |
| --allow-security-tests | 允许内置主动安全探针；提交型探针还需 --allow-submit |
| --timeout-ms | 每项操作等待上限，默认 10000；范围 1–120000 |
| --ignore-https-errors | 显式接受测试环境无效证书，默认不忽略 |
| --trace | 仅为失败、错误或待复核项保存原始 Trace；默认关闭 |

默认阻止非 GET/HEAD/OPTIONS 请求，以及未声明域名的导航。启用提交后，非只读请求也限制在 allowed_origins。页面资源的普通 GET 可以跨域；外部域名的授权由用户给定，不能自动扩展。

对于使用 POST 查询数据的页面，默认模式可能出现 Blocked。这说明执行权限不足，不代表该接口有 Bug。选择档位不能自动授权提交、删除、支付、探针或压测。

内置登录检查使用 TEST_USER、TEST_PASS 和 TEST_LOGIN_SUCCESS_SELECTOR。成功选择器必须来自实际页面；没有账号或成功判据会记录 Blocked。复杂登录、SSO、验证码优先使用用户已有的受控登录态或明确配置场景，不依赖 SGIP 等项目专属变量。

## 场景格式

顶层字段：schema_version=1、可选 ready_selector、可选 allowed_origins、scenarios 数组。默认 ready_selector=body；异步页面应指定能代表就绪的关键元素。

每个场景需要唯一的 id、title、module、steps；level 默认 L1，preconditions 是可选的前置条件说明。说明本身不执行；运行时需要验证的前置条件用断言步骤表达。id 只用字母、数字、连字符和下划线。

```yaml
schema_version: 1
ready_selector: '[data-testid="app-ready"]'
allowed_origins:
  - https://login.example.test
scenarios:
  - id: save-name
    title: 保存后刷新仍显示新名称
    module: 资料编辑
    level: L2
    steps:
      - action: fill
        target: {label: 名称}
        value: 测试名称
      - action: click
        target: {role: button, name: 保存}
      - action: expect_text
        target: {test_id: save-status}
        value: 已保存
      - action: reload
      - action: expect_value
        target: {label: 名称}
        value: 测试名称
```

定位 target 仅支持一种形式：role+name、label、test_id、css。role/name、label 使用精确匹配；多匹配不静默选择第一个。凭据值通过 fill_env 从环境读取，不写入配置。

| action | 输入与含义 |
|---|---|
| goto | value 为相对目标 URL 的路径或授权地址 |
| reload | 刷新当前页面，无 target/value |
| fill / fill_env | target + value；后者 value 是环境变量名 |
| click | target，无 value |
| press | target + value，例如 Enter |
| select | target + value，选择原生 select 的 option value |
| upload | target + value；文件路径相对配置文件所在目录 |
| expect_visible / expect_hidden | target，无 value |
| expect_text / expect_value | target + value，精确文本或输入值断言 |
| expect_count | target + 非负整数 value |
| expect_url | value 为预期完整 URL 或相对路径，无 target |

场景必须以结果断言结束；未知动作、未知字段、冲突定位器、重复 ID、越界地址等在浏览器启动前报错。配置不支持任意代码执行。执行动作失败计 Error；明确的结果断言失败计 Fail；缺少环境变量计 Blocked。

每项检查/场景使用独立 BrowserContext，场景内部步骤共享状态，因此支持保存后刷新等闭环。不能依赖前一场景的写入状态；需要共享的测试数据由已授权的项目 fixture 建立。

## 输出与退出码

- 根目录：summary.json、test-cases.json/yaml/xlsx、bugs.json/yaml、bug-report.xlsx。
- 平台目录：checks.json、findings.json、summary.json，以及按检查 ID 保存的脱敏证据 JSON/截图。
- 开启 --trace 时：平台目录/private-traces/，与普通交付隔离，原始内容可能含凭据或个人信息，需本地保管和交付前复核。

| 退出码 | 含义 |
|---|---|
| 0 | 至少一项 Pass，其他项仅为明确不适用的 Skipped；只代表已执行范围 |
| 1 | 有 Fail 或 NeedsReview，且没有阻塞/执行错误 |
| 2 | 配置/依赖/环境错误、任意 Blocked/Error，或没有实际通过/失败检查 |

L1+ 没有适用业务场景时会增加一条业务覆盖 Blocked。NeedsReview 不并入 Pass；Skipped 不进入已完成计数；没有缺陷不等于完成测试。

普通证据只保留必要的日志、请求方法/状态/URL 和 DOM 结构；不采集请求体、响应体或存储凭据值。日志及 URL 做脱敏，截图遮罩输入控件、data-qa-sensitive 区域和已知凭据文本。任意业务个人信息无法仅靠通用规则自动识别，交付前仍要检查。截图失败不生成虚假图片路径，并标记证据采集错误。

## 回归与评测

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -X utf8 scripts/test.py
python -X utf8 scripts/test.py -m "not browser"
```

回归测试只访问临时本机 HTTP 服务，验证正常页面、故障页面、权限阻塞、状态隔离、业务保存闭环、凭据脱敏和导出一致性。测试不使用真实账号或外部业务接口。

evals/evals.json 提供 Skill 行为评测场景。对比新旧版本时分别在干净会话执行相同任务，记录触发是否正确、询问次数、误报/漏报、证据完整性、耗时和 Token；自动化脚本测试通过不代表这组行为评测已经执行。

## 依据

- [Agent Skills 编写实践](https://agentskills.io/skill-creation/best-practices)
- [Agent Skills 评测](https://agentskills.io/skill-creation/evaluating-skills)
- [Playwright 最佳实践](https://playwright.dev/docs/best-practices)
- [Playwright 登录态](https://playwright.dev/python/docs/auth)
- [OWASP 日志指南](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
