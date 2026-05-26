# 峰极量化联合项目 V1 — 需求文档与开发计划

| 字段 | 内容 |
|------|------|
| 文档编号 | FJLHXM-V1 |
| 版本 | 1.0.0-draft |
| 状态 | 规划稿 |
| 基线项目 | 峰极量化项目-V1（离线 CSV/SQLite 回测引擎） |
| 设计工具 | pencil.dev（网页端 / 移动端 UI 原型与高保真） |
| 后端语言 | Python 3.12+ |
| 创建日期 | 2026-05-25 |

---

## 1. 项目背景与目标

### 1.1 背景

当前 **峰极量化项目-V1** 已具备：

- **峰极 OS 层**：`src/quant/os_engine.py`（3-3/T+3、硬化峰极线、红蓝阵营状态机）
- **定式层 DS01–DS08**：各自信号、入场、止损与结构审计
- **峰极总定式合一引擎**：`unified_whitelist_engine.py`（账本：不反仓、同向最多 3 笔）
- **离线回测 CLI**、沙盒图脚本、OKX 加密观察监测、本地 SQLite 行情库雏形

缺口：无统一 **Web / 移动端**、无 **模拟实盘持久化数据库**、无 **订阅付费**、无面向用户的 **1–5 年可视化回测与实时监测产品化界面**。

### 1.2 项目目标（FJLHXM-V1）

在 **「峰极 OS 负责结构、定式层负责交易规则」** 不变的前提下，建设一套 **可订阅的模拟实盘量化产品**：

1. **网页端 + 移动端** 双端一致体验
2. **首页** 展示各定式（DS01–DS08）及 **峰极总定式** 的历史回测概览
3. **历史回测模块**：用户可选 **1 年 / 2 年 / 3 年 / 4 年 / 5 年** 窗口，K 线图上清晰标注买卖、收益金额、收益曲线
4. **模拟实盘监测模块**：按品种 K 线实时（准实时）展示信号、持仓、账本事件；覆盖 **国内期货、A 股、海外虚拟货币、美股** 四大市场
5. **模拟实盘数据库**：统一存储行情、OS 状态、信号、成交、权益、订阅与审计
6. **订阅付费**：分层权益（免费预览 / 标准 / 专业 / 机构），支撑可持续运营

### 1.3 非目标（V1 明确不做）

- 不接入真实券商/交易所自动下单（V1 仅模拟实盘 + 观察信号）
- DS09（九重天 D1+M15）已纳入峰极总定式；见 `docs/DS09_IN_TOTAL_PATTERN.md`
- 不在 V1 实现全量 Level-2  tick 级回放（以 K 线周期为主：1D / 1H / 15m / 5m）

### 1.4 成熟案例参考

| 产品 | 借鉴点 |
|------|--------|
| **TradingView** | K 线交互、指标叠加、买卖标记、多周期切换 |
| **QuantConnect / 聚宽** | 策略回测报告、权益曲线、按策略/品种筛选 |
| **Binance / OKX 模拟盘** | 虚拟资金、持仓、逐仓保证金展示 |
| **雪球 / 同花顺** | 首页行情卡片、自选、板块分组 |
| **Notion / Linear 定价页** | 订阅档位清晰对比、试用转化 |

设计阶段用 **pencil.dev** 产出 Web + Mobile 信息架构、组件库与关键页面原型，再交给前端实现。

---

## 2. 架构原则

### 2.1 分层模型

