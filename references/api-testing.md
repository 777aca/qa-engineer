# API 接口测试（后端栈无关）

## 目录

- [1. 接口测试关心什么](#1-接口测试关心什么)
- [2. 测试点清单](#2-测试点清单)
- [3. 工具选型](#3-工具选型)
- [4. pytest + requests 推荐骨架](#4-pytest--requests-推荐骨架)
- [5. Postman / Newman 团队协作模式](#5-postman--newman-团队协作模式)
- [6. 断言要点](#6-断言要点)
- [7. 契约与 Schema 校验](#7-契约与-schema-校验)
- [8. Mock 与依赖隔离](#8-mock-与依赖隔离)
- [9. 安全性快速检查](#9-安全性快速检查)

---

## 1. 接口测试关心什么

API 接口测试与后端技术栈（PHP / Java / Go / Python / Node）**无关**——你测的是 HTTP/JSON 契约。核心关注点：

1. **正确性**：输入→输出是否符合文档
2. **边界**：长度、范围、空值、特殊字符
3. **错误处理**：异常时返回什么状态码 + 业务码 + 提示
4. **幂等性**：相同请求多次执行结果一致（尤其 PUT/DELETE）
5. **鉴权**：无 token、过期 token、越权访问
6. **性能**：响应时间分位（P50/P95/P99）
7. **契约稳定**：字段是否按文档，新增字段是否向后兼容

## 2. 测试点清单

对每个接口按以下清单过一遍：

### 功能正确性
- [ ] Happy Path：典型合法输入，返回 2xx + 数据结构正确
- [ ] 必填字段缺失 → 400
- [ ] 非法类型（字符串传给数字字段） → 400
- [ ] 字段长度超限 → 400
- [ ] 字段值越界 → 400 / 业务码
- [ ] 枚举值非法 → 400

### 鉴权与权限
- [ ] 无 Authorization → 401
- [ ] 过期 token → 401
- [ ] 错误签名 → 401
- [ ] 用户 A 的 token 访问用户 B 的资源 → 403
- [ ] 未登录用户访问需要登录的接口 → 401

### 数据副作用
- [ ] 创建接口：数据库里确实写入了
- [ ] 更新接口：字段确实被修改
- [ ] 删除接口：数据被标记删除或真删
- [ ] 不该变的字段没被改（防脏写）
- [ ] 相关的缓存 / 索引 / 消息队列被更新

### 幂等与并发
- [ ] 同一请求重试 3 次，结果一致
- [ ] 同时提交 2 次创建请求（如订单），只应生成 1 条
- [ ] 悲观锁 / 乐观锁是否生效

### 错误路径
- [ ] 依赖服务超时 → 返回合理错误码，不 500
- [ ] 数据库故障 → 合理错误码
- [ ] 超大请求体 → 413
- [ ] 请求频率过高 → 429（若有限流）

## 3. 工具选型

| 工具 | 场景 | 优缺点 |
|-----|------|-------|
| `curl` | 快速手测、文档示例 | 通用，但断言需手工 |
| Postman / Apifox | 交互式 + 团队协作 + 文档 | GUI 友好，Newman 可跑 CI |
| `pytest + requests` | 自动化、深度断言、CI | 推荐首选，灵活强大 |
| `httpx` | 支持 async | 替代 requests，适合高并发 |
| HTTPie | CLI 美化 | 手测很舒服 |
| [schemathesis](https://github.com/schemathesis/schemathesis) | 基于 OpenAPI 自动生成用例 | 契约测试神器 |

## 4. pytest + requests 推荐骨架

```python
# tests/api/conftest.py
import os
import pytest
import requests

BASE_URL = os.environ.get("API_BASE_URL", "https://staging.example.com/api")


@pytest.fixture(scope="session")
def auth_token() -> str:
    """登录一次，后续所有用例复用 token，避免每条用例都走登录流程。"""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "test@example.com", "password": "test123"},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()["data"]["token"]


@pytest.fixture
def api(auth_token: str) -> requests.Session:
    """带鉴权的 Session。用例写起来像 api.get(...) / api.post(...)。"""
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}"})
    s.base_url = BASE_URL  # type: ignore[attr-defined]
    return s
```

```python
# tests/api/test_user_profile.py
import pytest


class TestUserProfile:
    """GET /user/profile — 获取当前用户资料"""

    def test_应当_在_已登录时_返回_用户资料(self, api):
        r = api.get(f"{api.base_url}/user/profile")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        data = body["data"]
        # 字段契约
        assert set(data.keys()) >= {"id", "email", "nickname", "createdAt"}
        assert isinstance(data["id"], int)
        assert "@" in data["email"]

    def test_应当_在_无_token时_返回_401(self):
        import requests
        r = requests.get(f"{BASE_URL}/user/profile", timeout=5)
        assert r.status_code == 401

    @pytest.mark.parametrize("token", ["", "invalid", "Bearer expired.xxx.yyy"])
    def test_应当_在_token非法时_返回_401(self, token):
        import requests
        r = requests.get(
            f"{BASE_URL}/user/profile",
            headers={"Authorization": token},
            timeout=5,
        )
        assert r.status_code == 401
```

**执行（遵循用户 CLAUDE.md 规则，必须通过 scripts/ 下的 .js 脚本启停）**：

```js
// scripts/test-api.js
import { execSync } from "node:child_process";
execSync("pytest tests/api -v --tb=short", {
  stdio: "inherit",
  env: { ...process.env, API_BASE_URL: "https://staging.example.com/api" },
});
```

## 5. Postman / Newman 团队协作模式

团队协作 + 非开发人员参与时，Postman 更友好：

- **Collection**：一组相关接口
- **Environment**：区分 dev / staging / prod
- **Pre-request Script**：自动登录、生成签名
- **Tests 脚本**：JS 编写断言
- **Newman**：CI 中运行 Postman Collection

```js
// Postman → Tests 脚本示例
pm.test("状态码 200", () => pm.response.to.have.status(200));
pm.test("业务码为 0", () => {
  const body = pm.response.json();
  pm.expect(body.code).to.eql(0);
});
pm.test("响应时间 < 500ms", () => pm.expect(pm.response.responseTime).to.be.below(500));
```

CI 运行：`newman run collection.json -e staging.json --reporters cli,html`

## 6. 断言要点

### 三层断言
每条用例至少覆盖三层：

1. **协议层**：HTTP 状态码
2. **业务层**：业务 code / message
3. **数据层**：具体字段值、类型、结构

❌ 反例（只断状态码）：
```python
assert r.status_code == 200  # 后端返回 {"code": -1, "msg": "失败"} 也能过
```

✅ 正例：
```python
assert r.status_code == 200
body = r.json()
assert body["code"] == 0, f"业务码异常：{body}"
assert body["data"]["orderId"], "订单号不应为空"
```

### 断言尽量宽松匹配，避免脆弱
- 时间戳：只断类型、在合理区间，不断具体值
- ID：只断非空 + 类型，不断具体数字
- 列表：断包含关系，不断完全相等
- 顺序敏感字段才断顺序

## 7. 契约与 Schema 校验

若项目有 OpenAPI / Swagger 文档，可自动生成 Schema 并断言：

```python
import jsonschema

USER_SCHEMA = {
    "type": "object",
    "required": ["id", "email", "nickname"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "email": {"type": "string", "format": "email"},
        "nickname": {"type": "string", "maxLength": 50},
        "createdAt": {"type": "string", "format": "date-time"},
    },
}


def test_user_profile_schema(api):
    r = api.get(f"{api.base_url}/user/profile")
    jsonschema.validate(instance=r.json()["data"], schema=USER_SCHEMA)
```

## 8. Mock 与依赖隔离

当依赖第三方服务（支付、短信、风控）时：
- **本地 mock**：`responses` / `httpretty`（Python）
- **进程级 mock**：[WireMock](https://wiremock.org/) / [MockServer](https://www.mock-server.com/)
- **环境级**：测试环境对接沙箱（如支付宝沙箱）

**原则**：单元/接口测试隔离外部依赖；集成/E2E 保留真实依赖但用沙箱。

## 9. 安全性快速检查

每个接口至少做：
- [ ] SQL 注入：参数传 `' OR 1=1--`
- [ ] XSS：参数传 `<script>alert(1)</script>`，看回显
- [ ] 越权：A 用户 token 访问 B 用户资源 (`/orders/{B的id}`)
- [ ] IDOR：id 改成其他值能否访问
- [ ] 敏感字段泄漏：密码、token、身份证是否出现在响应里
- [ ] HTTPS：是否强制 HTTPS，HTTP 是否 301
- [ ] CORS：`Access-Control-Allow-Origin` 是否过宽（`*` 对敏感接口是风险）
