# UI E2E 自动化（以 Playwright 为首选）

## 目录

- [1. 为什么首选 Playwright](#1-为什么首选-playwright)
- [2. 选择器策略](#2-选择器策略)
- [3. 等待策略（禁止硬等待）](#3-等待策略禁止硬等待)
- [4. Page Object 模式](#4-page-object-模式)
- [5. 认证复用](#5-认证复用)
- [6. 测试数据准备](#6-测试数据准备)
- [7. 反脆弱模式](#7-反脆弱模式)
- [8. 调试手段](#8-调试手段)
- [9. CI 集成](#9-ci-集成)
- [10. Selenium / Cypress 的差异](#10-selenium--cypress-的差异)

---

## 1. 为什么首选 Playwright

- **前端技术栈无关**：Vue / React / Next / Nuxt / UniApp H5 都能测
- **自动等待**：大部分操作自带"等到可交互"语义
- **多浏览器**：Chromium / Firefox / WebKit 同一 API
- **Trace + Video + Screenshot**：失败自带完整上下文
- **并行 + 分片**：原生支持并行执行
- **TS 友好**：类型完整

仓库结构建议：
```
e2e/
├── fixtures/          # 自定义 fixture
├── pages/             # Page Object
├── specs/             # 用例文件
│   ├── auth/
│   ├── order/
│   └── ...
├── utils/             # 工具函数
├── data/              # 静态测试数据
└── playwright.config.ts
```

## 2. 选择器策略

**选择器稳定性顺序（从稳定到脆弱）**：

1. `data-testid`（与 UI 文案/结构解耦，首选）
2. `getByRole` + 可访问名（语义化，同时利好可访问性）
3. `getByLabel` / `getByPlaceholder` / `getByText`（业务语义）
4. CSS class（不稳定，Tailwind 项目尤其差）
5. XPath 全路径（最脆弱，禁止）

```ts
// ✅ 推荐
await page.getByTestId("login-submit").click();
await page.getByRole("button", { name: "登录" }).click();
await page.getByLabel("邮箱").fill("test@example.com");

// ❌ 避免
await page.locator(".ant-btn.ant-btn-primary").nth(2).click();
await page.locator("xpath=/html/body/div[3]/div/form/button").click();
```

**对开发侧的建议**：关键控件必加 `data-testid`。这需要开发协作，但比后期维护选择器成本低得多。

## 3. 等待策略（禁止硬等待）

绝对禁止 `await page.waitForTimeout(3000)` 式硬等待。一律显式等待：

```ts
// 等元素可见
await expect(page.getByTestId("order-list")).toBeVisible();

// 等元素消失（如 loading）
await expect(page.getByTestId("loading")).toBeHidden();

// 等 URL 变化
await page.waitForURL(/\/orders\/\d+/);

// 等具体网络请求
const [response] = await Promise.all([
  page.waitForResponse(r => r.url().includes("/api/orders") && r.status() === 200),
  page.getByTestId("submit-order").click(),
]);

// 等文本出现
await expect(page.getByText("下单成功")).toBeVisible();

// 自定义条件
await page.waitForFunction(() => window.__APP_READY__ === true);
```

**Playwright 的 `expect` 自带轮询重试**（默认 5 秒），比 Selenium 的 `WebDriverWait` 更简洁。

## 4. Page Object 模式

把页面结构封装成类，用例只关心业务动作：

```ts
// e2e/pages/login.page.ts
import { Page, Locator, expect } from "@playwright/test";

export class LoginPage {
  readonly page: Page;
  readonly email: Locator;
  readonly password: Locator;
  readonly submit: Locator;
  readonly errorBanner: Locator;

  constructor(page: Page) {
    this.page = page;
    this.email = page.getByLabel("邮箱");
    this.password = page.getByLabel("密码");
    this.submit = page.getByTestId("login-submit");
    this.errorBanner = page.getByTestId("login-error");
  }

  async goto() {
    await this.page.goto("/login");
  }

  async login(email: string, password: string) {
    await this.email.fill(email);
    await this.password.fill(password);
    await this.submit.click();
  }

  async expectLoggedIn() {
    await expect(this.page).toHaveURL(/\/dashboard/);
  }

  async expectError(message: string | RegExp) {
    await expect(this.errorBanner).toContainText(message);
  }
}
```

```ts
// e2e/specs/auth/login.spec.ts
import { test } from "@playwright/test";
import { LoginPage } from "../../pages/login.page";

test.describe("登录流程", () => {
  test("应当_在_正确凭证下_跳转到_Dashboard", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.login("test@example.com", "test123");
    await login.expectLoggedIn();
  });

  test("应当_在_密码错误时_显示_错误提示", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.login("test@example.com", "wrong");
    await login.expectError(/密码错误/);
  });
});
```

## 5. 认证复用

每条用例都登录一次太慢。用 `storageState` 复用登录态：

```ts
// e2e/global-setup.ts
import { chromium, FullConfig } from "@playwright/test";

export default async (_config: FullConfig) => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`${process.env.BASE_URL}/login`);
  await page.getByLabel("邮箱").fill(process.env.TEST_EMAIL!);
  await page.getByLabel("密码").fill(process.env.TEST_PASSWORD!);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(/\/dashboard/);
  await context.storageState({ path: "e2e/.auth/user.json" });
  await browser.close();
};
```

```ts
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: process.env.BASE_URL ?? "https://staging.example.com",
    storageState: "e2e/.auth/user.json",
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
});
```

## 6. 测试数据准备

**核心原则：UI 只测 UI，数据构造走 API。**

反例（慢且脆弱）：
```ts
// ❌ 通过 UI 创建 10 个订单作为测试数据
for (let i = 0; i < 10; i++) {
  await page.goto("/new-order");
  // ... 一堆点击
}
```

正例：
```ts
// ✅ 通过 API 批量造数据，再进 UI 只验证列表展示
import { apiCreateOrders } from "../utils/api";

test.beforeEach(async () => {
  await apiCreateOrders({ count: 10, userId: "test-user" });
});
```

**数据隔离**：
- 每条用例使用独立账号 / 独立命名空间
- 或用例末尾清理自己创建的数据
- 跑 CI 时用独立测试环境或独立租户

## 7. 反脆弱模式

E2E 最大的痛点是 flaky（偶发失败）。关键做法：

1. **合理的超时**：`actionTimeout: 10000`, `expect.timeout: 5000`
2. **重试机制**：CI 配 `retries: 2`，但禁止盲目无脑重试
3. **隔离副作用**：每个 worker 独立测试账号
4. **显式等网络静默**：`await page.waitForLoadState("networkidle")`
5. **隐藏动画**：测试环境注入 CSS `* { animation: none !important; }`
6. **固定时区 & locale**：`context({ timezoneId: "Asia/Shanghai", locale: "zh-CN" })`
7. **固定时钟（需要时）**：`page.clock.install({ time: new Date("2026-04-21") })`
8. **监听 console error 作为断言**：发现 JS 错误立即失败

```ts
test("页面不应有 console error", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", err => errors.push(err.message));
  page.on("console", msg => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  await page.goto("/");
  expect(errors, `页面出现 JS 错误：\n${errors.join("\n")}`).toEqual([]);
});
```

## 8. 调试手段

- **UI 模式**：`playwright test --ui`（最强大，可时间旅行）
- **Headed 模式**：`playwright test --headed`
- **暂停**：在用例中 `await page.pause()` 打开 Inspector
- **Trace Viewer**：`playwright show-trace trace.zip`（失败必看）
- **Codegen**：`playwright codegen https://example.com`（录制生成代码）
- **VSCode 插件**：官方 Playwright Test for VSCode，支持断点调试

## 9. CI 集成

**执行脚本（遵循用户 CLAUDE.md 规则）**：

```js
// scripts/test-e2e.js
import { execSync } from "node:child_process";

const env = {
  ...process.env,
  BASE_URL: process.env.BASE_URL ?? "https://staging.example.com",
  TEST_EMAIL: process.env.TEST_EMAIL ?? "e2e+ci@example.com",
  TEST_PASSWORD: process.env.TEST_PASSWORD ?? "",
};

execSync("playwright test --reporter=html,list", { stdio: "inherit", env });
```

**CI 建议**：
- 失败自动上传 Trace / Video / Screenshot（GitHub Actions artifact）
- 分片并行：`--shard=1/4` ... `--shard=4/4`
- 报告聚合：使用 `playwright-merge-reports`

## 10. Selenium / Cypress 的差异

| 特性 | Playwright | Cypress | Selenium |
|-----|-----------|---------|---------|
| 多浏览器 | ✅ Chromium/FF/WebKit | ⚠️ 主要 Chromium | ✅ 全部 |
| 多标签页 | ✅ | ❌（历史限制） | ✅ |
| iframe | ✅ | ⚠️ | ✅ |
| 自动等待 | ✅ 原生 | ✅ 原生 | ❌ 需手写 WebDriverWait |
| 并行 | ✅ | ⚠️（需 Dashboard） | ✅ |
| 语言 | TS/JS/Python/Java/.NET | 仅 JS/TS | 全语言 |
| 适用 | 现代 Web 首选 | React/Vue 小项目 | 旧项目 / 企业栈 |

若项目已有 Selenium/Cypress，不要强行迁移。本技能的核心模式（PO / 稳定选择器 / 显式等待 / 数据走 API）在三者通用。
