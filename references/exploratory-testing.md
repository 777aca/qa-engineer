# 主动探索测试（Exploratory Testing）

当用户**只丢给你一个 URL** 或 **一份前端源码**，却没有 PRD、没有用例清单、也没说"帮我写用例"时，默认走本 reference。目标是扮演测试工程师角色，**主动挖 bug 并汇总成清单**（默认 Excel 汇总表）。

## 目录

- [1. 何时走本流程](#1-何时走本流程)
- [2. 分级选择（L0–L4）](#2-分级选择l0l4)
- [3. 平台选择（PC / 移动端）](#3-平台选择pc--移动端)
- [4. 场景 A：只给 URL](#4-场景-a只给-url)
- [5. 场景 B：只给前端源码](#5-场景-b只给前端源码)
- [6. Bug 挖掘 Checklist（通用）](#6-bug-挖掘-checklist通用)
- [7. 证据收集规则](#7-证据收集规则)
- [8. Bug 清单数据结构](#8-bug-清单数据结构)
- [9. 产出 Excel 汇总表](#9-产出-excel-汇总表)
- [10. 与 bug-report.md 的关系](#10-与-bug-reportmd-的关系)
- [11. 不做的事](#11-不做的事)

---

## 1. 何时走本流程

满足任一即走：

- 用户给了 URL（`http://...` / `https://...`）但没说要做什么具体任务
- 用户给了前端代码片段/文件/仓库但没说要做什么具体任务
- 用户明确说"帮我找找 bug / 看看有什么问题 / 探索一下"
- 在启动协议里 Q1 勾了"主动探索测试"

注意：**这条流程仍然要走启动协议**（除非用户明确说"别问了直接找"）。Q1 选"主动探索测试"后，**必须补问两件事**：

1. **档位**（L0–L4，见第 2 节）——默认 **L2 闭环**
2. **平台**（PC / 移动端 / 两者）——默认 **PC**

Q3 产出格式默认 **Excel (.xlsx) 汇总表**。

---

## 2. 分级选择（L0–L4）

五档**严格递进**：选 Ln 时自动包含 L0 ~ L(n-1) 的全部检查，不跳档、不越权。

### 概览

| 档位 | 名称 | 预计时间 | 追加的问题 |
|-----|------|---------|-----------|
| L0 | 冒烟 Smoke | 2 分钟 | 这环境值不值得继续测？ |
| L1 | 主流程 Happy Path | 5–10 分钟 | 正确数据按正确顺序走得通吗？ |
| L2 | 闭环 End-to-End | 15–20 分钟 | 关键异常分支能优雅处理、数据能闭环一致吗？ |
| L3 | 精细 Detailed | 30–45 分钟 | 每个字段/每种输入/每种尺寸的细节对吗？ |
| L4 | 全面 Comprehensive | 60+ 分钟 | 安全/可访问/性能/代码质量过不过关？ |

### L0 冒烟（2 分钟）

**只回答一个问题**：环境能不能继续测？

检查清单：
- 页面能打开（status 2xx，非白屏）
- 首屏渲染完成（`<title>` 正确、关键元素可见）
- **零 JS 报错**（`pageerror` / `console.error` 为 0）
- 核心资源（JS/CSS/图片/首批接口）无 4xx/5xx/CORS 失败
- **零交互**，不填表单、不点按钮

**前置**：URL
**产出**：0–2 条阻断 bug，或绿灯"可以继续"
**典型场景**：新环境首次对接、发版后 10 分钟回归、CI 每次构建

### L1 主流程（5–10 分钟）

**追加的问题**：用正确数据按正确顺序操作，业务大动脉通不通？

检查清单（在 L0 基础上 +）：
- 走核心正向路径：登录 → 进入主功能 → 典型操作 → 登出
- 只用合法数据、合法顺序
- 每步操作后验证：页面跳转对、关键数据对、关键 UI 对
- **不做**：空值/超长/XSS/权限/a11y/响应式/网络异常

**前置**：URL + 测试账号 + 能说清"核心路径是哪条"
**产出**：3–5 条"挡路型" bug
**典型场景**：新功能第一次联调、确认主干是否可用

### L2 闭环（15–20 分钟）

**追加的问题**：关键分支出错能否优雅处理、数据能否闭环一致？

检查清单（在 L1 基础上 +）：
- **关键异常分支**：空值提交、重复提交（连点）、权限不足、401/403 跳转、网络失败的提示
- **闭环一致性**：创建 → 查询 → 修改 → 删除，前后数据一致；状态机转换正确
- **导航健壮**：刷新/浏览器回退/复制链接重开，状态不丢、不报错
- **不做**：边界值穷举、XSS 注入专项、a11y、响应式断点、性能

**前置**：L1 全部 + 了解业务闭环
**产出**：5–10 条 bug（多数 S2–S3）
**典型场景**：迭代结束前主力测试、上线前验收
**默认档**：用户不指定时走这档

### L3 精细（30–45 分钟）

**追加的问题**：字段/输入/尺寸的细节对不对？

检查清单（在 L2 基础上 +）：
- 每个输入框跑**等价类 + 边界值**：空、超长、前后空格、特殊字符、emoji、极大/极小数值
- 表格/列表：排序、筛选、分页、空态、大数据量、加载态
- **响应式**按所选平台做断点视觉扫描（见第 3 节）
- 交互细节：键盘全走、Tab 顺序、焦点、loading、骨架屏
- **不做**：XSS / SQL 注入专项、a11y 深度、性能压测、源码审查

**前置**：L2 全部 + PRD/业务规则（不然边界值无从定义）
**产出**：10–20 条 bug（多数 S3–S4）
**典型场景**：重要模块加固、用户投诉集中的版本

### L4 全面（60+ 分钟）

**追加的问题**：非功能维度全部过关吗？

检查清单（在 L3 基础上 +）：
- **安全黑盒**：XSS 反射/存储、SQL 注入特征字、越权（改 URL id）、cookie HttpOnly/Secure/SameSite、localStorage 敏感数据
- **可访问性深度**：`<label>`、`alt`、键盘全走、焦点陷阱、对比度
- **网络专项**：慢网、离线、请求并发、CORS、混合内容
- **代码审查**（有源码时）：空值解引用、useEffect 依赖、事件泄漏、`dangerouslySetInnerHTML`、正则灾难性回溯（见 Checklist 第 4.7 节）
- **轻量性能**：LCP / INP / 明显长任务

**前置**：L3 全部 + **安全测试授权** + （可选）源码
**产出**：15–30+ 条 bug
**典型场景**：重大版本发布、安全合规审查、年度质量盘点

### 档位选择决策辅助

- 不知道选哪档 → **L2**
- 只想知道"是不是坏的" → **L0**
- 冒烟通过想快速跑一遍业务 → **L1**
- 迭代末尾常规验收 → **L2**
- 专项加固、PRD 在手 → **L3**
- 重大版本 + 安全授权 → **L4**

---

## 3. 平台选择（PC / 移动端）

询问 Q1 后，也**必须追问平台**。不同平台的 viewport、交互、检查项都不一样。

### 3.1 PC（Desktop，默认）

- viewport：`1280 × 800`（基准）、`1920 × 1080`（大屏）
- 输入设备：鼠标 + 键盘
- 必做：键盘 Tab 导航、hover 态、右键菜单（如有）
- 响应式断点（L3+）：`1280`、`1920`

### 3.2 移动端（Mobile）

- viewport：`375 × 667`（iPhone SE 基线）、`390 × 844`（iPhone 14）
- UA：设置为 `Mozilla/5.0 (iPhone; ...)` 或 Android UA
- 输入设备：touch（`tap` 而非 `click`）、无 hover
- 必做：touch 手势、软键盘弹起后的布局、横竖屏切换（如网页支持）
- 响应式断点（L3+）：`375`、`414`、`768`（平板边界）

### 3.3 两者都测

- 每个用例在 PC + Mobile 各跑一遍
- Bug 条目 `tags` 加 `desktop` 或 `mobile` 区分
- 注意：**不要把 PC 发现的 bug 在 Mobile 再报一遍**，同根 bug 只报一条，备注"两平台均复现"

### 3.4 平台识别提示

如果用户给了 URL 没说平台，先看一眼再问：
- URL 含 `/m/`、`/mobile/`、`/wap/` → 很可能是移动端专属
- 源码用 `rem` / `vw` / 大量 `@media (max-width: 768px)` → 多半是移动端
- 有 UniApp/Taro/小程序字样 → 移动端
- 否则默认 PC，追问确认

### 3.5 探索时 viewport 的切换规则

- L0 / L1 / L2：**只用所选平台的基线 viewport**（PC=1280, Mobile=375）
- L3 起：在基线基础上**追加响应式断点扫描**
- 两者都测时：每档都跑两遍，分别生成 `bugs-pc.yaml` / `bugs-mobile.yaml`，最后合并成一张 Excel

---

## 4. 场景 A：只给 URL

### 2.1 首选：真实浏览器交互（Playwright / webapp-testing）

**优先调用 `document-skills:webapp-testing`**（或项目内已配置的 Playwright MCP），按下面的探索脚本走：

1. **Open + 首屏诊断**
   - 打开 URL，等待 `networkidle`
   - 截首屏截图
   - 抓 `console.log` / `console.error` / `console.warn`
   - 抓 Network：是否有 4xx / 5xx / CORS 失败 / 混合内容
   - 检查 `<title>` / `meta` / 是否有 JS 未加载

2. **结构扫描**
   - 列出所有可见交互元素：`button`, `a[href]`, `input`, `form`, `select`, `[role=button]`
   - 列出所有 `<img>` 检查 `naturalWidth === 0`（坏图）
   - 列出所有外链 `href` 做 HEAD 请求看 404
   - 可访问性粗检：`<img>` 是否有 `alt`、表单控件是否有 `<label>`、按钮是否有可访问名

3. **交互探索（按优先级）**
   - **表单类**：每个输入框塞空值/超长/特殊字符/脚本片段/emoji；观察校验是否触发、是否报错、是否泄漏堆栈
   - **按钮类**：全部点一遍；连点 5 次观察重复提交/节流；观察 loading 是否消失
   - **路由类**：侧栏/导航菜单每项点开，观察白屏/404/权限报错
   - **参数污染**：在 URL 追加 `?id=-1`、`?id=9999999999`、`?id=<script>`、把 query 删掉，看页面是否炸
   - **刷新/回退**：F5 刷新、浏览器回退、复制链接在新标签页打开，看状态是否丢失或报错
   - **断网/慢网**：DevTools 切 offline / slow 3G，重复关键操作，看有没有体面的错误处理
   - **窗口尺寸**：375×667 / 768×1024 / 1920×1080 各截一张，看响应式是否塌
   - **快速导航**：连续切换 tab、在请求返回前离开页面，看有没有"setState on unmounted"类警告

4. **状态与存储**
   - 看 `localStorage` / `sessionStorage` / `cookie` 里是否明文存了敏感数据
   - 清空后刷新，看是否优雅地把用户引导回登录
   - 手动改 `localStorage` 里的 token / user 字段，看前端是否盲信

5. **每发现一个可疑点**
   - 立即截图保存到 `discuss/bugs/assets/`
   - 保存 console 片段、network 请求（HAR 或关键行）
   - 记录最小复现路径
   - 按第 6 节的结构追加进 bug 清单

### 2.2 降级：静态抓页分析（WebFetch）

**仅当**浏览器环境不可用（MCP 未配置、CI 环境、用户明说不开浏览器）时使用：

- `WebFetch` 拉 HTML，让模型定位：
  - 未闭合/错嵌套标签、缺失 `lang`、重复 `id`
  - 直接暴露的 API 路径（`fetch(...)` / `axios(...)` / `<form action>`）
  - 未混淆的业务注释、埋点 key、feature flag 名
  - 明文配置项、内网地址、测试邮箱
  - 大量内联 script 里的可疑正则（`.*` 式过宽校验、无 `g` flag 的 `replace`）
- 静态分析**只能发现表层问题**。务必在 bug 清单的每一条上标注 `evidence: 静态分析（未经运行验证）`，让读者知道置信度。

### 2.3 什么都抓不到时

如果 URL 需要登录、被防火墙挡住、是内网地址：
- **立刻停**，告诉用户"这个地址我打不开，要么给测试账号，要么给我静态 HTML，要么切到源码探索模式"。
- 不要假装打开了、编造截图或 bug。

---

## 5. 场景 B：只给前端源码

按用户选的"先审查再出用例"混合路线走，**两步出产物**：

### Step 1：代码审查式找 bug（出"已确认"清单）

针对每个组件/路由/工具文件，按下面的嗅探清单扫一遍（参考第 4 节）。每个命中的点按第 6 节结构写进 bug 清单，`evidence` 字段贴代码行号。

### Step 2：业务推断 + 出用例（出"待验证"清单）

从组件 props / 路由定义 / API 调用 / 文案反推业务语义，产出一批"**如果真跑起来会踩这些坑**"的用例：

- 用等价类/边界值/状态迁移方法（见 `test-design.md`）
- 每条用例的 `title` 要写成"**验证**..."而不是"**bug**..."
- 在 bug 清单里标 `status: 待验证`，和已确认 bug 分开

### Step 3：统一汇总

两批合并到同一张 Excel，用 `status` 列区分 `已确认` / `待验证`。

---

## 6. Bug 挖掘 Checklist（通用）

下面这张表是**每次探索都要过一遍**的快检清单。每条命中即可生成一条 bug 候选。**在 L0/L1 档不触发 4.4/4.5/4.6；L2 只触发 4.3/4.4 的异常路径；L3 触发 4.1/4.2 的穷举；L4 触发 4.5/4.6/4.7 全部。**

### 6.1 UI / 渲染

| 编号 | 要点 | 如何触发 |
|------|------|---------|
| UI-01 | 空数据态缺失 | 把接口返回改为空数组/null |
| UI-02 | 长文本溢出、截断无 `title` | 填 500 字标题 |
| UI-03 | 图片失败无占位 | 替换 `src` 为无效 URL |
| UI-04 | 响应式塌陷 | 窗口拖到 375px |
| UI-05 | Loading 卡死 | 接口延迟到 30s / 返回 500 |
| UI-06 | 重复渲染闪烁 | 快速切换筛选条件 |
| UI-07 | 深色模式/主题丢色 | 切换主题 |
| UI-08 | i18n 缺 key（`__key__` 裸露） | 切语言 |

### 6.2 表单 / 输入

| 编号 | 要点 | 如何触发 |
|------|------|---------|
| FORM-01 | 空值未拦截 | 直接点提交 |
| FORM-02 | 前后空格未 trim | 输入 `  abc  ` |
| FORM-03 | 超长未限制 | 粘贴 10000 字符 |
| FORM-04 | XSS 反射 | 输入 `<script>alert(1)</script>` / `<img onerror=...>` |
| FORM-05 | SQL/命令注入关键字 | 输入 `' OR 1=1 --` / `; rm -rf /` |
| FORM-06 | Emoji / 多字节字符 | 输入 `🚀𝒜` |
| FORM-07 | 邮箱/手机号正则过松或过紧 | `a@b`、`+86 13800138000`、`13800138000 ` |
| FORM-08 | 重复提交 | 连点提交按钮 5 次 |
| FORM-09 | 校验时机错误 | 只有 blur 才校验，submit 时漏 |
| FORM-10 | Autofocus、Tab 顺序错乱 | 用键盘 Tab 走一遍 |

### 6.3 交互 / 状态

| 编号 | 要点 | 如何触发 |
|------|------|---------|
| STATE-01 | 返回/前进后状态丢失 | 浏览器回退 |
| STATE-02 | 刷新后未保留筛选/分页 | F5 |
| STATE-03 | 切换 Tab 前的未保存数据未提示 | 有草稿时导航走 |
| STATE-04 | 离开页面时请求未取消 | 切页面看 Network |
| STATE-05 | 幂等接口重复调用 | 连点/快速切换 |
| STATE-06 | 竞态（慢请求被快请求覆盖） | 快速切换筛选 |
| STATE-07 | localStorage 污染 | 手改 storage 刷新 |

### 6.4 网络 / 错误处理

| 编号 | 要点 | 如何触发 |
|------|------|---------|
| NET-01 | 4xx/5xx 无用户可见提示 | mock 返回 500 |
| NET-02 | 超时无提示、无重试 | 断网 |
| NET-03 | 401 不跳登录 | 清 token |
| NET-04 | 403 / 404 页面硬编码 | 改 URL |
| NET-05 | CORS / 混合内容 | 看 Console |
| NET-06 | 请求里带了敏感信息到第三方 | 看 Network 面板 |
| NET-07 | 并发同一资源 N 次 | 看瀑布图 |

### 6.5 可访问性（a11y）

| 编号 | 要点 | 如何触发 |
|------|------|---------|
| A11Y-01 | `<img>` 无 `alt` | 扫 DOM |
| A11Y-02 | 表单控件无 `<label>` / `aria-label` | 扫 DOM |
| A11Y-03 | 按钮用 `<div onClick>` | 扫 DOM |
| A11Y-04 | 颜色对比度 < 4.5 | 取色 + 计算 |
| A11Y-05 | 不能键盘操作 | 拔鼠标走一遍 |
| A11Y-06 | 焦点丢失 / 陷阱 | 打开弹窗看 Tab 能否出来 |

### 6.6 安全（黑盒层面）

| 编号 | 要点 | 如何触发 |
|------|------|---------|
| SEC-01 | token 存在 localStorage（XSS 可偷） | 看存储 |
| SEC-02 | cookie 无 `HttpOnly` / `Secure` / `SameSite` | 看 DevTools Application |
| SEC-03 | 前端校验后端不校验 | 绕过前端直接打接口 |
| SEC-04 | 越权：改 URL 里的 id 能看别人数据 | 改 `/user/1` → `/user/2` |
| SEC-05 | 暴露的 sourcemap / `.git` / `.env` | 访问 `/.git/config` |
| SEC-06 | 源码里硬编码 key / secret | grep 搜 `sk-`、`AKIA`、`password` |

### 6.7 代码审查专属（只在场景 B 用）

| 编号 | 要点 | 如何识别 |
|------|------|---------|
| CODE-01 | 可能的空值解引用 | `obj.foo.bar` 而 `obj` 没保证 |
| CODE-02 | `useEffect` 依赖数组漏项 | 闭包引用了未列入依赖的变量 |
| CODE-03 | 组件 unmount 后 setState | 异步 + 没 abort |
| CODE-04 | 数字/金额用浮点相加 | `0.1 + 0.2` 精度 |
| CODE-05 | 时间未带时区 | `new Date(str)` 无时区 |
| CODE-06 | key 用 index | 列表 `map((item, i) => <Row key={i}/>)` |
| CODE-07 | 事件监听器未解绑 | addEventListener 无 remove |
| CODE-08 | 轮询无清理 | setInterval 无 clearInterval |
| CODE-09 | 危险 HTML | `dangerouslySetInnerHTML` / `v-html` 接未转义变量 |
| CODE-10 | 过宽正则 / 灾难性回溯 | `.*.*` 重叠量词 |
| CODE-11 | 异步错误未捕获 | `fetch().then()` 无 `.catch` |
| CODE-12 | 硬编码的 URL / 账号 / token | grep 搜 |

---

## 7. 证据收集规则

**每一条 bug 清单条目，必须至少有一种证据**，否则它只是"猜测"，应标成 `status: 待验证`。

| 场景 | 证据形式 | 存放 |
|------|---------|------|
| 浏览器探索 | 截图、console 片段、HAR/请求片段 | `discuss/bugs/assets/<bug-id>/` |
| 静态抓页 | HTML/JS 片段、行号 | bug 条目的 `evidence` 字段 |
| 代码审查 | 文件路径 + 行号 + 代码片段 | bug 条目的 `evidence` 字段 |

证据字段格式示例：

```yaml
evidence:
  - type: screenshot
    path: discuss/bugs/assets/BUG-007/search-overflow.png
  - type: console
    content: "Warning: Each child in a list should have a unique 'key' prop."
  - type: code
    path: src/components/UserList.tsx:42
    snippet: "users.map((u, i) => <Row key={i} user={u} />)"
```

---

## 8. Bug 清单数据结构

用下面的结构存；后续用 `scripts/bugs_to_xlsx.py` 转 Excel。每条 bug 必须带 `level`（发现它的档位）和 `platform`（`pc` / `mobile`）两个字段。

```yaml
project: <被测对象名，URL 或仓库名>
target: <URL 或源码路径>
mode: explore-url    # explore-url | explore-code | mixed
level: L2            # L0 | L1 | L2 | L3 | L4
platform: pc         # pc | mobile | both
explorer: claude-qa
scanned_at: 2026-04-21

bugs:
  - id: BUG-001
    title: 商品标题超长时列表塌陷遮挡价格
    category: UI-02
    module: 商品列表
    level: L3              # 这条 bug 是在哪档发现的
    platform: mobile       # pc | mobile | both
    severity: S3          # S1|S2|S3|S4
    priority: P2          # P0|P1|P2|P3
    status: 已确认        # 已确认 | 待验证
    reproducible: 必现    # 必现 | 偶现 | 一次
    steps:
      - 打开首页
      - 找到任意标题超 30 字的商品
      - 缩窗到 375px
    expected: 标题溢出省略，价格完整可见
    actual: 标题占满两行，价格被截掉
    evidence:
      - type: screenshot
        path: discuss/bugs/assets/BUG-001/overflow.png
    suggestion: 标题加 `line-clamp: 2` 或 `text-ellipsis`，价格固定宽度
    tags: [mobile, list]
```

必填：`id`, `title`, `level`, `platform`, `severity`, `priority`, `status`, `steps`, `expected`, `actual`
可选：`category`, `module`, `reproducible`, `evidence`, `suggestion`, `tags`

---

## 9. 产出 Excel 汇总表

调用 `scripts/bugs_to_xlsx.py`：

```bash
python scripts/bugs_to_xlsx.py discuss/bugs/bugs.yaml -o discuss/bugs/bug-report.xlsx
```

产出列：ID、标题、分类、模块、严重度、优先级、状态、必现/偶现、复现步骤、期望、实际、证据、建议、标签。

- 严重度/优先级/状态列带下拉验证
- S1/P0 高亮红色
- 首行冻结 + 自动筛选

---

## 9.1 同步产出测试用例清单（必做）

主动探索测试**不是只出 bug，还必须同时产出测试用例清单**。用户没有明确说"不要用例"，就都要做。

### 转换规则

把探索过程中**已经走过的每个检查点**固化成一条用例，不管有没有发现 bug：

- 发现 bug 的点 → 用例 `expected` 写"**正确的**预期行为"（不是 bug 当前的表现），`priority` 按对应 bug 的优先级
- 没发现 bug 的点 → 照样写一条 Pass 状态的用例，沉淀为**回归资产**
- 一次探索扫到的 Bug Checklist（第 6 节）命中条目，逐条变成用例
- 同一功能点 PC/Mobile 各跑了一遍 → 合成一条用例，`precondition` 里写"PC / Mobile 各验一次"

### 用例数据结构

```yaml
cases:
  - id: TC-001
    title: 商品标题超长时列表布局保持完整
    module: 商品列表
    priority: P2
    level: L3                # 对应发现档位
    platform: mobile
    precondition:
      - 已登录测试账号
      - 至少存在一个标题 > 30 字的商品
    steps:
      - 打开首页
      - 滚动到标题超长的商品
      - 窗口缩至 375px
    expected:
      - 标题最多占两行并溢出省略
      - 价格完整可见不被遮挡
    linked_bug: BUG-001      # 若该用例来源于某 bug，关联上
```

### 产出路径

- YAML 源：`discuss/testing/test-cases.yaml`
- Excel：`python scripts/cases_to_xlsx.py discuss/testing/test-cases.yaml -o discuss/testing/test-cases.xlsx`
- XMind（可选）：`python scripts/cases_to_xmind.py discuss/testing/test-cases.yaml -o discuss/testing/test-cases.xmind`

最终交付两张表：`bug-report.xlsx`（发现的问题） + `test-cases.xlsx`（可复用的回归用例）。

---

## 10. 与 bug-report.md 的关系

- **本文件**：**批量探索**时的发现流程和**汇总清单**格式
- **bug-report.md**：**单个 bug** 进入正式流程（提 Jira/禅道）时的**详细报告模板**

工作流衔接：
1. 先用本流程扫出 bug 清单（Excel 汇总）
2. 用户确认后，对每条 S1/S2/P0/P1 的 bug，再用 `new_bug_report.py` 生成详细报告

---

## 11. 不做的事

- **不扫代码规范 / 命名规范**：不评价代码风格、变量命名、接口路径命名（RESTful / camelCase vs snake_case / URL 复数等）、字段命名、注释完整度、文件组织。**只关心功能是否跑通、是否符合预期、是否会炸**。命名不规范但功能正确的，直接跳过
- **不做有风险的操作**：不点"删除账号"、"注销"、"支付"类不可逆按钮，除非用户明说测试环境可以
- **不做 DoS / 暴力探测**：不打压测、不扫 admin 路径、不跑字典爆破
- **不绕过授权**：只测试自己有权限看的页面；未授权接口发现越权也只报告不深挖
- **不编造 bug**：打不开就说打不开，看不懂代码就问用户；宁可少报不要误报
- **不越俎代庖**：找到疑似 bug 不要直接去改代码，除非用户明确要修
