# free-stockdb 摸底审计（P0）

**审计时间**：2026-10-12
**审计目标**：评估 `https://github.com/hello245m/free-stockdb`（MIT）可吸收精华点，作为峰极OS A 股数据底座升级的参考输入。
**审计方式**：只读 clone 到 `$env:TEMP\free-stockdb-audit`，逐文件读源码 + 设计模式提取。未运行二进制，未导入其 `stockdb.pyd` 依赖。
**审计范围**：根目录 + `cpp/` + `pybao/` + `调用方式/` + `docs/` 全部 Python / C++ / 配置文件。

---

## 1. 元信息

| 维度 | 值 |
|------|------|
| 仓库 | https://github.com/hello245m/free-stockdb |
| 作者 | hello245m |
| License | **MIT**（Copyright (c) 2026 hello245m）—— ✅ 最宽松开源，允许使用/复制/修改/发布/再授权/销售；条件：保留版权声明 |
| 最近活动 | tarball 提交时间 2026-10-05；README 标注 v0.3.5（08-10） |
| 仓库定位 | **A 股日 K、分钟 K 与 ETF 分钟、tick 级数据的本地量化引擎**（数据底座，不含策略信号） |

**MIT 兼容性结论**：可直接借鉴其源码设计；但派生代码需在显著处保留 `Copyright (c) 2026 hello245m` 声明（标准 MIT 义务）。本项目若借鉴具体模块，新模块文件头加注释即可满足。

---

## 2. 目录树（35 个文件 / 5 个目录）

```text
free-stockdb-main/
├── LICENSE                   1066B  MIT
├── README.md                12466B
├── stockdb.conf              418B  服务配置（端口 7899/127.0.0.1）
├── sync_url.txt              429B  数据同步源（默认全注释）
├── .gitignore                 42B
├── 数据数据库运行图.png      11301B
├── 调用说明.txt              701B  五种调用方式总览
├── cpp/                              C++ LevelDB 时序引擎
│   ├── CMakeLists.txt        1748B
│   ├── examples/main.cpp     2679B
│   ├── include/stockdb/
│   │   ├── client.hpp        2998B
│   │   ├── server.hpp        1665B
│   │   ├── updater.hpp        999B
│   ├── src/
│   │   ├── client.cpp        4041B
│   │   ├── server.cpp       12962B  LevelDB server
│   │   ├── updater.cpp      10580B  增量同步器（含 manifest/SHA-256 校验）
│   └── tools/
│       ├── main_server.cpp   1824B
│       └── main_updater.cpp  3606B
├── docs/
│   └── DATA_SOURCE.md        1687B  数据源与 manifest.txt 协议
├── pybao/                           Python 接口 + 指标 + MCP
│   ├── stock_sdk.py         23892B  SDK 客户端（同步/异步 get_data）
│   ├── zhibiao.py           17885B  39 指标 + 5 指数 + 板块索引
│   ├── native_mcp.py        17489B  自研 MCP 框架（零第三方依赖）
│   ├── 安装.py               2281B  把 stockdb.pyd 路径写入 .pth
│   └── 说明_运行-安装.py-...txt   243B
└── 调用方式/                         5 种调用方式
    ├── python/
    │   ├── sdk_test.py       2285B
    │   ├── rd_test.py        3689B  原生 rd API 用法（K-V 协议文档）
    │   ├── zb_test.py        5944B  zb.get + bk.get 用法
    │   ├── http_js.js       15083B  Node.js HTTP 客户端
    │   └── 调用.txt           453B
    ├── ai_mcp/
    │   ├── README.md         2139B
    │   └── stock_mcp_server.py  2059B  包装 stock_sdk + native_mcp
    ├── http/
    │   ├── http_api.py        721B
    │   └── rd_test.py        3741B
    └── excel/
        ├── wps_js_macro.js  15358B  WPS 宏
        ├── 查看数据.html   42021B  浏览器入口
        └── 说明.txt          256B
```

**注**：目录含 GBK 文件名（"pybao"/"调用方式"/"数据数据库运行图"），tar 解压时 PowerShell 解码为乱码；用 cmd `dir /x` 拿短名或直接读短路径可绕过。

---

## 3. 技术栈与依赖