```text
┌─────────────────────────────────────────────────────────────┐
│  表现层：Web（Next.js） / Mobile（React Native 或 Flutter）   │
├─────────────────────────────────────────────────────────────┤
│  API 层：FastAPI（REST + WebSocket 推送）                     │
├─────────────────────────────────────────────────────────────┤
│  应用层：回测编排 / 模拟实盘调度 / 订阅鉴权 / 报表聚合         │
├─────────────────────────────────────────────────────────────┤
│  领域层：                                                     │
│    · 峰极 OS 层（结构：峰极线、阵营、转势）                    │
│    · 定式层 DS01–DS08（交易：信号、止损、审计）                │
│    · 总控账本（峰极总定式）                                    │
├─────────────────────────────────────────────────────────────┤
│  数据层：PostgreSQL + TimescaleDB / Redis / 对象存储           │
│  行情采集：国内期货、A 股、OKX 加密、美股（yfinance/第三方）    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 与现有代码的关系

| 现有模块 | V1 迁移策略 |
|----------|-------------|
| `quant/os_engine.py` | 抽为 **纯 Python 包** `fengji_core`，供 API Worker 调用 |
| `quant/ds01.py` … `ds08.py` | 同上，零 UI 依赖 |
| `unified_whitelist_engine.py` | 封装为 `run_unified_backtest()` / `run_unified_monitor()` 服务函数 |
| `market_data_store.py` | 逻辑迁移至 PostgreSQL；SQLite 仅作本地开发降级 |
| `crypto_combined_monitor.py` | 改造为 **定时 Job**，结果写入模拟实盘库 |
| `plot_ds*_sandbox.py` | 后端生成标注数据；前端 K 线组件渲染（替代静态 matplotlib 为主路径） |
| CSV 结果文件 | V1 以 **数据库为主、CSV 导出为辅** |

**宪法不变**：`docs/CANONICAL_RULES.md` 与 `docs/FENGJI_TOTAL_PATTERN_SPEC.md` 仍为 OS / 总定式最高准绳。

---

## 3. 用户角色与权限

| 角色 | 说明 | V1 权限 |
|------|------|---------|
| 访客 | 未登录 | 首页公开指标摘要、1 个演示品种 1 年回测预览 |
| 免费用户 | 注册未付费 | 1 年回测、监测延迟 15 分钟、最多 3 个自选 |
| 标准订阅 | 月付/年付 | 1–3 年回测、监测延迟 1 分钟、20 自选、单定式详情 |
| 专业订阅 | 月付/年付 | 1–5 年回测、准实时监测、全市场、峰极总定式、导出 |
| 机构订阅 | 合同 | API 只读、多席位、私有部署选项（V1.1+） |
| 管理员 | 内部 | 品种上下架、白名单、任务监控、审计 |

---

## 4. 功能需求 — 网页端

### 4.1 信息架构（IA）

```text
峰极量化 Web
├── 首页（Dashboard）
├── 历史回测
│   ├── 定式回测（DS01 … DS08 各一页）
│   ├── 峰极总定式回测
│   └── 回测详情（K 线 + 交易列表 + 权益曲线 + 指标卡）
├── 模拟实盘监测
│   ├── 国内期货
│   ├── A 股
│   ├── 海外虚拟货币
│   └── 美股
├── 品种详情（K 线主战场）
│   ├── 周期切换（1D / 1H / 15m / 5m，按定式/市场可用性）
│   ├── 峰极 OS 叠加（hardened_fengji_line、红蓝阵营色带）
│   ├── 买卖标记 / 持仓 / 止损线
│   └── 侧边栏：信号流、账本事件、模拟持仓
├── 我的
│   ├── 自选
│   ├── 模拟账户（权益、持仓、历史成交）
│   └── 订阅与账单
├── 定价 / 订阅
└── 帮助与文档（链到 docs 摘要）
```

### 4.2 首页（Dashboard）

**需求 ID：WEB-HOME-001**

- 顶部：**四大市场** 入口 Tab（国内期货 / A 股 / 海外 crypto / 美股）
- 中部：**定式卡片矩阵**（DS01–DS08 + 峰极总定式）
  - 每卡片：定式名称、中文别名（挫棍、指形战法等）、默认 1 年回测收益率、最大回撤、交易次数、bad_audits 状态
  - 点击跳转对应 **历史回测列表页**
- 下部：
  - **模拟实盘概览**：全市场今日信号数、观察中品种数、总模拟权益（聚合）
  - **热门品种** 滚动条（按订阅热度 / 信号频率）
- 未登录：敏感数字脱敏；登录后按订阅档位显示完整数据

**UI 设计（pencil.dev）**：参考 TradingView 首页 + 聚宽策略广场卡片布局；深色/浅色双主题。

### 4.3 历史回测模块

**需求 ID：WEB-BT-001 ~ WEB-BT-010**

| ID | 需求描述 | 验收标准 |
|----|----------|----------|
| WEB-BT-001 | 回测时间窗口 | 用户可选 **1 / 2 / 3 / 4 / 5 年**（相对当前日或数据最新日回溯） |
| WEB-BT-002 | 定式维度 | 支持单定式 DS01–DS08 与 **峰极总定式** 独立回测 |
| WEB-BT-003 | 品种维度 | 按市场筛选；支持搜索、自选、白名单标签 |
| WEB-BT-004 | 异步任务 | 回测 >3s 走任务队列，展示进度条；结果可缓存 |
| WEB-BT-005 | K 线标注 | 买入 ↑ / 卖出 ↓ 明确标记；hover 显示：定式、方向、入场价、止损、盈亏 |
| WEB-BT-006 | OS 叠加 | 可选显示 hardened 峰极线、红蓝阵营背景、active_high/low |
| WEB-BT-007 | 收益曲线 | 独立 Chart：权益、回撤阴影、基准对比（可选） |
| WEB-BT-008 | 指标卡 | 总收益、年化、最大回撤、Sharpe、胜率、交易次数、bad_audits |
| WEB-BT-009 | 交易明细表 | 可排序、导出 CSV（专业档） |
| WEB-BT-010 | 资金模型 | 按市场切换：期货（保证金+乘数）、crypto（逐仓 2x）、A 股/美股（现金账户） |

**回测参数默认值（与现项目对齐）**

```text
期货：initial_cash=100000, lots=1, commission=0.0001, slippage=1 tick
Crypto：initial_cash=1000, margin_per_trade=200, leverage=2, fee=0.05%/side
A 股/美股：initial_cash=100000, 整股/整手规则（V1 可先简化）
OS：gap=3, atr_window=14
```

### 4.4 模拟实盘监测模块

**需求 ID：WEB-MON-001 ~ WEB-MON-008**

| ID | 需求描述 |
|----|----------|
| WEB-MON-001 | 四大市场 **分板块** 列表：品种、最新价、阵营、今日信号、模拟持仓状态 |
| WEB-MON-002 | 点击进入 **品种 K 线页**，默认展示监测周期（crypto DS08 默认 H1 等） |
| WEB-MON-003 | **准实时刷新**：免费 15min 延迟；标准 1min；专业 WebSocket 推送 |
| WEB-MON-004 | 展示 **candidate / accepted / rejected** 信号及拒单原因（对齐 ledger） |
| WEB-MON-005 | 模拟账户：**虚拟资金** 按用户订阅独立或共享演示账户（V1 建议每用户独立 paper account） |
| WEB-MON-006 | 信号 **只观察不下单** 开关可见（合规文案）；V1 不向交易所发单 |
| WEB-MON-007 | 飞书/Telegram/Web 通知（专业档，对接现有 webhook 配置模式） |
| WEB-MON-008 | 审计：strategy_bad_trades 必须为 0 才显示「结构合格」徽章 |

### 4.5 品种 K 线图页（核心页面）

**需求 ID：WEB-CHART-001 ~ WEB-CHART-006**

- **图表引擎**：Lightweight Charts（TradingView 开源）或 ECharts K 线
- **图层**（可开关）：
  1. OHLCV K 线
  2. hardened_fengji_line 折线
  3. 红/蓝阵营区间色带
  4. 买卖标记 + 止损线
  5. 成交量
- **联动**：点击交易明细行，K 线定位到 entry/exit；双击重置缩放
- **移动端适配**：pinch 缩放、横屏全屏 K 线

**pencil.dev 交付物**：`designs/web-chart-detail.pen`、`designs/web-backtest-report.pen`

### 4.6 订阅付费模块

**需求 ID：WEB-SUB-001 ~ WEB-SUB-006**

| 档位 | 月价（示意） | 核心权益 |
|------|-------------|----------|
| 免费 | ¥0 | 1 年回测预览、3 自选、延迟监测 |
| 标准 | ¥99/月 | 3 年回测、20 自选、1min 监测、单定式 |
| 专业 | ¥299/月 | 5 年回测、全市场、总定式、导出、通知 |
| 年付 | 8 折 | 同上 |

**支付渠道（V1 优先级）**：

1. 微信支付 / 支付宝（国内）
2. Stripe（海外 crypto / 美股用户）
3. 兑换码 / 对公转账（机构）

**功能**：

- 定价页、结账、订阅状态、发票申请（V1.1）
- 后端 **Feature Gate** 中间件：按 `subscription_tier` 限制回测年限、品种数、刷新频率
- 试用：专业档 7 天（需绑手机）

---

## 5. 功能需求 — 移动端

### 5.1 原则

与 Web **同 API、同数据模型**；移动端优先：**首页 → 自选 → 品种 K 线 → 回测摘要**。

### 5.2 信息架构

```text
峰极量化 App
├── Tab1 首页（定式卡片 + 市场概览）
├── Tab2 监测（四市场列表）
├── Tab3 回测（定式/总定式 + 年限选择）
├── Tab4 我的（账户、订阅、设置）
└── 模态：K 线全屏、交易详情、订阅升级
```

### 5.3 关键需求

| ID | 需求 |
|----|------|
| MOB-001 | iOS + Android（推荐 **React Native + Expo** 或 **Flutter**，与 Web 共享 TS 类型） |
| MOB-002 | K 线页手势、深色模式、推送（Firebase / APNs） |
| MOB-003 | 离线缓存：最近查看的 5 个品种 K 线最后一屏快照 |
| MOB-004 | 生物识别登录（Face ID / 指纹） |
| MOB-005 | 订阅走 Apple IAP / Google Play Billing + 后端收据校验 |
| MOB-006 | 与 Web 订阅互斥逻辑：同一账号以最高有效档为准 |

**pencil.dev 交付物**：`designs/mobile-home.pen`、`designs/mobile-chart.pen`、`designs/mobile-pricing.pen`

### 5.4 成熟案例对照

| 场景 | 参考 App |
|------|----------|
| K 线 + 标记 | TradingView Mobile、同花顺 |
| 模拟盘 | 东方财富模拟炒股、Binance Lite |
| 订阅 | Bloomberg Mobile、Wind 金融终端 |

---

## 6. 模拟实盘数据库设计

### 6.1 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| 主库 | **PostgreSQL 16** | 用户、订阅、账本、回测元数据 |
| 时序 | **TimescaleDB** 扩展 | bars、os_snapshots、equity_points |
| 缓存/队列 | **Redis** + **Celery** / ARQ | 回测任务、监测 Job、WS pub/sub |
| 对象存储 | MinIO / S3 | 大型 CSV 导出、沙盒 PNG 归档 |
| 迁移 | Alembic | Python 与现有栈一致 |

在现有 `market_data.sqlite` 之上 **升级而非废弃**：导入脚本 `scripts/migrate_sqlite_to_pg.py`。

### 6.2 核心表结构（逻辑模型）

#### 6.2.1 行情与市场

```sql
-- instruments：统一品种主数据
CREATE TABLE instruments (
    id              BIGSERIAL PRIMARY KEY,
    market          TEXT NOT NULL,  -- FUTURES | A_STOCK | CRYPTO | US_STOCK
    symbol          TEXT NOT NULL,
    name            TEXT,
    exchange        TEXT,
    currency        TEXT,
    multiplier      NUMERIC,
    tick_size       NUMERIC,
    margin_rate     NUMERIC,
    is_whitelisted  BOOLEAN DEFAULT FALSE,
    metadata        JSONB,
    UNIQUE (market, symbol)
);

