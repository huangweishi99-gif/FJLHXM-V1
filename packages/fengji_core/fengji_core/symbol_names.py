"""品种中文名映射：飞书等通知里把代码显示成「中文(代码)」。"""
from __future__ import annotations

# 国内期货/A股：合约代码 -> 中文名。覆盖模拟盘 symbols 全集。
FUTURES_CN_NAMES: dict[str, str] = {
    "SA": "纯碱",
    "FG": "玻璃",
    "RB": "螺纹钢",
    "PG": "液化气",
    "FU": "燃油",
    "CJ": "红枣",
    "OI": "菜油",
    "SP": "纸浆",
    "LH": "生猪",
    "JD": "鸡蛋",
    "SI": "工业硅",
    "PP": "聚丙烯",
    "SH": "烧碱",
    "EB": "苯乙烯",
    "NI": "沪镍",
    "SR": "白糖",
    "EG": "乙二醇",
    "AO": "氧化铝",
    "JM": "焦煤",
    "EC": "集运欧线",
    "RU": "橡胶",
    "BR": "合成橡胶",
    "SF": "硅铁",
    "M": "豆粕",
    "MA": "甲醇",
    "P": "棕榈",
    "V": "PVC",
    "TA": "PTA",
    "UR": "尿素",
    "CF": "棉花",
    "LC": "碳酸锂",
    "AU": "沪金",
    "AG": "沪银",
    "SC": "原油",
    "I": "铁矿",
    "SM": "锰硅",
    "RM": "菜粕",
}

# 海外虚拟货币：基础币种 -> 中文/通用名。无公认中文译名的保留项目名。
CRYPTO_CN_NAMES: dict[str, str] = {
    "BTC": "比特币",
    "ETH": "以太坊",
    "SOL": "索拉纳",
    "AVAX": "雪崩",
    "TRUMP": "特朗普币",
    "RENDER": "渲染币",
    "IO": "io.net",
    "TAO": "Bittensor",
    "DASH": "达世币",
    "LTC": "莱特币",
    "DOGE": "狗狗币",
    "ADA": "艾达币",
    "APT": "Aptos",
    "LINK": "Chainlink",
    "BNB": "币安币",
    "ZEC": "大零币",
    "XRP": "瑞波币",
    "BCH": "比特币现金",
    "TRX": "波场币",
    "DOT": "波卡",
    "MATIC": "马蹄",
    "SHIB": "柴犬币",
    "UNI": "Uniswap",
    "ATOM": "Cosmos",
    "FIL": "文件币",
    "ARB": "Arbitrum",
    "OP": "Optimism",
    "SUI": "Sui",
    "NEAR": "Near",
    "INJ": "Injective",
    "SEI": "Sei",
    "TIA": "Celestia",
    "PEPE": "佩佩",
    "WIF": "dogwifhat",
}


def _clean(symbol: str) -> str:
    return str(symbol).strip().upper().replace("-", "").replace("_", "")


def normalize_a_stock_symbol(symbol: str) -> str:
    """A 股代码统一为 6 位（PG 样本里可能存 2475 / 988 这类短码）。"""
    sym = _clean(symbol)
    if sym.isdigit() and len(sym) <= 6:
        return sym.zfill(6)
    return sym


# A 股中文名（回测 PG 样本 + HOT20）；缺映射时仅显示 6 位代码。
A_STOCK_CN_NAMES: dict[str, str] = {
    "300308": "中际旭创",
    "300502": "新易盛",
    "300059": "东方财富",
    "002475": "立讯精密",
    "002594": "比亚迪",
    "300750": "宁德时代",
    "600519": "贵州茅台",
    "601899": "紫金矿业",
    "002241": "歌尔股份",
    "002230": "科大讯飞",
    "603019": "中科曙光",
    "000977": "浪潮信息",
    "002371": "北方华创",
    "688981": "中芯国际",
    "601138": "工业富联",
    "000725": "京东方A",
    "600036": "招商银行",
    "601318": "中国平安",
    "300760": "迈瑞医疗",
    "002414": "高德红外",
    "000988": "华工科技",
    "600522": "中天科技",
    "600105": "永鼎股份",
}


def a_stock_name(symbol: str) -> str | None:
    code = normalize_a_stock_symbol(symbol)
    return A_STOCK_CN_NAMES.get(code)


def a_stock_display(symbol: str) -> str:
    """A 股 -> 「中文(002475)」；缺映射时退回 6 位代码。"""
    code = normalize_a_stock_symbol(symbol)
    cn = A_STOCK_CN_NAMES.get(code)
    return f"{cn}({code})" if cn else code


def futures_display(symbol: str) -> str:
    """期货代码 -> 「中文(代码)」；缺映射时退回代码本身。"""
    code = _clean(symbol).removesuffix("USDT")
    cn = FUTURES_CN_NAMES.get(code)
    return f"{cn}({code})" if cn else code


def crypto_display(symbol: str) -> str:
    """加密交易对 -> 「中文(BTCUSDT)」；缺映射时退回交易对本身。"""
    text = _clean(symbol)
    if not text.endswith("USDT"):
        text = f"{text}USDT"
    base = text.removesuffix("USDT")
    cn = CRYPTO_CN_NAMES.get(base)
    return f"{cn}({text})" if cn else text