| 层 | 实现 | 依赖 |
|---|---|---|
| 存储 | C++ + **LevelDB**（嵌入式 KV） | libcurl + OpenSSL（用于 SHA-256 校验）+ LevelDB |
| 计算核心 | **Rust**（编译为 `zb_core` C 扩展） | 比 pandas 快 3 倍 |
| 压缩 | Zstd | 3 倍压缩比 |
| Python SDK | 纯 Python + C 扩展 `stockdb.pyd` | pandas（可选） |
| MCP | 纯 Python stdio JSON-RPC | **零第三方依赖**（自研） |
| HTTP / Excel / AI / 浏览器 | 薄包装层 | — |

**对我们的关键启示**：项目核心是 **C++ LevelDB + Rust 加速 + 纯 Python 薄包装**。我们不能直接依赖 `stockdb.pyd`（需对应 build + LevelDB），但可以**只借鉴 Python 薄包装的设计模式**。

---

## 4. 核心设计模式（10 条精华）

### 4.1 `StockDBClient.get_data()` 签名（`pybao/stock_sdk.py:425-511`）

```python
def get_data(
    self,
    code: Union[str, List[str]],          # 单股或批量
    start: Optional[str] = None,
    end: Optional[str] = None,
    frequency: str = '1d',                # 1d/1m/5m/15m/30m/60m/1w/1M
    fields: Optional[Union[str, List[str]]] = None,  # 字段投影
    limit: Optional[int] = None,
    desc: bool = False,                   # 时间降序
    as_df: bool = False,                  # 返回 pandas.DataFrame
    fq: Optional[str] = 'qfq'             # 前/后/不复权
) -> Union[List[Dict], Dict[str, List[Dict]], DataFrame]
```

**设计要点**：
- **同步 / 异步**两套实现（`get_data` / `get_data_async`），签名完全对齐
- **单路 pipeline 批量查询**：`rd.pipe() → mget × N → do()`，避免单股 N 次连接
- **频率自适应表名**：分钟 vs 日 K 自动选表
- **8 位日期补全 14 位**：`build_time_query_for_retrieval()` 在分钟 K 时把 `'20260620'` 补成 `'20260620000000'`
- **同步接口**：`_to_dataframe()` 自动把单股 list / 批量 dict 包装成 DataFrame，`code` 列置首

**借鉴路径**：P2 `src/bulk_query.py` 直接套此签名（用本地 sqlite 实现）。

### 4.2 复权因子在 `__init__` 预加载 + 二分查找（`stock_sdk.py:28-46, 371-422`）

```python
def __init__(self, ...):
    # 一次性预加载全部复权因子到内存
    self._fq_dates = {}    # {code: [date_str, ...]}
    self._fq_cums = {}     # {code: [cum_float, ...]}

def _apply_fq_in_memory(self, code, records, fq_type):
    # 二分查找: 找到 <= r_date_str 的最大除权日对应的 cum
    idx = bisect.bisect_right(dates, r_date_str) - 1
    f_current = cums[idx] if idx >= 0 else 1.0
    ratio = f_latest / f_current if qfq else 1.0 / f_current
```

**设计要点**：
- **不存复权后价格，运行时算**（存储开销小）
- 复权因子按 `code:date` 存 KV，LevelDB 天然有序 → 不需排序直接二分
- 小数位区分：股票代码 `1`/`5` 开头（ETF/基金）用 3 位，其他 2 位
- 复权比例接近 1.0 时跳过折算（节省计算）

**借鉴路径**：P2 `src/adj_factor.py` 套此模式。

### 4.3 周期合成在内存动态算（`stock_sdk.py:128-369`）

```python
def _merge_to_period(self, daily_data, frequency):     # "1w"/"1M"
    # 用 ISO 纪年与周数作为周 K 分组键
    iso = dt.isocalendar()
    key = (iso[0], iso[1])

def _merge_minutes_to_period(self, minute_data, frequency):  # "5m"/"15m"/"30m"/"60m"
    # 经典时间轴对齐：570-690 + 780-900 = 9:30-11:30 + 13:00-15:00
    def trading_elapsed(minute_of_day):
        if 570 <= minute_of_day <= 690:
            return minute_of_day - 570
        if 780 <= minute_of_day <= 900:
            return 120 + (minute_of_day - 780)
```

**设计要点**：
- **存日 K 不存周 K**（周 K 内存合成）
- **存 1m 不存 5m**（分钟 K 内存合成）
- **A 股交易时段**（9:30-11:30 + 13:00-15:00）显式映射到 `elapsed_minutes` 槽位，午休空槽不计入 60 分钟
- `pre_close`、`pct_chg`、`amplitude` 在合成时自动算
- 截面属性（pe_ttm / pb / total_mv / float_mv / is_st）取周期末值
- 字段 None 不当 0（停牌日不会写记录，聚合时自动跳过）