-- bars：Timescale hypertable
CREATE TABLE bars (
    instrument_id   BIGINT NOT NULL,
    timeframe       TEXT NOT NULL,  -- 1D | 1H | 15m | 5m
    dt              TIMESTAMPTZ NOT NULL,
    open, high, low, close, volume NUMERIC,
    source          TEXT,
    PRIMARY KEY (instrument_id, timeframe, dt)
);
```

#### 6.2.2 用户与订阅

```sql
CREATE TABLE users (...);
CREATE TABLE subscriptions (
    user_id, tier, status, provider, expires_at, ...
);
CREATE TABLE paper_accounts (
    id, user_id, market_group, initial_cash, cash, equity, ...
);
```

#### 6.2.3 回测结果

```sql
CREATE TABLE backtest_jobs (
    id UUID PRIMARY KEY,
    user_id, strategy_id, instrument_id,
    years SMALLINT CHECK (years BETWEEN 1 AND 5),
    status, params JSONB, started_at, finished_at
);

CREATE TABLE backtest_trades (
    job_id, strategy_id, direction,
    entry_time, exit_time, entry_price, exit_price,
    net_pnl, initial_stop, exit_reason, ...
);

CREATE TABLE backtest_equity (
    job_id, dt, equity, drawdown
);

CREATE TABLE backtest_metrics (
    job_id, total_return, ann_return, max_dd, sharpe, win_rate, bad_audits
);
```

#### 6.2.4 模拟实盘 / 监测

```sql
CREATE TABLE monitor_runs (
    id, instrument_id, run_at, reference_bar_time, ...
);

