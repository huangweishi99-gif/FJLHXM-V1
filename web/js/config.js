/** 峰极 Web · API 与全局配置 */
window.FengJiConfig = {
  API_BASE: (() => {
    const params = new URLSearchParams(window.location.search);
    const override = params.get("api_base");
    if (override) return override.replace(/\/$/, "");
    if (window.location.protocol === "http:" || window.location.protocol === "https:") {
      return window.location.origin;
    }
    // 本地开发默认 8001（8000 可能被旧 API 占用且代码未更新）
    return "http://127.0.0.1:8001";
  })(),

  STRATEGY_ANIM: {
    DURATION_SEC: 10,
    ENGINE_VERSION: "fengji_core@0.1.0",
    LOTTIE: {
      ENABLED: true,
      MODE: "auto",
      CDN: "https://unpkg.com/lottie-web@5.12.2/build/player/lottie.min.js",
      BASE_PATH: "assets/lottie",
      SOURCES: {
        DS01: "DS01.json",
        DS02: "DS02.json",
        DS03: "DS03.json",
        DS04: "DS04.json",
        DS05: "DS05.json",
        DS06: "DS06.json",
        DS07: "DS07.json",
        DS08: "DS08.json",
        DS09: "DS09.json",
        TOTAL: "TOTAL.json",
      },
    },
  },

  STRATEGY_META: {
    TOTAL: { alias: "峰极总定式", desc: "DS01–DS08 合一引擎，不反仓" },
    DS01: { alias: "挫棍式", desc: "初始挫棍，左30线≤2" },
    DS02: { alias: "阴阳相吃式", desc: "红阳吃阴 / 蓝阴吃阳" },
    DS03: { alias: "二四棒式", desc: "合法假峰/假极 + active 结构" },
    DS04: { alias: "夹棍式", desc: "K1/K2/K3 夹棍结构" },
    DS05: { alias: "指形式", desc: "K2 可能形成极的位置" },
    DS06: { alias: "外扩峰式", desc: "转势授权 + 外扩峰启动" },
    DS07: { alias: "共振式", desc: "同向延续 / 反向并轨" },
    DS08: { alias: "否认确定式", desc: "五点结构 + 否认/确定" },
    DS09: { alias: "九重天", desc: "D1 阵营 + M15 二次攻击（A股/LC）" },
  },

  MARKETS: [
    { id: "FUTURES", label: "期货", icon: "📈", defaultSymbol: "PVC" },
    { id: "A_STOCK", label: "A股", icon: "🇨🇳", defaultSymbol: "000021" },
    { id: "CRYPTO", label: "虚拟货币", icon: "₿", defaultSymbol: "ETHUSDT" },
    { id: "US_STOCK", label: "美股", icon: "🇺🇸", defaultSymbol: "AAPL" },
  ],

  /** 国内期货代码 ↔ 中文名（品种搜索别名，与 fengji_core.symbol_names 对齐） */
  FUTURES_CN_NAMES: {
    SA: "纯碱",
    FG: "玻璃",
    RB: "螺纹钢",
    PG: "液化气",
    FU: "燃油",
    CJ: "红枣",
    OI: "菜油",
    SP: "纸浆",
    LH: "生猪",
    JD: "鸡蛋",
    SI: "工业硅",
    PP: "聚丙烯",
    SH: "烧碱",
    EB: "苯乙烯",
    NI: "沪镍",
    SR: "白糖",
    EG: "乙二醇",
    AO: "氧化铝",
    JM: "焦煤",
    EC: "集运欧线",
    RU: "橡胶",
    BR: "合成橡胶",
    SF: "硅铁",
    M: "豆粕",
    MA: "甲醇",
    P: "棕榈",
    V: "PVC",
    TA: "PTA",
    UR: "尿素",
    CF: "棉花",
    LC: "碳酸锂",
    AU: "沪金",
    AG: "沪银",
    SC: "原油",
    I: "铁矿",
    SM: "锰硅",
    RM: "菜粕",
  },

  /** 期货中文俗称 → 短代码（补充 FUTURES_CN_NAMES 未覆盖的口语） */
  FUTURES_CN_ALIASES: {
    黄金: "AU",
    白银: "AG",
    沪金: "AU",
    沪银: "AG",
    原油: "SC",
    铁矿: "I",
    铁矿石: "I",
    豆粕: "M",
    棕榈油: "P",
    棕榈: "P",
  },

  /** 模拟监测 · 演示品种目录（不按市场分栏） */
  MONITOR_CATALOG: [
    { symbol: "BTCUSDT", market: "CRYPTO", name: "比特币" },
    { symbol: "ETHUSDT", market: "CRYPTO", name: "以太坊" },
    { symbol: "SOLUSDT", market: "CRYPTO", name: "Solana" },
    { symbol: "BNBUSDT", market: "CRYPTO", name: "BNB" },
    { symbol: "DOGEUSDT", market: "CRYPTO", name: "狗狗币" },
    { symbol: "LTCUSDT", market: "CRYPTO", name: "莱特币" },
    { symbol: "ADAUSDT", market: "CRYPTO", name: "Cardano" },
    { symbol: "AVAXUSDT", market: "CRYPTO", name: "Avalanche" },
    { symbol: "LINKUSDT", market: "CRYPTO", name: "Chainlink" },
    { symbol: "RENDERUSDT", market: "CRYPTO", name: "Render" },
    { symbol: "000021", market: "A_STOCK", name: "深科技" },
    { symbol: "000063", market: "A_STOCK", name: "中兴通讯" },
    { symbol: "PVC", market: "FUTURES", name: "PVC" },
    { symbol: "LC", market: "FUTURES", name: "碳酸锂" },
    { symbol: "CJ", market: "FUTURES", name: "红枣" },
    { symbol: "SA", market: "FUTURES", name: "纯碱" },
    { symbol: "FG", market: "FUTURES", name: "玻璃" },
    { symbol: "PP", market: "FUTURES", name: "聚丙烯" },
    { symbol: "SI", market: "FUTURES", name: "工业硅" },
    { symbol: "SF", market: "FUTURES", name: "硅铁" },
    { symbol: "JD", market: "FUTURES", name: "鸡蛋" },
    { symbol: "EC", market: "FUTURES", name: "集运欧线" },
    { symbol: "LH", market: "FUTURES", name: "生猪" },
    { symbol: "PG", market: "FUTURES", name: "液化气" },
    { symbol: "AAPL", market: "US_STOCK", name: "苹果" },
    { symbol: "NVDA", market: "US_STOCK", name: "英伟达" },
  ],

  MONITOR_DEMO_QUOTES: {
    BTCUSDT: 73701.93,
    ETHUSDT: 2493.03,
    SOLUSDT: 81.31,
    BNBUSDT: 657.1,
    DOGEUSDT: 0.10137,
    LTCUSDT: 52.34,
    ADAUSDT: 0.2423,
    AVAXUSDT: 9.28,
    LINKUSDT: 9.523,
    RENDERUSDT: 2.366,
    "000021": 12.48,
    "000063": 32.15,
    PVC: 4943,
    LC: 98200,
    CJ: 9270,
    SA: 1200,
    FG: 1020,
    PP: 8215,
    SI: 6240,
    SF: 6320,
    JD: 3450,
    EC: 1800,
    LH: 11935,
    PG: 3900,
    AAPL: 198.5,
    NVDA: 118.2,
  },

  DEFAULT_SUBSCRIPTION_PLAN: "free",

  /** 订阅档位 · 权限说明唯一数据源（品种仅限制数量，不限制池） */
  SUBSCRIPTION_PLANS: {
    free: {
      label: "免费",
      trialDays: 7,
      strategies: ["DS01", "DS02", "DS03"],
      years: [1],
      maxWatchlist: 3,
      monitorDelay: "15 分钟",
      features: [
        "可用定式 01–03 进行历史回测与模拟监测（不含峰极总定式 TOTAL）",
        "1 年历史回测试用",
        "注册后 7 天有效，期满需升级",
        "模拟监测延迟 15 分钟",
        "回测与监测共享名额，全库任选最多 3 个品种",
      ],
    },
    standard: {
      label: "标准",
      strategies: ["DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08", "DS09"],
      years: [1, 3],
      maxWatchlist: 20,
      monitorDelay: "1 分钟",
      features: [
        "可用定式 01–09 进行历史回测与模拟监测（不含峰极总定式 TOTAL）",
        "1 年、3 年历史回测",
        "模拟监测延迟 1 分钟",
        "回测与监测共享名额，全库任选最多 20 个品种",
        "满额后需先移除已有品种，再添加新品种",
      ],
    },
    pro: {
      label: "专业",
      strategies: ["TOTAL", "DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08", "DS09"],
      years: [1, 3, 5],
      maxWatchlist: 50,
      monitorDelay: "准实时 WebSocket",
      features: [
        "定式 01–09 与峰极总定式 TOTAL 全部可用",
        "1 年、3 年、5 年历史回测",
        "模拟监测 WebSocket 准实时",
        "回测与监测共享名额，全库任选最多 50 个品种",
        "回测支持导出 CSV、查看同类历史成交、按信号强弱筛选",
      ],
    },
  },

  PRICING_TIER_META: {
    free: {
      name: "免费",
      price: "¥0",
      priceSuffix: "",
      tagline: "免费试用 7 天",
      featured: false,
      cta: "注册免费试用",
      ctaHref: "login.html?mode=register&intent=free",
      ctaVariant: "primary",
      trialNote: "注册后自动开启 7 天试用；期满未订阅将暂停回测与监测权限。",
    },
    standard: {
      name: "标准",
      price: "¥99",
      priceSuffix: "/月",
      tagline: "",
      featured: true,
      cta: "订阅标准档",
      ctaHref: "payment.html?pay=standard",
      ctaVariant: "primary",
      trialNote: "",
    },
    pro: {
      name: "专业",
      price: "¥299",
      priceSuffix: "/月",
      tagline: "",
      featured: false,
      cta: "订阅专业档",
      ctaHref: "payment.html?pay=pro",
      ctaVariant: "primary",
      trialNote: "",
    },
  },

  /**
   * 三档独立流程（权限只认 localStorage fj-plan，URL ?plan= 不参与鉴权）
   * free    ：注册试用 → 回测页
   * standard：订阅扫码 → 模拟监测
   * pro     ：订阅扫码 → 历史回测
   */
  PLAN_FLOW: {
    free: {
      label: "免费试用",
      registerEntry: "login.html?mode=register&intent=free",
      afterRegister: "backtest.html",
      afterLogin: "index.html",
      homeFeature: "backtest.html",
    },
    standard: {
      label: "标准订阅",
      subscribeEntry: "payment.html?pay=standard",
      afterPayment: "monitor.html",
      homeFeature: "monitor.html",
    },
    pro: {
      label: "专业订阅",
      subscribeEntry: "payment.html?pay=pro",
      afterPayment: "backtest.html",
      homeFeature: "backtest.html",
    },
  },

  /** 扫码付款确认后 · 各档唯一落地页（不含 ?plan=，避免 URL 串档） */
  PAYMENT_SUCCESS_ROUTES: {
    standard: {
      href: "monitor.html",
      label: "标准档已开通",
      hint: "即将进入模拟监测（标准档专属入口）",
    },
    pro: {
      href: "backtest.html",
      label: "专业档已开通",
      hint: "即将进入历史回测（专业档专属入口）",
    },
  },
};

(function attachPricingTiers(cfg) {
  const order = ["free", "standard", "pro"];
  cfg.PRICING_TIERS = order.map((planId) => {
    const plan = cfg.SUBSCRIPTION_PLANS[planId];
    const meta = cfg.PRICING_TIER_META[planId] || {};
    return {
      planId,
      ...meta,
      features: plan?.features || [],
    };
  });
})(window.FengJiConfig);