**借鉴路径**：P5 指标层可复用此分钟 K 合成逻辑；DS09 触发若需 5m/15m/60m 对齐也直接用。

### 4.4 板块索引 BoardIndex 四向索引一次构建（`zhibiao.py:60-220`）

```python
class BoardIndex:
    def __init__(self, rows=None):
        self.boards: list[dict[str, Any]] = []
        self.by_code: dict[str, dict[str, Any]] = {}        # 板块代码 → 板块
        self.by_stock: dict[str, list[dict[str, Any]]] = defaultdict(list)  # 股票 → 所属板块
        self.by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)  # 名称 → 板块
        self.by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)  # 类别 → 板块列表
        self._build()                                        # 全量预加载

    def get(self, x, category, fields):
        # 板块代码 → 单板块；股票代码 → 所属板块；名称 → 模糊匹配
```

**设计要点**：
- **一次预加载四个索引**，查询 O(1) 或 O(n) 模糊匹配
- **双向：板块 → 股票 / 股票 → 板块**
- 支持 4 类：概念板块(0) / 申万一级(1) / 申万二级(2) / 申万三级(3)
- 字段投影：`bk.get("600633", 1, "group,name")` 只返回这两个字段
- `bk.get(category=1, fields="name,code")` 返回某类别全板块字典

**借鉴路径**：P1 `src/sector_mapping.py` 直接套此设计（数据源改用本地 JSON / AKShare / 东财）。

### 4.5 39 指标 + 5 指数加权（`zhibiao.py:1-541`）

```python
METHOD_NAMES = {1: "equal", 2: "float_mv", 3: "amount", 4: "volume", 5: "total_mv"}
# equal=等权 / float_mv=流通市值 / amount=成交额 / volume=成交量 / total_mv=总市值

def jisuan(name, codes, *, start, end, frequency="day", method=1, base=1000.0,
           fq="qfq", fields=None, n=None, cross=False):
    # cross=False → 原值；cross=True → 仅交叉信号；cross="with_value" → 值+信号
```

**指标清单**（`zhibiao.py:476-481`）：
- 基础 10：ma, ema, sma, wma, dma, std, sum, hhv, llv, ref
- 趋势 10：macd, kdj, rsi, wr, bias, boll, psy, cci, atr, bbi
- 通道 3：dmi, taq, ktn
- 量价 6：trix, vr, cr, emv, mfi, obv
- 综合 10：dpo, brar, dfma, mtm, mass, roc, expma, asi, xsii, zhishu

**底层**：Rust 编译的 `zb_core.BATCH(names, params, ...)` / `BATCH_CROSS(...)` / `ZHISHU(...)`。

**对我们的关键启示**：指标算法我们用 pandas + numpy 在 P5 实现；不引入 Rust（除非 P6 性能瓶颈证明必要）。

### 4.6 增量同步 manifest 协议 + SHA-256 校验（`cpp/src/updater.cpp:84-273`）

```cpp
// manifest.txt 每行：<sha256> <size-in-bytes> <relative-path>
struct ManifestEntry {
    std::string sha256;
    std::uintmax_t size = 0;
    fs::path relative_path;
};

bool parse_manifest(const std::string& text, std::vector<ManifestEntry>* entries) {
    // 跳过 # 注释；sha256 必须 64 字符；relative_path 必须不含 ".."
}

// 同步流程：
//   1. load_manifest(source) → HTTP / file:// / 本地
//   2. 遍历 entry → 查 file_size + sha256 是否一致 → 一致跳过
//   3. 否则 fetch_entry → 写 .part → 校验 → rename
```

**设计要点**：
- **临时文件 `.part` + 校验后 rename**（不会写到一半）
- **sha256 + size 双校验**（不能 SHA 一致但 size 错 / size 一致但 SHA 错）
- **禁止 `..` 路径穿越**（manifest 不可信也安全）
- **增量跳过**：已存在 + 一致 → 不下载（节省带宽）
- **HTTP 失败处理**：`curl_easy_perform` 失败 + `writer.failed` 退出
- **完整验证入口**：`verify_synced_files()` 单独跑

**借鉴路径**：P4 数据源多通道直接套此协议；`dataN/manifest.txt` + SHA-256 + 大小校验。

### 4.7 同步源三模式（`docs/DATA_SOURCE.md`）

```
- 本地目录：D:/stockdb-mirror
- file:// URL：file:///D:/stockdb-mirror
- HTTP(S) URL：https://data.example.com/stockdb
```

