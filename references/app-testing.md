# 移动 App 测试（Appium 通用 + Flutter 专属）

## 目录

- [1. 决策：选 Appium 还是 flutter_driver/integration_test](#1-决策选-appium-还是-flutter_driverintegration_test)
- [2. Appium 基础](#2-appium-基础)
- [3. Appium 定位策略](#3-appium-定位策略)
- [4. Flutter 专属测试方案](#4-flutter-专属测试方案)
- [5. 多设备 / 云真机](#5-多设备--云真机)
- [6. 常见陷阱](#6-常见陷阱)
- [7. 小程序 / UniApp / H5 混合](#7-小程序--uniapp--h5-混合)

---

## 1. 决策：选 Appium 还是 flutter_driver/integration_test

| 维度 | Appium | Flutter 官方测试 |
|-----|--------|----------------|
| 被测 App 类型 | 原生（Android/iOS）、Flutter、RN、Hybrid、小程序 | 仅 Flutter |
| 元素定位 | 通过 UIAutomator / XCUITest | 通过 Flutter Finder（直接访问 Widget 树） |
| 稳定性 | 中（依赖平台 driver） | 高（App 内自动化） |
| 视角 | 黑盒，纯 UI | 灰盒，可访问 App 内部 |
| 适合角色 | 测试工程师 | 开发 + 测试 |
| CI 成本 | 中高（需模拟器/真机） | 低（可跑 host mode） |

**建议**：
- **Flutter App** → 集成测试用 `integration_test`（开发协作）+ 少量 Appium 做冒烟
- **原生 / RN / 混合** → Appium
- **跨端一致性测试** → Appium

## 2. Appium 基础

### 架构
```
测试脚本 (Python/JS/Java)
      ↓ WebDriver 协议
Appium Server (localhost:4723)
      ↓
UIAutomator2 (Android)  /  XCUITest (iOS)
      ↓
被测设备
```

### 目录建议
```
app-e2e/
├── capabilities/       # 各平台各设备的 capabilities
├── pages/              # 页面对象（Android/iOS 分开或合并）
├── specs/
├── utils/
└── drivers/
```

### Python 最小骨架

```python
# app-e2e/conftest.py
import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options


@pytest.fixture
def android_driver():
    opts = UiAutomator2Options().load_capabilities({
        "platformName": "Android",
        "deviceName": "emulator-5554",
        "app": "/abs/path/to/app-debug.apk",
        "automationName": "UiAutomator2",
        "noReset": False,
        "autoGrantPermissions": True,
    })
    driver = webdriver.Remote("http://localhost:4723", options=opts)
    driver.implicitly_wait(0)  # 关闭隐式等待，统一用显式等待
    yield driver
    driver.quit()
```

```python
# app-e2e/specs/test_login.py
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_应当_在_正确凭证下_登录成功(android_driver):
    wait = WebDriverWait(android_driver, 10)
    wait.until(EC.presence_of_element_located(
        (AppiumBy.ACCESSIBILITY_ID, "emailInput")
    )).send_keys("test@example.com")
    android_driver.find_element(AppiumBy.ACCESSIBILITY_ID, "passwordInput").send_keys("test123")
    android_driver.find_element(AppiumBy.ACCESSIBILITY_ID, "loginBtn").click()
    wait.until(EC.presence_of_element_located(
        (AppiumBy.ACCESSIBILITY_ID, "homeTitle")
    ))
```

**启动脚本**：

```js
// scripts/test-app.js
import { execSync, spawn } from "node:child_process";

// 启动 Appium Server 为后台进程
const appium = spawn("appium", ["--log-level", "info", "--log", "logs/appium.log"], {
  detached: true, stdio: "ignore",
});
appium.unref();

try {
  execSync("pytest app-e2e/specs -v", { stdio: "inherit" });
} finally {
  process.kill(-appium.pid);
}
```

## 3. Appium 定位策略

稳定性排序（与 Web 略不同）：

1. **accessibilityId**（首选）：Android 为 `content-desc`，iOS 为 `accessibilityIdentifier`。**要求开发协作添加**。
2. **resource-id**（Android）/ **id**（iOS）：相对稳定，改版时易变
3. **text / label**：与文案绑定，多语言切换易碎
4. **xpath**：最脆弱，避免使用

**推动开发添加 accessibilityId**：
- Android：`android:contentDescription="loginBtn"`（或 Compose `Modifier.semantics { contentDescription = "loginBtn" }`）
- iOS：`button.accessibilityIdentifier = "loginBtn"`
- Flutter：`Semantics(identifier: "loginBtn", child: ...)` 或 `Key("loginBtn")`
- React Native：`testID="loginBtn"`

## 4. Flutter 专属测试方案

Flutter 官方推荐 `integration_test` 包，跑在真实设备/模拟器上，直接访问 Widget 树。

```dart
// integration_test/login_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:my_app/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('登录流程', () {
    testWidgets('应当_在_正确凭证下_跳转到_主页', (tester) async {
      app.main();
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('emailInput')), 'test@example.com');
      await tester.enterText(find.byKey(const Key('passwordInput')), 'test123');
      await tester.tap(find.byKey(const Key('loginBtn')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('homeTitle')), findsOneWidget);
    });
  });
}
```

执行：
```js
// scripts/test-flutter-integration.js
import { execSync } from "node:child_process";
execSync("flutter test integration_test/login_test.dart -d emulator-5554", {
  stdio: "inherit",
});
```

### 对比 flutter_driver
`flutter_driver` 已进入维护状态，新项目一律用 `integration_test`。

### Flutter + Appium 共存
若需与原生模块一起测（如扫码、支付 SDK），用 Appium 的 `FlutterDriver` 扩展：
- [appium-flutter-driver](https://github.com/appium/appium-flutter-driver)
- capabilities 加 `"automationName": "Flutter"`

## 5. 多设备 / 云真机

### 本地多设备
并行跑需不同 `systemPort` 和 `udid`：
```python
# capabilities/device_matrix.py
DEVICES = [
  {"deviceName": "Pixel_6", "udid": "emulator-5554", "systemPort": 8200},
  {"deviceName": "Galaxy_S22", "udid": "emulator-5556", "systemPort": 8201},
]
```
用 `pytest-xdist` 并行：`pytest -n 2`

### 云真机平台
- AWS Device Farm
- BrowserStack App Automate
- Sauce Labs
- 国内：腾讯 WeTest、阿里 MQC、Testin

**优点**：覆盖真实机型、无需维护设备
**缺点**：单次收费、网络慢

## 6. 常见陷阱

### 权限弹窗
Android 动态权限在初次启动时弹出：
- 设 `autoGrantPermissions: true`（Appium）
- 或在脚本中主动处理

### 系统弹窗 / OS 更新提示
iOS 可能在测试中弹系统对话框：
- 设 `autoAcceptAlerts: true`

### App 冷启动太慢
- 开启 `noReset: true` 复用已登录状态
- 或用独立 session，首次登录后导出 storage

### 网络环境
- Android 模拟器访问宿主机用 `10.0.2.2`，iOS 用 `localhost`
- 统一用公网 staging 环境最省心

### 动画干扰
- 关闭系统动画：`adb shell settings put global window_animation_scale 0`
- iOS 启动参数 `-UIAnimationDragCoefficient 0`

### 稳定性 Checklist
- 每条用例独立，互不依赖
- 失败自动截图 + 录屏 + 日志
- 关键步骤加重试（网络请求）
- App 崩溃监听（Crash 要作为测试失败）

## 7. 小程序 / UniApp / H5 混合

### 微信小程序
- 官方：小程序自动化 SDK（miniprogram-automator），Node.js 驱动
- 仅限开发者工具环境
- 与 Appium 无关

```js
// 示例（概念性）
import automator from "miniprogram-automator";
const miniProgram = await automator.launch({ projectPath: "./miniprogram-project" });
const page = await miniProgram.currentPage();
const btn = await page.$("#loginBtn");
await btn.tap();
```

### UniApp
- H5 版本 → 直接用 Playwright（前端栈无关）
- App 版本 → Appium（它就是原生壳，Webview 或原生渲染视情况）
- 小程序版本 → 各小程序自动化 SDK

### WebView / 混合 App
Appium 切换 context：
```python
contexts = driver.contexts  # ['NATIVE_APP', 'WEBVIEW_com.example.app']
driver.switch_to.context(contexts[1])
# 现在可用 Selenium CSS/XPath 定位 H5
```

### 建议策略
- **核心业务 on Web H5** → Playwright 覆盖（快）
- **核心业务 on App** → Appium/Flutter 集成测试覆盖（稳）
- 两端都不要漏，但不必用同一套脚本两次覆盖