CREATE TABLE signals (
    run_id, strategy_id, signal_type,  -- candidate | accepted | rejected
    direction, entry_time, entry_price, reject_reason, ...
);

CREATE TABLE paper_positions (
    account_id, instrument_id, strategy_id,
    direction, entry_time, entry_price, qty,
    initial_stop, current_stop, status
);

CREATE TABLE ledger_events (
    account_id, event_time, event_type,  -- open | close | reject | conflict
    payload JSONB
);

CREATE TABLE os_snapshots (
    instrument_id, timeframe, bar_time,
    camp, active_high, active_low,
    identity_line JSONB,
    hardened_line JSONB
);
```

#### 6.2.5 与现有 CSV 字段映射

| 现有文件 | 目标表 |
|----------|--------|
| `candidate_trades.csv` | `signals` (type=candidate) + `backtest_trades` |
| `accepted_trades.csv` | `signals` + `paper_positions` |
| `rejected_orders.csv` | `signals` (type=rejected) |
| `ledger_events.csv` | `ledger_events` |
| `equity.csv` | `backtest_equity` |
| `strategy_bad_trades.csv` | `backtest_metrics.bad_audits` 计数 + 明细 JSONB |
| `os_log.csv` / engine frame | `os_snapshots` |

### 6.3 数据采集与更新频率

| 市场 | 来源（V1） | 更新 |
|------|-----------|------|
| 国内期货 | 现有 CSV 目录 + 后续 CTP/第三方 | 日 K 日更；H1 按需 |
| A 股 | `data/a_stock/` + Tushare/AkShare | 日更 |
| 海外 crypto | OKX REST（沿用 `fetch_okx_history`） | 1H/15m 每 1–5 分钟 Job |
| 美股 | yfinance / Polygon（V1 日 K） | 日更 |

---

## 7. 后端 API 概要

**框架**：FastAPI + Pydantic v2 + SQLAlchemy 2.0

### 7.1 主要 REST 端点

```text
POST   /api/v1/auth/register|login|refresh
GET    /api/v1/dashboard/summary
GET    /api/v1/strategies                          # DS01-08 + TOTAL
GET    /api/v1/instruments?market=&q=
POST   /api/v1/backtests                           # body: strategy_id, instrument_id, years
GET    /api/v1/backtests/{job_id}
GET    /api/v1/backtests/{job_id}/trades
GET    /api/v1/backtests/{job_id}/equity
GET    /api/v1/backtests/{job_id}/chart-bundle     # K线+OS+markers 一次拉取
GET    /api/v1/monitor/markets/{market}/overview
GET    /api/v1/monitor/instruments/{id}/live
GET    /api/v1/monitor/instruments/{id}/signals
GET    /api/v1/paper/accounts/me
GET    /api/v1/subscriptions/plans
POST   /api/v1/subscriptions/checkout
WS     /api/v1/ws/monitor?token=
```

### 7.2 后台任务

| Job | 周期 | 说明 |
|-----|------|------|
| `ingest_bars_*` | 按市场 | 写入 bars |
| `run_monitor_symbol` | 1–5 min | 封装 `crypto_combined_monitor` 逻辑 |
| `run_backtest_job` | 按需 | Celery Worker 调用 `fengji_core` |
| `aggregate_dashboard` | 5 min | 首页定式卡片统计 |
| `subscription_reconcile` | 1 h | 支付回调对账 |

### 7.3 Python 包结构（建议 monorepo）

```text
峰极量化项目-V1/
├── packages/
│   └── fengji_core/          # 从 src/quant + unified 引擎抽取
├── services/
│   └── api/                  # FastAPI
├── workers/
│   └── celery_app/
├── web/                      # Next.js 14 App Router
├── mobile/                   # React Native
├── designs/                  # pencil.dev .pen 文件
└── FJLHXM-V1.md
```

---

## 8. 前端技术方案

### 8.1 Web

| 项 | 选型 |
|----|------|
| 框架 | **Next.js 14**（App Router, RSC 用于 Dashboard） |
| UI | Tailwind CSS + shadcn/ui |
| 图表 | lightweight-charts + recharts（权益曲线） |
| 状态 | TanStack Query + Zustand |
| 鉴权 | NextAuth.js 或 Clerk |

### 8.2 Mobile

| 项 | 选型 |
|----|------|
| 框架 | **Expo (React Native)** — 与 Web 共享 TS 类型与 API Client |
| 图表 | react-native-lightweight-charts 或 WebView 嵌 TradingView 风格组件 |
| 导航 | Expo Router |

### 8.3 pencil.dev 工作流

1. **Phase 0** 完成 IA 与 Design Token（色板：红阵营 #E53935、蓝阵营 #1E88E5、深色背景 #0D1117）
2. 产出页面：**首页、回测报告、K 线详情、监测列表、定价页** × Web/Mobile 共 10+ 屏
3. 设计评审 → 导出规格 → 前端按组件拆分实现
4. 所有 `.pen` 存于 `designs/`，README 链接预览截图

---

## 9. 非功能需求

| 类别 | 指标 |
|------|------|
| 性能 | 回测结果页首屏 <2s（缓存命中）；K 线 5000 根流畅缩放 |
| 可用性 | API 99.5%（V1）；监测 Job 失败自动重试 3 次 |
| 安全 | JWT 短期 + Refresh；支付回调签名校验；敏感配置 KMS |
| 合规 | 全站「模拟实盘、不构成投资建议」；不提供真实下单入口 |
| 审计 | 所有拒单、bad_trade 可追溯；管理员操作日志 |
| i18n | V1 中文为主；crypto/美股模块预留英文 |

---

## 10. 开发计划（分阶段）

### Phase 0 — 规划与设计（2 周）

| 任务 | 产出 |
|------|------|
| 确认 FJLHXM-V1 需求评审 | 签字版需求基线 |
| pencil.dev 全站 IA + 核心 10 屏 | `designs/*.pen` |
| DB ER 图 + OpenAPI 草案 | `docs/api/openapi.yaml` |
| 抽取 `fengji_core` 包 | 单元测试覆盖 OS + DS05 |

**里程碑 M0**：设计稿 + API 草案 + core 包可 pip install -e

---

### Phase 1 — 数据层与回测 API（4 周）

| 任务 | 产出 |
|------|------|
| PostgreSQL + TimescaleDB 部署 | docker-compose.yml |
| 表结构 Alembic 迁移 | migrations/ |
| SQLite/CSV → PG 导入 | ingest 脚本 |
| `POST /backtests` + Worker | 1–5 年 DS01–08 + 总定式 |
| chart-bundle API（K线+标记+OS） | 供前端一次拉取 |

**里程碑 M1**：Postman 可跑通「生猪 3 年 DS05 回测」并返回 chart-bundle

---

### Phase 2 — Web MVP（5 周）

| 任务 | 产出 |
|------|------|
| 首页 Dashboard | 定式卡片 + 四市场入口 |
| 历史回测列表 + 详情页 | 年限选择、指标卡、权益曲线 |
| K 线页 v1 | 买卖标记、OS 线、阵营色带 |
| 登录注册 + 免费档 Feature Gate | |

**里程碑 M2**：Web 端可演示完整「选品种 → 选 5 年 → 看 K 线回测」

---

### Phase 3 — 模拟实盘监测（4 周）

| 任务 | 产出 |
|------|------|
| 监测 Job 管线 | crypto 先行，期货/A 股跟进 |
| paper_accounts + ledger 写入 | |
| 监测列表 + 实时 K 线 WebSocket | |
| 用户模拟账户页 | |

**里程碑 M3**：crypto 10 品种准实时监测上线（观察模式）

---

### Phase 4 — 订阅付费（3 周）

| 任务 | 产出 |
|------|------|
| 定价页 + 微信/Stripe 接入 | |
| 订阅档位 Feature Gate | 年限/延迟/导出 |
| 管理后台（品种上下架） | 简易 Admin |

**里程碑 M4**：完成一笔真实测试订阅并解锁 5 年回测

---

### Phase 5 — Mobile + 美股（4 周）

| 任务 | 产出 |
|------|------|
| Expo App：首页 / 监测 / K 线 / 我的 | TestFlight + 内测 APK |
| 美股日 K ingest（yfinance） | US_STOCK 板块 |
| 推送通知（专业档） | |
| 性能与安全审计 | |

**里程碑 M5**：双端发布 1.0.0（模拟实盘）

---

### Phase 6 — 打磨与扩展（持续）

- A 股 / 期货监测全量
- DS09 研究频道（与总定式隔离）
- 机构 API、私有部署
- 沙盒图导出、社交分享卡片

---

## 11. 总体排期

```text
Phase 0  ██ 2w
Phase 1  ████ 4w
Phase 2  █████ 5w
Phase 3  ████ 4w
Phase 4  ███ 3w
Phase 5  ████ 4w
─────────────────
合计约 22 周（~5.5 个月）至 V1.0 双端上线
```

建议团队配置：

| 角色 | 人数 |
|------|------|
| Python 后端 / 量化 | 1–2 |
| 前端 Web | 1 |
| 移动端 | 1 |
| UI/UX（pencil.dev） | 0.5 |
| DevOps | 0.5 |

---

## 12. 风险与依赖

| 风险 | 缓解 |
|------|------|
| 行情源不稳定 | 多源 fallback；bars 表保留 source 字段 |
| 回测计算量大 | 结果缓存（instrument+strategy+years 哈希）；预计算热门组合 |
| 支付合规 | 先上兑换码内测；正式接入需企业主体 |
| OS 规则变更 | fengji_core 版本号；回测 job 记录 engine_version |
| 美股/ A 股规则差异 | 各市场独立 `ExecutionModel` 插件 |

---

## 13. V1 验收清单

- [ ] 首页展示 DS01–DS08 + 峰极总定式回测摘要（默认 1 年，可切换）
- [ ] 任意白名单品种可选 **1–5 年** 回测，K 线买卖标记清晰
- [ ] 收益金额、权益曲线、最大回撤等指标与现有 CLI 结果一致（抽样 10 组对比）
- [ ] 四市场板块监测列表可访问，crypto 准实时更新
- [ ] 模拟实盘库完整记录 signals / ledger / paper_positions
- [ ] 订阅付费可阻断超档功能（如 5 年回测、导出）
- [ ] Web + Mobile 核心路径体验一致
- [ ] pencil.dev 设计稿与实现对齐度评审通过
- [ ] 全站模拟实盘免责声明与 bad_audits=0 徽章逻辑正确

---

## 14. 附录

### 14.1 定式中文名对照

| ID | 名称 |
|----|------|
| DS01 | 挫棍 |
| DS02 | 阴阳相吃 |
| DS03 | 二四棒 |
| DS04 | 夹棍 / 隔山炮 |
| DS05 | 指形战法 |
| DS06 | 政权革命 / 外扩峰 |
| DS07 | 共振决战 |
| DS08 | 夺权 |
| TOTAL | 峰极总定式 |

### 14.2 相关现有文档

- `docs/CANONICAL_RULES.md`
- `docs/FENGJI_TOTAL_PATTERN_SPEC.md`
- `docs/LOCAL_MARKET_DATA_DB.md`
- `docs/CRYPTO_COMBINED_SYSTEM.md`
- `README.md`

### 14.3 文档修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0-draft | 2026-05-25 | 首版需求与开发计划 |

---

*本文档为 FJLHXM-V1 的规划基线。进入 Phase 1 前建议召开需求评审，冻结 OS/定式宪法范围与 V1 市场优先级（建议：Crypto 监测 → 期货回测 → A 股 → 美股）。*