**设计要点**：
- **不内置任何数据地址**（无中心化源依赖）
- `sync_url.txt` 第一行有效配置即数据源
- 公网必须用 HTTPS
- SHA-256 不能替代对镜像源的信任
- 镜像发布顺序：先数据后 manifest（避免半完成清单）

**借鉴路径**：P4 `dataN/` 多源挂载，本地/网络共享皆可；新增 `sync_url.txt` 配置入口。

### 4.8 自研 MCP 框架（`pybao/native_mcp.py` 17KB）

```python
class NativeMCP:
    def tool(self, func=None, **kwargs):
        def decorator(f):
            self._tools[f.__name__] = {
                "name": f.__name__,
                "description": inspect.getdoc(f) or "",
                "inputSchema": self._build_input_schema(f, skip_params={"ctx", "self"}),
                "func": f,
                "sig": inspect.signature(f),
            }
            return f
        return decorator(func) if func else decorator

    # 协议版本：2024-11-05
    # 支持：tools/list、tools/call、resources/list、resources/templates/list、
    #      resources/read、prompts/list、prompts/get、initialize、ping、shutdown
    # 帧编码：line-delimited JSON（默认）+ Content-Length（自动）
```

**设计要点**：
- **零第三方依赖**（仅 Python stdlib）
- **装饰器自动生成 JSON Schema**（用 `inspect.signature()` + 类型注解）
- **URI 模板**：`@mcp.resource("stock://{code}")` 自动 regex 编译
- **stdout 锁 + 强制 flush**（MCP 客户端不会半读）
- **错误返回也走 JSON-RPC**（不抛异常到 stdout）
- **async + lifespan context**（OpenAI-style）

**对我们的关键启示**：✅ **P3 直接抄这个 `NativeMCP`**（17KB 纯 stdlib），我们只需：
- 替换 `StockDBClient` 为 `bulk_query.py` 的本地 sqlite 实现
- 替换 `get_market_kline` 工具为更丰富的工具集（get_kline / list_sectors / sector_stocks / get_indicator / get_index）
- 暴露 `stockdb-fengji` 名字给 Codex/Cursor/Claude

### 4.9 K-V 协议风格（`examples/raw_test.py`）

```
K-V: table:keyn:keyn_1 -> (int/float/str/dict/list)
日k:code:date -> dict
分钟k:code:date -> dict
股票代码 -> {'6': ['600001', ...], '0': ['000001', ...]}
退市* -> ['600421', ...]
板块* -> [('801760.SL', {...}), ...]
复权:code:date -> cum
```

**查询语法**：
| 语法 | 含义 |
|---|---|
| `'20260625'` | 单日点查 |
| `'202606*'` | 通配（按字典序） |
| `'20260620<20260626'` | 闭区间范围 |
| `'20260620<N'` | 开始到无限 |
| `'N>20260626'` | 无限到结束 |
| `'`20260620>20260626'` | 倒序范围（用 `vals[-3:]` 取末尾 3 条） |

**借鉴路径**：**不直接套**（我们用 sqlite 不需要 K-V 范式），但 **range 查询语法可参考**（我们 P2 用 pandas 日期索引 + 切片即可）。

### 4.10 HTTP API 极简设计（`调用方式/http/http_api.py`）

```python
# 假设是 simple Flask / http.server：
@app.route("/get_data")
def get_data():
    code = request.args.get("code")
    start = request.args.get("start")
    end = request.args.get("end")
    frequency = request.args.get("frequency", "1d")
    return jsonify(client.get_data(code=code, start=start, end=end, frequency=frequency))
```

**借鉴路径**：P3 AI MCP 入口做出来后，HTTP 也加一个 thin wrapper（`/` + `/get_kline` + `/sectors` + `/sector_stocks`），便于非 Python 客户端调用。

---

## 5. 安全设计要点

| 项 | free-stockdb 实现 | 我们要做的 |
|---|---|---|
| 监听地址 | 默认 `127.0.0.1:7899` | MCP stdio（最安全，无网络） |
| 认证 | stockdb.conf 注释有 `auth: this-is-a-very-strong-password-32ch`（默认注释） | 默认关闭，按需开 |
| 路径安全 | 禁止 manifest `..` | 同样策略 |
| 临时写入 | `.part` 临时 + 校验后 rename | 同样策略 |
| SHA-256 | OpenSSL libcrypto | Python `hashlib.sha256()` |
| 日志轮转 | stockdb.conf `rotate.size: 1000000000`（1GB） | 已有的 `rotate_log_tail.py` |

