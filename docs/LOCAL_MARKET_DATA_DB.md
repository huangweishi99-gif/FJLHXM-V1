# 本地行情数据库

状态：`ACTIVE`

本项目已建立本地 SQLite 行情库，后续回测优先从数据库读取，不再到处找 CSV 或临时下载。

数据库位置：

```text
data/market_data.sqlite
```

覆盖率表：

```text
data/market_data_coverage.csv
```

数据库工具：

```text
src/market_data_store.py
```

## 数据结构

核心表：

```text
instruments  # 品种表
bars         # K线表
```

`bars` 主键：

```text
market + symbol + timeframe + dt
```

支持市场：

```text
CRYPTO
FUTURES
A_STOCK
```

支持周期：

```text
1D
1H
15m
5m
```

统一 K 线字段：

```text
date, open, high, low, close, volume
```

## 已导入数据

已导入：

```text
A股：高德红外 002414 日线、60分钟线
国内期货：实盘数据日K线、5-60分钟csv
虚拟货币：data/crypto_okx 本地缓存
```

## 常用命令

初始化数据库：

```powershell
python src\market_data_store.py --db data\market_data.sqlite init
```

导入 A 股缓存：

```powershell
python src\market_data_store.py --db data\market_data.sqlite import-a-stock --dir data\a_stock
```

导入虚拟货币缓存：

```powershell
python src\market_data_store.py --db data\market_data.sqlite import-crypto-okx --dir data\crypto_okx
```

导入国内期货：

```powershell
python src\market_data_store.py --db data\market_data.sqlite import-futures `
  --daily-dir "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线" `
  --minute-dir "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv"
```

查看覆盖率：

```powershell
python src\market_data_store.py --db data\market_data.sqlite coverage --out data\market_data_coverage.csv
```

从数据库导出回测 CSV：

```powershell
python src\market_data_store.py --db data\market_data.sqlite export `
  --market A_STOCK `
  --symbol 002414 `
  --timeframe 1D `
  --out results\db_export_check\002414_1D.csv
```

A股峰极总定式回测优先使用数据库：

```powershell
python src\backtest_a_stock_fengji.py `
  --symbol 002414 `
  --name 高德红外 `
  --initial-cash 20000 `
  --data-source db `
  --out-dir results\fengji_total_a_stock_002414_gaodehongwai_db
```

`--data-source` 说明：

```text
auto     = 默认，先查数据库；数据库缺数据才下载
db       = 强制只用数据库，缺数据直接报错
download = 强制走东方财富下载/CSV缓存
```

## 使用原则

以后回测流程：

```text
1. 先查 data/market_data_coverage.csv
2. 数据齐全则从 data/market_data.sqlite 导出标准 CSV
3. 回测脚本只吃导出的标准 CSV
4. 缺数据才新增下载或导入，不临时到处找文件
```

这样做可以避免：

```text
路径混乱
同一品种多份 CSV 口径不一致
重复下载
回测结果无法复现
```
