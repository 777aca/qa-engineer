# 性能 / 压力测试

## 目录

- [1. 性能测试分类](#1-性能测试分类)
- [2. 关键指标与验收标准](#2-关键指标与验收标准)
- [3. 工具选型](#3-工具选型)
- [4. 场景建模](#4-场景建模)
- [5. Locust 模式](#5-locust-模式)
- [6. k6 模式](#6-k6-模式)
- [7. JMeter 适用场景](#7-jmeter-适用场景)
- [8. 指标解读与瓶颈定位](#8-指标解读与瓶颈定位)
- [9. 性能报告模板](#9-性能报告模板)

---

## 1. 性能测试分类

| 类型 | 目的 | 典型场景 |
|-----|------|---------|
| **负载测试（Load）** | 确认在预期负载下性能达标 | "日常 1000 QPS，响应时间 P95 < 500ms" |
| **压力测试（Stress）** | 找到系统极限 | 持续增压到系统崩溃/限流 |
| **峰值测试（Spike）** | 验证突发流量下的表现 | 秒杀、开抢场景 |
| **容量测试（Capacity）** | 确定系统上限以做扩容规划 | "5000 QPS 时需要几台机器" |
| **耐力测试（Soak）** | 长时间运行找内存泄漏/资源累积 | 跑 8 小时观察内存曲线 |
| **基准测试（Benchmark）** | 版本迭代前后对比，防性能回归 | 每次发版前跑固定场景 |

**先确定类型再选工具**。大多数团队第一步是做"负载测试+基准回归"。

## 2. 关键指标与验收标准

### 前置：必须量化的指标
- **吞吐量**：QPS / TPS / RPS
- **响应时间**：Avg / P50 / P95 / P99 / Max
- **错误率**：HTTP 5xx 比例、业务失败比例
- **并发用户数**：VU（Virtual User）
- **资源消耗**：CPU、内存、带宽、DB 连接、磁盘 IO

### 为什么更看 P95/P99 而非平均
平均值掩盖长尾。100 个请求 99 个 100ms、1 个 10 秒，平均 199ms 看起来没问题，但 1% 用户体验极差。**生产级系统看 P99。**

### 验收标准示例
```
接口 POST /api/orders
- 吞吐量目标：≥ 500 TPS
- 响应时间：P50 < 200ms，P95 < 500ms，P99 < 1s
- 错误率：< 0.1%
- 持续时间：30 分钟稳定运行
```

## 3. 工具选型

| 工具 | 语言 | 优点 | 场景 |
|-----|-----|------|-----|
| **Locust** | Python | 脚本灵活、Web UI、分布式 | 复杂业务流、数据驱动 |
| **k6** | JS | 现代、云原生、CI 友好、报告漂亮 | 基准测试、CI 回归 |
| **JMeter** | Java/GUI | 生态最全、协议最广、GUI 编辑 | 传统企业、多协议测试 |
| **wrk / wrk2** | Lua | 极致轻量、单机高并发 | 快速基准、单接口 |
| **Gatling** | Scala | 报告精美、DSL 优雅 | 深度定制 |
| **Artillery** | JS/YAML | 配置简单 | 快速脚本 |

**推荐组合**：
- Python 团队 → Locust
- JS/TS 团队 → k6
- 协议多样（JDBC、MQ、FTP）→ JMeter

## 4. 场景建模

压测不是"无脑打接口"，要**模拟真实用户行为**：

### Step 1：定义场景
- 用户类型：游客 vs 登录用户 vs VIP
- 行为组合：浏览 60% + 下单 20% + 支付 10% + 其他 10%
- 思考时间：用户操作之间的间隔（通常 1~5 秒）

### Step 2：计算目标并发
典型换算：
```
目标 QPS = 日活 × 每用户请求数 ÷ 有效使用秒数
峰值 QPS ≈ 日均 QPS × 3~5 倍
并发用户 ≈ QPS × 平均响应时间（Little's Law）
```

### Step 3：数据准备
- 账号池：准备 1000~10000 个测试账号（避免单账号 session 冲突）
- 数据池：商品、地址、优惠券等所需数据提前入库
- 防刷白名单：把压测 IP 加到限流白名单

### Step 4：环境
- **严禁在生产压测**（除非有全链路压测基础设施）
- 测试环境配置应**等比例缩放**：生产 10 台 → 测试 1~2 台，结论按比例推算
- 关闭日志的 DEBUG 级别，接近生产

## 5. Locust 模式

```python
# perf/locustfile.py
from locust import HttpUser, task, between, events
import random


@events.test_start.add_listener
def on_start(environment, **kwargs):
    # 全局前置：确认服务可达
    pass


class ShopUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """每个 VU 启动时登录一次"""
        r = self.client.post("/api/auth/login", json={
            "email": f"perf+{random.randint(1, 10000)}@example.com",
            "password": "perf123",
        })
        self.token = r.json()["data"]["token"]
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(6)
    def browse_products(self):
        self.client.get("/api/products?page=1", name="GET /products")

    @task(2)
    def view_detail(self):
        pid = random.randint(1, 1000)
        self.client.get(f"/api/products/{pid}", name="GET /products/{id}")

    @task(1)
    def create_order(self):
        with self.client.post(
            "/api/orders",
            json={"productId": random.randint(1, 1000), "qty": 1},
            name="POST /orders",
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.failure(f"下单失败: {r.status_code} {r.text[:200]}")
            elif r.json().get("code") != 0:
                r.failure(f"业务失败: {r.json()}")
```

**启动脚本**：

```js
// scripts/perf-locust.js
import { execSync } from "node:child_process";
execSync(
  "locust -f perf/locustfile.py --host https://staging.example.com " +
    "--users 500 --spawn-rate 20 --run-time 10m --headless --html logs/perf-report.html",
  { stdio: "inherit" }
);
```

## 6. k6 模式

```js
// perf/k6/order.js
import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const orderLatency = new Trend("order_latency");
const bizErrorRate = new Rate("biz_error_rate");

export const options = {
  scenarios: {
    load: {
      executor: "ramping-vus",
      stages: [
        { duration: "2m", target: 100 }, // 爬坡
        { duration: "5m", target: 100 }, // 保持
        { duration: "2m", target: 0 },   // 爬降
      ],
    },
  },
  thresholds: {
    "http_req_duration{name:POST /orders}": ["p(95)<500", "p(99)<1000"],
    "http_req_failed": ["rate<0.001"],
    "biz_error_rate": ["rate<0.005"],
  },
};

export function setup() {
  const r = http.post("https://staging.example.com/api/auth/login", {
    email: "perf@example.com",
    password: "perf123",
  });
  return { token: r.json("data.token") };
}

export default function (data) {
  const headers = { Authorization: `Bearer ${data.token}`, "Content-Type": "application/json" };
  const res = http.post(
    "https://staging.example.com/api/orders",
    JSON.stringify({ productId: 100, qty: 1 }),
    { headers, tags: { name: "POST /orders" } }
  );
  orderLatency.add(res.timings.duration);
  const ok = check(res, {
    "status 200": r => r.status === 200,
    "code 0":    r => r.json("code") === 0,
  });
  bizErrorRate.add(!ok);
  sleep(1);
}
```

执行：`k6 run perf/k6/order.js --out json=logs/k6-result.json`

## 7. JMeter 适用场景

适合：
- 需要 GUI 编辑（新手或非代码人员）
- 多协议混合测试（HTTP + JDBC + JMS + FTP）
- 企业级插件生态（InfluxDB + Grafana 集成）

不推荐：
- 代码驱动的压测（k6/Locust 更好）
- CI 流水线（JMeter 报告集成弱）

关键做法：
- 用非 GUI 模式跑：`jmeter -n -t plan.jmx -l result.jtl -e -o report/`
- GUI 只用来调试脚本

## 8. 指标解读与瓶颈定位

### 看到曲线怎么读
- **QPS 达到某值后不再上涨** → 吞吐量瓶颈
- **响应时间随并发线性增长** → 资源不足或锁竞争
- **响应时间陡增断崖** → 触发限流 / GC / 连接池打满
- **错误率突然飙升** → 依赖挂了 / 限流生效 / OOM

### 逐层定位
1. **客户端**：压测机器 CPU/网络是否成为瓶颈？（分布式压测解决）
2. **网关 / LB**：Nginx 连接数、后端连接池
3. **应用层**：JVM GC、线程池、ORM 连接池
4. **DB**：慢查询日志、锁等待、索引
5. **缓存**：命中率、Redis 连接数
6. **外部依赖**：第三方接口超时

### 常用排查命令
```bash
# Linux 通用
top / htop                # CPU、内存
iostat -x 1               # 磁盘 IO
vmstat 1                  # 系统负载
ss -s / netstat -s        # 网络连接
pidstat -p <pid> 1        # 进程级细节

# JVM
jstack <pid>              # 线程栈
jstat -gcutil <pid> 1s    # GC 情况
jmap -histo <pid>         # 堆对象分布

# DB
SHOW PROCESSLIST;         # MySQL 活跃查询
SHOW ENGINE INNODB STATUS;
pg_stat_activity          # PostgreSQL
```

## 9. 性能报告模板

```markdown
# {项目名} 性能测试报告 v{版本}

## 1. 测试概述
- 测试目标：验证下单接口在 500 并发下的表现
- 测试时间：2026-04-21 14:00 ~ 14:30
- 测试人：{姓名}

## 2. 环境
| 项 | 配置 |
|---|-----|
| 应用服务器 | 4C8G × 2 |
| 数据库 | MySQL 8.0，8C16G |
| 缓存 | Redis 7.0，2C4G |
| 网络 | 内网千兆 |
| 被测版本 | v1.2.3 (commit abc1234) |

## 3. 场景设计
- 场景：登录 → 浏览商品 → 下单
- 负载模型：500 VU，2 分钟爬坡，5 分钟保持
- 思考时间：1~3 秒

## 4. 测试结果
| 接口 | 请求数 | TPS | Avg | P50 | P95 | P99 | 错误率 |
|-----|-------|-----|-----|-----|-----|-----|-------|
| POST /auth/login | 500 | 8.3 | 120ms | 110ms | 200ms | 350ms | 0% |
| GET /products | 32,100 | 107 | 85ms | 70ms | 180ms | 320ms | 0% |
| POST /orders | 5,200 | 17.3 | 420ms | 380ms | 780ms | **1.5s** | 0.08% |

## 5. 资源使用
| 组件 | CPU 峰值 | 内存峰值 | 备注 |
|-----|---------|---------|-----|
| App-1 | 82% | 6.2G | 接近上限 |
| App-2 | 80% | 6.1G | |
| MySQL | 65% | 11G | 有慢查询 |
| Redis | 15% | 1G | 富余 |

## 6. 瓶颈分析
- **POST /orders P99 1.5s 超标**：慢查询 `SELECT ... FROM orders WHERE user_id = ?` 未命中索引
- **App CPU 接近 80%**：未来扩容阈值建议设 70%

## 7. 结论与建议
- ✅ 负载测试目标基本达成（除下单 P99 未达标）
- ❗ 上线前需在 `orders.user_id` 增加索引
- ❗ 建议生产环境至少准备 3 台 App 服务器

## 8. 附件
- logs/k6-result.json
- grafana 监控截图
- 慢查询日志
```