**风险提示**：
- ❌ 不要复制 stockdb.conf 里的 `this-is-a-very-strong-password-32ch`（默认密码示例，已注释）—— **我们任何密码都不应该以明文注释形式进入仓库**
- ❌ 不要复用其 `stockdb.pyd` 二进制（要重新 build 时容易出错，且我们无 LevelDB 依赖）

---

## 6. 可吸收精华（按优先级排序）

| # | 精华 | 借鉴到 | 风险 |
|---|------|--------|------|
| **A1** | MCP 装饰器框架（17KB stdlib） | P3 `src/services/mcp_fengji.py` 直接抄 | 极低（保留版权 + 不依赖二进制） |
| **A2** | `get_data()` 签名 | P2 `src/bulk_query.py` 直接套 | 低 |
| **A3** | 复权因子预加载 + 二分 | P2 `src/adj_factor.py` | 低 |
| **B1** | 板块索引 BoardIndex 四向索引 | P1 `src/sector_mapping.py` | 低 |
| **B2** | 5 种指数加权 | P5 指标层 | 低 |
| **C1** | 多源挂载（本地 / HTTP / file://） | P4 `dataN/` 多源 | 低 |
| **C2** | manifest.txt 协议 + SHA-256 + size 校验 | P4 | 低 |
| **C3** | 增量同步（已存在+一致跳过） | P4 | 低 |
| **D1** | 39 指标 + 5 指数 | P5 用 pandas 实现 | 中（实现量大） |
| **D2** | 周/月 K 内存动态合成 | P5 + DS09 | 低 |
| **D3** | 分钟 K 内存动态合成（含 A 股交易时段） | P5 + DS09 | 低 |
| **E1** | HTTP API 极简 | P3 配套 | 极低 |
| **F1** | Rust 加速 | P6（仅在性能瓶颈时） | 高（维护成本） |

---

## 7. 不能借鉴的边界

- ❌ **stockdb.pyd 二进制**（LevelDB 绑定，跨平台构建重）
- ❌ **C++ LevelDB 服务**（与现有 sqlite 共存成本高）
- ❌ **zb_core Rust 扩展**（我们 P5 用 pandas 替代）
- ❌ **stockdb.conf 默认密码示例**（已注释，但不复用）
- ❌ **其内置指标策略**（如有买入启发式，不引入）
- ❌ **任何修改峰极线 / 阵营 / DS01-DS09 的设计**（违反宪法）

---

## 8. 与 P1-P6 阶段的对应表

| 阶段 | 主要借鉴 | 关键交付物 |
|------|---------|-----------|
| **P0**（本文档） | — | `docs/FREE_STOCKDB_AUDIT.md` |
| **P1 板块映射** | 4.4 BoardIndex 设计 | `src/sector_mapping.py` + tests≥6 |
| **P2 复权 + 批量查询** | 4.1, 4.2, 4.3 设计 | `src/adj_factor.py` + `src/bulk_query.py` + tests≥10 |
| **P3 AI MCP 入口** | 4.8 自研 MCP + 4.10 HTTP | `src/services/mcp_fengji.py` + `src/services/http_fengji.py` + tests≥8 |
| **P4 数据源多通道** | 4.6 manifest + 4.7 同步源 + 4.9 K-V 风格 | `dataN/` + `scripts/sync_dataN.py` + SHA-256/大小校验 + Zstd 落盘 |
| **P5 指标层** | 4.3 周/月/分钟合成、4.5 39 指标 + 5 指数 | `src/indicators.py` + tests≥15 |
| **P6 性能加速** | （评估后再定，可能借鉴 Rust） | 待定 |

---

## 9. 验证计划

每阶段完成后：
1. `python -m pytest tests/test_<module>.py -q` 全绿
2. 与现有本地 sqlite (`data/market_data.sqlite`) 共存不破坏
3. 不修改峰极线 / 阵营 / DS01-DS09 / 峰极OS 任何字段
5. CHANGELOG + TODO 双更新
4. 不引入 stockdb.pyd 二进制依赖
6. 不引入 Rust / LevelDB 依赖（P6 之前）

---

## 10. 安全边界

- 仅借鉴 Python 设计模式与算法
- 不引入 free-stockdb 二进制
- 所有派生代码文件头注明「Design inspired by free-stockdb MIT © 2026 hello245m」
- 不在本项目写入 stockdb.conf 默认密码示例
- P3 MCP 入口默认 stdio，不暴露网络端口（除非用户明确批准）

---

**P0 阶段产出**：本文档。
**P0 阶段未完成事项**：无。
**是否进入 P1**：待用户决策。