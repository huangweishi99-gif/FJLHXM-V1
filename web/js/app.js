/** 峰极 Web · 共享 UI 逻辑 */
(function () {
  const CFG = window.FengJiConfig;

  function getTheme() {
    return localStorage.getItem("fj-theme") || "light";
  }

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("fj-theme", theme);
    const btn = document.getElementById("themeToggle");
    if (btn) btn.textContent = theme === "dark" ? "☀️" : "🌙";
  }

  function renderNav(active) {
    const nav = document.getElementById("appleNav");
    if (!nav) return;
    const links = [
      { href: "index.html", label: "首页" },
      { href: "backtest.html", label: "历史回测" },
      { href: "monitor.html", label: "模拟监测" },
      { href: "strategies.html", label: "策略学堂" },
      { href: "pricing.html", label: "订阅" },
      { href: "community.html", label: "交流群" },
    ];
    nav.innerHTML = links
      .map(
        (l) =>
          `<a href="${l.href}" class="${active === l.href ? "active" : ""}">${l.label}</a>`
      )
      .join("");
  }

  function buildNavShell(activePage) {
    return `
<nav class="apple-nav">
  <div class="apple-nav-inner">
    <a class="apple-logo" href="index.html">
      <span class="apple-logo-mark">峰</span>
      <span>峰极量化</span>
    </a>
    <div class="apple-nav-links" id="appleNav"></div>
    <div class="apple-nav-actions">
      <button class="btn btn-ghost btn-sm" id="themeToggle" type="button" title="切换主题">🌙</button>
      <a class="btn btn-ghost btn-sm nav-pricing-link" href="pricing.html">订阅</a>
      <span id="navUserSlot"></span>
      <a class="btn btn-primary btn-sm" href="backtest.html">开始回测</a>
    </div>
  </div>
</nav>`;
  }

  function maskAccount(account) {
    const s = String(account || "").trim();
    if (!s) return "用户";
    if (s.length <= 4) return s;
    return `${s.slice(0, 3)}***${s.slice(-2)}`;
  }

  function isLoggedIn() {
    const token = getAccessToken();
    const session = getAuthSession();
    const account = (session?.user?.account || getCurrentUser() || "").trim();
    return Boolean(token || account);
  }

  function renderNavAuth() {
    const slot = document.getElementById("navUserSlot");
    if (!slot) return;
    const token = getAccessToken();
    const session = getAuthSession();
    const account = (session?.user?.account || getCurrentUser() || "").trim();
    if (isLoggedIn()) {
      const plan = getSubscriptionPlan();
      const label = CFG.SUBSCRIPTION_PLANS?.[plan]?.label || plan;
      const displayAccount = account || "用户";
      slot.innerHTML = `
        <span class="nav-user-badge" title="${escapeHtml(displayAccount)} · ${escapeHtml(label)}档">
          <span class="nav-user-plan">${escapeHtml(label)}</span>
          <span class="nav-user-id">${escapeHtml(maskAccount(displayAccount))}</span>
        </span>
        <button class="btn btn-ghost btn-sm nav-logout-btn" type="button" id="navLogoutBtn">退出</button>`;
      document.getElementById("navLogoutBtn")?.addEventListener("click", () => {
        authLogout();
      });
      return;
    }
    slot.innerHTML = `<a class="btn btn-ghost btn-sm" href="${loginUrlWithReturn()}">登录</a>`;
  }

  function clearAuthSession() {
    localStorage.removeItem("fj-access-token");
    localStorage.removeItem("fj-auth");
    localStorage.removeItem("fj-user");
    localStorage.setItem("fj-plan", "free");
    if (!localStorage.getItem("fj-trial-start")) {
      localStorage.setItem("fj-trial-start", new Date().toISOString());
    }
    renderNavAuth();
  }

  function authLogout() {
    clearAuthSession();
    renderNavAuth();
    document.dispatchEvent(new CustomEvent("fj-auth-ready"));
  }

  function initShell(activePage) {
    stripPlanQueryFromUrl();
    const mount = document.getElementById("navMount");
    if (mount) {
      mount.innerHTML = buildNavShell(activePage);
      renderNav(activePage);
      renderNavAuth();
      setTheme(getTheme());
      document.getElementById("themeToggle")?.addEventListener("click", () => {
        setTheme(getTheme() === "dark" ? "light" : "dark");
      });
    }
    void refreshAuthSessionFromApi().then(() => {
      renderNavAuth();
      document.dispatchEvent(new CustomEvent("fj-auth-ready"));
    });
  }

  async function fetchStrategies() {
    try {
      const res = await fetch(`${CFG.API_BASE}/api/v1/strategies`);
      if (!res.ok) return [];
      return await res.json();
    } catch {
      return [];
    }
  }

  async function fetchSymbolSummary(market, limit = 500) {
    const q = new URLSearchParams({ market, limit: String(limit) });
    const res = await fetch(`${CFG.API_BASE}/api/v1/backtests/symbol-summary?${q}`);
    if (!res.ok) return [];
    return await res.json();
  }

  function symbolSummaryRowCode(row) {
    return String(row?.display_symbol || row?.symbol || "").trim();
  }

  function symbolSummaryRowLabel(row) {
    const code = symbolSummaryRowCode(row);
    const name = String(row?.symbol_name || "").trim();
    const sym = String(row?.symbol || "").trim();
    if (!name || name === sym || code.includes(name)) return code;
    return `${code} · ${name}`;
  }

  function catalogDisplayLabel(row, { includeMarket = false } = {}) {
    const display = String(row?.display_symbol || "").trim();
    const sym = String(row?.symbol || "").trim();
    const name = String(row?.symbol_name || "").trim();
    let title = display || sym || name || "—";
    if (name && name !== sym && !title.includes(name)) {
      title = `${title} · ${name}`;
    }
    if (includeMarket) {
      return `${title} · ${marketLabel(row?.market)}`;
    }
    return title;
  }

  function catalogRowToWatchEntry(row) {
    let symbol = String(row?.symbol || symbolSummaryRowCode(row)).trim().toUpperCase();
    if (/^\d+$/.test(symbol) && symbol.length < 6) symbol = symbol.padStart(6, "0");
    return {
      symbol,
      market: String(row?.market || "").toUpperCase(),
      name: String(row?.symbol_name || "").trim(),
    };
  }

  function futuresCnName(code) {
    return (CFG.FUTURES_CN_NAMES || {})[String(code || "").trim().toUpperCase()] || "";
  }

  function futuresCodeFromAlias(text) {
    const sym = String(text || "").trim().toUpperCase();
    if (!sym) return "";
    if ((CFG.FUTURES_CN_NAMES || {})[sym]) return sym;
    for (const [code, name] of Object.entries(CFG.FUTURES_CN_NAMES || {})) {
      if (String(name).trim().toUpperCase() === sym) return code;
    }
    for (const [alias, code] of Object.entries(CFG.FUTURES_CN_ALIASES || {})) {
      if (String(alias).trim().toUpperCase() === sym) return String(code || "").trim().toUpperCase();
    }
    return "";
  }

  function validateSymbolMarketPair(symbol, market) {
    const mkt = String(market || "").toUpperCase();
    const sym = String(symbol || "").trim().toUpperCase();
    if (!sym) return { ok: false, message: "请选择品种" };
    if (mkt === "A_STOCK" && !/^\d{6}$/.test(sym)) {
      const fut = futuresCodeFromAlias(sym);
      if (fut) {
        return {
          ok: false,
          message: `「${symbol}」是国内期货（${fut}），不是 A 股代码。请将市场切换为「期货」后重试。`,
        };
      }
      return {
        ok: false,
        message: `A 股代码须为 6 位数字（当前「${symbol}」无效）。请切换市场或输入正确代码。`,
      };
    }
    if (mkt === "US_STOCK" && !/^[A-Z][A-Z0-9_.-]{0,11}$/.test(sym.replace(/_/g, ""))) {
      return { ok: false, message: `美股代码格式无效（当前「${symbol}」）。请使用如 AAPL、BRK_B。` };
    }
    return { ok: true, message: "" };
  }

  function isFuturesMarket(market) {
    const mkt = String(market || "").toUpperCase();
    return mkt === "FUTURES" || mkt === "CN_FUTURES";
  }

  function catalogRowSearchScore(row, query) {
    const q = String(query || "").trim().toUpperCase();
    if (!q) return 0;
    const sym = String(row?.symbol || "").trim().toUpperCase();
    const market = String(row?.market || "").toUpperCase();
    const name = String(row?.symbol_name || "").trim().toUpperCase();
    const display = String(row?.display_symbol || symbolSummaryRowCode(row) || "").trim().toUpperCase();
    const aliasCode = futuresCodeFromAlias(q);

    if (sym === q) return 1000;
    if (name === q) return 980;
    if (display === q) return 960;
    if (isFuturesMarket(market)) {
      if (aliasCode && sym === aliasCode && futuresCnName(sym).toUpperCase() === q) return 950;
      if (sym === q || name === q) return 940;
      if (aliasCode && (sym === aliasCode || sym === q)) return 930;
      if (futuresCnName(sym).toUpperCase() === q) return 920;
    }
    if (display.startsWith(q)) return 800;
    if (sym.startsWith(q)) return 780;
    if (name.startsWith(q)) return 760;
    if (display.includes(q)) return 600;
    if (name.includes(q)) return 580;
    if (sym.includes(q)) return 560;
    return 0;
  }

  function sortCatalogRowsByQuery(rows, query) {
    const q = String(query || "").trim().toUpperCase();
    if (!q) return rows || [];
    return [...(rows || [])].sort((a, b) => catalogRowSearchScore(b, q) - catalogRowSearchScore(a, q));
  }

  function catalogRowMatchesQuery(row, query) {
    const q = String(query || "").trim().toUpperCase();
    if (!q) return true;
    if (catalogRowSearchScore(row, q) <= 0) return false;

    const code = String(row?.symbol || "").trim().toUpperCase();
    const aliasCode = futuresCodeFromAlias(q);
    // PVC -> V 只允许命中期货，禁止误匹配美股 V / 其他市场的单字母代码
    if (aliasCode && code === aliasCode && q !== aliasCode) {
      return isFuturesMarket(row?.market);
    }
    return true;
  }

  function lookupSymbolCatalogRow(catalog, symbol, marketHint) {
    let sym = String(symbol || "").trim().toUpperCase();
    if (!sym) return null;
    if (/^\d+$/.test(sym) && sym.length < 6) sym = sym.padStart(6, "0");
    const mkt = marketHint ? String(marketHint).toUpperCase() : "";
    const inMarket = (row) => !mkt || mkt === "ALL" || String(row?.market || "").toUpperCase() === mkt;

    const pickBest = (matches) => {
      if (!matches.length) return null;
      if (matches.length === 1) return matches[0];
      const ranked = sortCatalogRowsByQuery(matches, sym);
      const exact = ranked.find((row) => String(row?.symbol || "").toUpperCase() === sym);
      if (exact) return exact;
      const aliasCode = futuresCodeFromAlias(sym);
      if (aliasCode) {
        const fut = ranked.find((row) => isFuturesMarket(row?.market)
          && String(row?.symbol || "").toUpperCase() === aliasCode);
        if (fut) return fut;
        const futByName = ranked.find((row) => isFuturesMarket(row?.market)
          && (String(row?.symbol || "").toUpperCase() === sym
            || String(row?.symbol_name || "").toUpperCase() === sym));
        if (futByName) return futByName;
      }
      const withChart = ranked.find((row) => row.has_chart_data !== false);
      return withChart || ranked[0];
    };

    const exact = (catalog || []).filter((row) => {
      if (!inMarket(row)) return false;
      const code = symbolSummaryRowCode(row).toUpperCase();
      const raw = String(row?.symbol || "").toUpperCase();
      return code === sym || raw === sym;
    });
    const exactHit = pickBest(exact);
    if (exactHit) return exactHit;

    const fuzzy = (catalog || []).filter((row) => inMarket(row) && catalogRowMatchesQuery(row, sym));
    const fuzzyHit = pickBest(fuzzy);
    if (fuzzyHit) return fuzzyHit;

    const futuresCode = futuresCodeFromAlias(sym);
    if (futuresCode && futuresCode !== sym) {
      return lookupSymbolCatalogRow(catalog, futuresCode, marketHint || "FUTURES");
    }
    return null;
  }

  function resolveWatchEntryInput(catalog, rawInput, marketFilter) {
    const text = String(rawInput || "").trim();
    if (!text) return null;
    let sym = text.toUpperCase();
    if (/^\d+$/.test(sym) && sym.length < 6) sym = sym.padStart(6, "0");
    const filter = String(marketFilter || "").toUpperCase();
    const marketHint = filter && filter !== "ALL" ? filter : null;
    const futuresAlias = futuresCodeFromAlias(sym);
    if (futuresAlias && (!marketHint || marketHint === "FUTURES")) {
      const futRow = lookupSymbolCatalogRow(catalog, sym, "FUTURES")
        || lookupSymbolCatalogRow(catalog, futuresAlias, "FUTURES");
      if (futRow) return catalogRowToWatchEntry(futRow);
    }
    const row = lookupSymbolCatalogRow(catalog, sym, marketHint);
    if (row) return catalogRowToWatchEntry(row);
    const crossFutures = futuresCodeFromAlias(sym);
    if (crossFutures) {
      const futRow = lookupSymbolCatalogRow(catalog, crossFutures, "FUTURES");
      if (futRow) return catalogRowToWatchEntry(futRow);
      return {
        symbol: crossFutures,
        market: "FUTURES",
        name: futuresCnName(crossFutures) || sym,
      };
    }
    const staticEntry = catalogEntry(sym);
    if (staticEntry) {
      return {
        symbol: String(staticEntry.symbol || sym).toUpperCase(),
        market: String(staticEntry.market || "").toUpperCase(),
        name: String(staticEntry.name || "").trim(),
      };
    }
    const futuresCode = futuresCodeFromAlias(sym);
    if (futuresCode && (!marketHint || marketHint === "FUTURES")) {
      const aliasRow = lookupSymbolCatalogRow(catalog, futuresCode, "FUTURES")
        || lookupSymbolCatalogRow(catalog, sym, "FUTURES");
      if (aliasRow) return catalogRowToWatchEntry(aliasRow);
      return {
        symbol: futuresCode,
        market: "FUTURES",
        name: futuresCnName(futuresCode) || "",
      };
    }
    if (/^\d{6}$/.test(sym)) return { symbol: sym, market: "A_STOCK", name: "" };
    if (sym.endsWith("USDT")) return { symbol: sym, market: "CRYPTO", name: "" };
    if (marketHint && marketHint !== "ALL") {
      return { symbol: sym, market: marketHint, name: "" };
    }
    return { symbol: sym, market: "FUTURES", name: "" };
  }

  async function fetchAllSymbolSummary(limit = 500) {
    const markets = (CFG.MARKETS || []).map((item) => item.id);
    const batches = await Promise.all(markets.map((market) => fetchSymbolSummary(market, limit)));
    const seen = new Set();
    const out = [];
    for (const rows of batches) {
      for (const row of rows || []) {
        const key = `${String(row.market || "").toUpperCase()}|${String(row.symbol || "").toUpperCase()}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(row);
      }
    }
    return out.sort((a, b) => {
      const ma = marketLabel(a.market);
      const mb = marketLabel(b.market);
      const cmp = ma.localeCompare(mb, "zh-CN");
      if (cmp !== 0) return cmp;
      return symbolSummaryRowLabel(a).localeCompare(symbolSummaryRowLabel(b), "zh-CN");
    });
  }

  /** When market=ALL, avoid zh sort + slice leaving only A-share in the first page. */
  function sliceCatalogRows(rows, limit, marketFilter, hasSearchQuery = false) {
    const list = rows || [];
    if (!list.length) return [];
    if (hasSearchQuery) return list.slice(0, limit);
    const mkt = String(marketFilter || "").toUpperCase();
    if (mkt && mkt !== "ALL") return list.slice(0, limit);

    const buckets = new Map();
    for (const row of list) {
      const key = String(row.market || "").toUpperCase();
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(row);
    }
    const markets = [...buckets.keys()].sort((a, b) =>
      marketLabel(a).localeCompare(marketLabel(b), "zh-CN"),
    );
    const perMarket = Math.max(20, Math.ceil(limit / Math.max(markets.length, 1)));
    const merged = [];
    for (const key of markets) {
      merged.push(...buckets.get(key).slice(0, perMarket));
    }
    return merged.slice(0, limit);
  }

  function formatPct(v, digits = 1) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "—";
    return `${(n * 100).toFixed(digits)}%`;
  }

  function formatNum(v, digits = 2) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "—";
    return n.toFixed(digits);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function tierClass(tier) {
    if (!tier || tier === "INSUFFICIENT_DATA") return "tier-INSUFFICIENT_DATA";
    return `tier-${tier}`;
  }

  function marketLabel(market) {
    const item = (CFG.MARKETS || []).find((m) => m.id === market);
    return item ? item.label : market || "—";
  }

  function getSubscriptionPlan() {
    const session = getAuthSession();
    const token = getAccessToken();
    const authPlan = session?.user?.plan;
    if (token && authPlan && CFG.SUBSCRIPTION_PLANS?.[authPlan]) {
      return authPlan;
    }
    if (token) {
      return CFG.DEFAULT_SUBSCRIPTION_PLAN || "free";
    }
    const raw = localStorage.getItem("fj-plan") || CFG.DEFAULT_SUBSCRIPTION_PLAN || "free";
    return CFG.SUBSCRIPTION_PLANS?.[raw] ? raw : "free";
  }

  function formatFeatureGateError(detail) {
    const msg = String(detail || "");
    const yearMatch = msg.match(/plan '([^']+)' does not allow (\d+)-year backtest/);
    if (yearMatch) {
      const planKey = yearMatch[1];
      const yrs = yearMatch[2];
      const label = CFG.SUBSCRIPTION_PLANS?.[planKey]?.label || planKey;
      const allowed = (CFG.SUBSCRIPTION_PLANS?.[planKey]?.years || [1]).join("/");
      const loginHint = getAccessToken()
        ? "请确认当前登录账号已开通对应档位，或切换回测年限。"
        : "请先登录并在付款页完成「我已完成付款」确认，勿仅依赖本地演示档位。";
      return `服务端识别为「${label}」：不支持 ${yrs} 年回测（该档仅 ${allowed} 年）。${loginHint}`;
    }
    const stratMatch = msg.match(/plan '([^']+)' does not allow strategy '([^']+)'/);
    if (stratMatch) {
      const planKey = stratMatch[1];
      const sid = stratMatch[2];
      const label = CFG.SUBSCRIPTION_PLANS?.[planKey]?.label || planKey;
      return sid === "TOTAL"
        ? `服务端识别为「${label}」：峰极总定式 TOTAL 仅专业档可用。请升级专业档并用该账号登录。`
        : `服务端识别为「${label}」：不可用定式 ${sid}。请切换定式或升级订阅。`;
    }
    if (/subscription expired/i.test(msg)) {
      return "当前账号订阅或免费试用已到期，请前往定价页升级后重新登录。";
    }
    if (/login required/i.test(msg)) {
      return "提交自选品种回测须先登录；服务端不再接受本地演示档位或伪造 plan。";
    }
    return msg;
  }

  /** 移除 URL 中的 ?plan=，防止通过链接伪造档位 */
  function stripPlanQueryFromUrl() {
    try {
      const u = new URL(window.location.href);
      if (!u.searchParams.has("plan")) return;
      u.searchParams.delete("plan");
      const qs = u.searchParams.toString();
      history.replaceState(null, "", u.pathname + (qs ? `?${qs}` : "") + u.hash);
    } catch {
      /* noop */
    }
  }

  function getPlanFlow(planId) {
    return CFG.PLAN_FLOW?.[planId] || null;
  }

  function getPlanHomeHref(planId) {
    const flow = getPlanFlow(planId);
    return flow?.homeFeature || flow?.afterPayment || flow?.afterRegister || "index.html";
  }

  function getSubscriptionConfig() {
    return CFG.SUBSCRIPTION_PLANS[getSubscriptionPlan()];
  }

  function watchlistSymbolKeys(items) {
    return (items || [])
      .map((item) => {
        if (item && typeof item === "object") return String(item.symbol || "").toUpperCase();
        return String(item || "").toUpperCase();
      })
      .filter(Boolean);
  }

  function ensureSymbolInQuota(symbol, market) {
    const cfg = getSubscriptionConfig();
    const sym = String(symbol || "").toUpperCase();
    if (!sym) return { ok: false, message: "请选择品种" };

    const list = loadWatchlist();
    const keys = watchlistSymbolKeys(list);
    if (keys.includes(sym)) return { ok: true };

    const max = cfg.maxWatchlist || 0;
    if (max > 0 && keys.length >= max) {
      return {
        ok: false,
        message: `${cfg.label}档最多 ${max} 个品种（${keys.join("、")}），请先在模拟监测页移除后再选新品种`,
      };
    }

    const entry =
      catalogEntry(sym) ||
      (CFG.MONITOR_CATALOG || []).find((row) => String(row.symbol).toUpperCase() === sym) || {
        symbol: sym,
        market: market || "",
        name: "",
      };
    list.push(entry);
    saveWatchlist(list);
    return { ok: true, added: true };
  }

  function symbolQuotaHint() {
    const cfg = getSubscriptionConfig();
    const max = cfg.maxWatchlist || 0;
    if (!max) return "";
    const n = watchlistSymbolKeys(loadWatchlist()).length;
    return `已选 ${n}/${max} 品种`;
  }

  function isSymbolInWatchlist(symbol) {
    const sym = String(symbol || "").toUpperCase();
    return watchlistSymbolKeys(loadWatchlist()).includes(sym);
  }

  function isStrategyAllowed(strategyId) {
    const cfg = getSubscriptionConfig();
    return (cfg.strategies || []).includes(String(strategyId || "").toUpperCase());
  }

  function isYearAllowed(years) {
    const cfg = getSubscriptionConfig();
    return (cfg.years || []).includes(Number(years));
  }

  function isPlanActive() {
    const session = getAuthSession();
    const token = getAccessToken();
    const expiresAt = session?.user?.plan_expires_at;
    if (token && expiresAt) {
      const expiresMs = new Date(expiresAt).getTime();
      if (!Number.isNaN(expiresMs)) {
        return Date.now() < expiresMs;
      }
    }
    const cfg = getSubscriptionConfig();
    if (!cfg.trialDays) return true;
    const start = localStorage.getItem("fj-trial-start");
    if (!start) return true;
    const elapsed = Date.now() - new Date(start).getTime();
    return elapsed < cfg.trialDays * 86400000;
  }

  function planGateMessage() {
    if (isPlanActive()) return "";
    const token = getAccessToken();
    if (token) {
      return "当前账号订阅或免费试用已到期，请升级标准档或专业档后继续使用。";
    }
    return "免费试用已结束，请升级标准档或专业档后继续使用。";
  }

  function strategyDisplayName(strategyId) {
    const meta = CFG.STRATEGY_META?.[strategyId] || {};
    const alias = meta.alias || "";
    return alias ? `${strategyId} · ${alias}` : strategyId;
  }

  function backtestUrl(market, symbol, strategy) {
    const p = new URLSearchParams({ market, symbol });
    if (strategy) p.set("strategy", strategy);
    return `backtest.html?${p}`;
  }

  function normalizeStrategyId(strategyId) {
    const sid = String(strategyId || "").trim().toUpperCase();
    if (!sid) return "";
    if (sid === "TOTAL") return "TOTAL";
    const match = sid.match(/^DS(\d{1,2})$/);
    return match ? `DS${match[1].padStart(2, "0")}` : sid;
  }

  /** W15 · 策略学堂深链（可选 open=1 自动弹层） */
  function strategyAnimPageUrl(strategyId, { open = true } = {}) {
    const sid = normalizeStrategyId(strategyId);
    if (!sid) return "strategies.html";
    const p = new URLSearchParams({ strategy: sid });
    if (open) p.set("open", "1");
    return `strategies.html?${p.toString()}`;
  }

  function strategyAnimLinkHtml(strategyId, label, { open = true, className = "strategy-anim-link" } = {}) {
    const sid = normalizeStrategyId(strategyId);
    if (!sid || !isStrategyAllowed(sid)) return escapeHtml(label || sid || "—");
    const text = escapeHtml(label || `${sid} 动画`);
    return `<a class="${escapeHtml(className)}" href="${escapeHtml(strategyAnimPageUrl(sid, { open }))}">${text}</a>`;
  }

  /** O2 · 定式帮助深链（默认 open=1 弹层预览） */
  function strategyHelpLinkHtml(strategyId, { label = "", open = true, className = "strategy-help-link strategy-anim-link" } = {}) {
    const sid = normalizeStrategyId(strategyId);
    if (!sid || !isStrategyAllowed(sid)) return escapeHtml(label || sid || "—");
    const text = label || `${sid} 定式帮助`;
    return strategyAnimLinkHtml(sid, text, { open, className });
  }

  function signalStrengthUrl(tradeId) {
    return `${CFG.API_BASE}/api/v1/signals/${encodeURIComponent(tradeId)}/strength`;
  }

  async function fetchSignalStrength(tradeId) {
    if (!tradeId) throw new Error("missing trade_id");
    const res = await fetch(signalStrengthUrl(tradeId));
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `signal strength failed: ${res.status}`);
    }
    return await res.json();
  }

  async function fetchBucketTrades({ strategyId, market, bucketKey, symbol, limit = 20 }) {
    const q = new URLSearchParams({
      strategy_id: strategyId,
      market,
      bucket_key: bucketKey,
      limit: String(limit),
    });
    if (symbol) q.set("symbol", symbol);
    const res = await fetch(`${CFG.API_BASE}/api/v1/context-stats/bucket-trades?${q}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `bucket trades failed: ${res.status}`);
    }
    return await res.json();
  }

  function authHeaders(extra = {}) {
    const headers = { ...extra };
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  async function submitBacktestJob({ market, symbol, strategyId, years }) {
    const payload = {
      market,
      symbol,
      strategy_id: strategyId,
      years: Number(years),
      user_id: getCurrentUser() || null,
    };
    const res = await fetch(`${CFG.API_BASE}/api/v1/backtests`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(formatFeatureGateError(err.detail) || `backtest submit failed: ${res.status}`);
    }
    return await res.json();
  }

  async function fetchBacktestJob(jobId) {
    if (!jobId) throw new Error("missing backtest job id");
    const res = await fetch(`${CFG.API_BASE}/api/v1/backtests/${encodeURIComponent(jobId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `backtest job failed: ${res.status}`);
    }
    return await res.json();
  }

  async function submitCustomInstrumentRequest({ market, symbol, strategies, years, enablePaper = false }) {
    const res = await fetch(`${CFG.API_BASE}/api/v1/custom-instruments/request`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        market,
        symbol,
        strategies: strategies && strategies.length ? strategies : ["TOTAL"],
        years: Number(years),
        enable_paper: Boolean(enablePaper),
        user_id: getCurrentUser() || null,
        plan_id: getSubscriptionPlan(),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `custom instrument request failed: ${res.status}`);
    }
    return await res.json();
  }

  async function fetchCustomInstrumentRequest(requestId) {
    if (!requestId) throw new Error("missing custom instrument request id");
    const res = await fetch(`${CFG.API_BASE}/api/v1/custom-instruments/requests/${encodeURIComponent(requestId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `custom instrument status failed: ${res.status}`);
    }
    return await res.json();
  }

  async function fetchPaperWatchlistRuntime({
    status = "pending_runtime",
    limit = 100,
    includeSignalPreview = false,
    preferRuntimeCache = false,
  } = {}) {
    const userId = getCurrentUser();
    if (!userId) return { count: 0, items: [] };
    const q = new URLSearchParams({
      user_id: userId,
      status,
      limit: String(limit),
      include_signal_preview: includeSignalPreview ? "true" : "false",
      prefer_runtime_cache: preferRuntimeCache ? "true" : "false",
    });
    const res = await fetch(`${CFG.API_BASE}/api/v1/paper-watchlist/runtime?${q}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `paper watchlist runtime failed: ${res.status}`);
    }
    return await res.json();
  }

  function getAuthSession() {
    try {
      return JSON.parse(localStorage.getItem("fj-auth") || "null");
    } catch {
      return null;
    }
  }

  function setAuthSession(payload) {
    if (!payload || !payload.user) return;
    localStorage.setItem("fj-auth", JSON.stringify(payload));
    localStorage.setItem("fj-access-token", payload.access_token || "");
    localStorage.setItem("fj-user", payload.user.account || "");
    if (payload.user.plan && CFG.SUBSCRIPTION_PLANS?.[payload.user.plan]) {
      localStorage.setItem("fj-plan", payload.user.plan);
    }
  }

  function getAccessToken() {
    return (localStorage.getItem("fj-access-token") || "").trim();
  }

  async function refreshAuthSessionFromApi() {
    const token = getAccessToken();
    if (!token) return null;
    try {
      const res = await fetch(`${CFG.API_BASE}/api/v1/auth/me`, {
        headers: authHeaders(),
      });
      if (!res.ok) {
        if (res.status === 401) {
          clearAuthSession();
        }
        return null;
      }
      const me = await res.json();
      const prev = getAuthSession() || {};
      const merged = {
        ...prev,
        access_token: token,
        refresh_token: prev.refresh_token || "",
        user: { ...(prev.user || {}), ...me },
      };
      setAuthSession(merged);
      if (me.account) {
        localStorage.setItem("fj-user", me.account);
      }
      renderNavAuth();
      return me;
    } catch {
      return null;
    }
  }

  async function authRegister(account, password) {
    const res = await fetch(`${CFG.API_BASE}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `register failed: ${res.status}`);
    }
    const payload = await res.json();
    setAuthSession(payload);
    renderNavAuth();
    return payload;
  }

  async function authLogin(account, password) {
    const res = await fetch(`${CFG.API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `login failed: ${res.status}`);
    }
    const payload = await res.json();
    setAuthSession(payload);
    renderNavAuth();
    return payload;
  }

  function monitorWebSocketUrl({
    userId = getCurrentUser(),
    plan = getSubscriptionPlan(),
    intervalSeconds,
    includeSignalPreview = true,
    preferRuntimeCache = true,
    channels = "positions,runtime,quotes",
  } = {}) {
    const base = new URL(CFG.API_BASE || window.location.origin, window.location.href);
    const rootPath = base.pathname.replace(/\/$/, "");
    base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
    base.pathname = `${rootPath}/api/v1/ws/monitor`;
    base.search = "";
    const q = base.searchParams;
    const token = getAccessToken();
    if (token) {
      q.set("access_token", token);
    } else {
      if (userId) q.set("user_id", userId);
      q.set("plan", plan || "free");
    }
    q.set("status", "pending_runtime");
    q.set("limit", "100");
    q.set("include_signal_preview", includeSignalPreview ? "true" : "false");
    q.set("prefer_runtime_cache", preferRuntimeCache ? "true" : "false");
    if (channels) q.set("channels", String(channels));
    if (intervalSeconds) q.set("interval_seconds", String(intervalSeconds));
    return base.toString();
  }

  async function updatePaperWatchlistStatus(watchlistId, status) {
    const userId = getCurrentUser();
    if (!userId) throw new Error("missing current user");
    if (!watchlistId) throw new Error("missing paper watchlist id");
    const res = await fetch(`${CFG.API_BASE}/api/v1/paper-watchlist/${encodeURIComponent(watchlistId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, status }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `paper watchlist update failed: ${res.status}`);
    }
    return await res.json();
  }

  function getMonitorCatalog() {
    return CFG.MONITOR_CATALOG || [];
  }

  function catalogEntry(symbol) {
    const sym = String(symbol || "").trim().toUpperCase();
    if (!sym) return null;
    return (CFG.MONITOR_CATALOG || []).find((row) => String(row.symbol || "").toUpperCase() === sym) || null;
  }

  function watchlistStorageKey() {
    return `fj-watchlist-${getSubscriptionPlan()}`;
  }

  function loadWatchlist() {
    try {
      const raw = localStorage.getItem(watchlistStorageKey());
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function saveWatchlist(items) {
    localStorage.setItem(watchlistStorageKey(), JSON.stringify(items));
  }

  function findWatchlistEntry(symbol) {
    const sym = String(symbol || "").toUpperCase();
    return loadWatchlist().find((item) => {
      const key =
        item && typeof item === "object" ? String(item.symbol || "").toUpperCase() : String(item || "").toUpperCase();
      return key === sym;
    }) || null;
  }

  function symbolPageUrl(symbol, market) {
    const p = new URLSearchParams({ symbol: String(symbol || ""), market: String(market || "FUTURES") });
    return `symbol.html?${p}`;
  }

  function monitorRefreshMs() {
    if (monitorPollIntervalMs && monitorPollIntervalMs > 0) {
      return monitorPollIntervalMs;
    }
    const delay = getSubscriptionConfig().monitorDelay || "";
    if (String(delay).includes("15")) return 15 * 60 * 1000;
    if (String(delay).includes("1 分钟")) return 60 * 1000;
    return 30 * 1000;
  }

  let monitorPollIntervalMs = null;

  function applyMonitorPolicyFromPayload(data) {
    const sec = Number(data?.monitor_policy?.min_interval_seconds || 0);
    if (sec > 0) {
      monitorPollIntervalMs = sec * 1000;
    }
  }

  async function monitorPollFetch(url, options = {}) {
    const headers = {
      ...(options.headers || {}),
      ...authHeaders(),
    };
    const res = await fetch(url, { ...options, headers });
    if (res.status === 429) {
      const retry = Number(res.headers.get("Retry-After") || 0);
      return { res, data: null, throttled: true, retryAfterSeconds: retry };
    }
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (data) applyMonitorPolicyFromPayload(data);
    return { res, data, throttled: false, retryAfterSeconds: 0 };
  }

  function defaultMonitorStrategy() {
    const cfg = getSubscriptionConfig();
    const list = cfg.strategies || [];
    if (list.includes("TOTAL")) return "TOTAL";
    return list[0] || "DS01";
  }

  function getCurrentUser() {
    return (localStorage.getItem("fj-user") || "").trim();
  }

  function isPaidPlan(planId) {
    return planId === "standard" || planId === "pro";
  }

  function setSubscriptionPlan(planId) {
    if (!CFG.SUBSCRIPTION_PLANS?.[planId]) return { ok: false, reason: "unknown_plan" };
    const current = getSubscriptionPlan();
    if (current === "pro" && planId === "standard") {
      return { ok: false, reason: "no_downgrade", message: "当前为专业档，不可降为标准档。" };
    }
    localStorage.setItem("fj-plan", planId);
    if (planId === "free") {
      if (!localStorage.getItem("fj-trial-start")) {
        localStorage.setItem("fj-trial-start", new Date().toISOString());
      }
      localStorage.removeItem("fj-paid-at");
    } else {
      localStorage.removeItem("fj-trial-start");
      localStorage.setItem("fj-paid-at", new Date().toISOString());
    }
    return { ok: true, planId };
  }

  function paymentSuccessRoute(planId) {
    return CFG.PAYMENT_SUCCESS_ROUTES?.[planId] || null;
  }

  function communityPayUrl(planId) {
    if (!isPaidPlan(planId)) return "community.html";
    return `payment.html?pay=${encodeURIComponent(planId)}`;
  }

  const LOCAL_PAGE_ALLOWLIST = new Set([
    "index.html",
    "backtest.html",
    "monitor.html",
    "strategies.html",
    "pricing.html",
    "community.html",
    "payment.html",
    "login.html",
    "admin.html",
    "symbol.html",
  ]);

  function decodeMaybeEncoded(value) {
    let s = String(value || "").trim();
    for (let i = 0; i < 2; i += 1) {
      try {
        const next = decodeURIComponent(s);
        if (next === s) break;
        s = next;
      } catch {
        break;
      }
    }
    return s;
  }

  function normalizeLocalPagePath(value, fallback = "") {
    const raw = decodeMaybeEncoded(value);
    if (!raw || raw.startsWith("//") || raw.startsWith("\\") || /^[a-z][a-z0-9+.-]*:/i.test(raw)) {
      return fallback;
    }
    try {
      const url = new URL(raw, window.location.href);
      if (url.origin !== window.location.origin) return fallback;
      const page = (url.pathname.split("/").pop() || "").toLowerCase();
      if (!LOCAL_PAGE_ALLOWLIST.has(page)) return fallback;
      return `${page}${url.search}${url.hash}`;
    } catch {
      return fallback;
    }
  }

  function loginUrlWithReturn(returnPath, { mode } = {}) {
    const p = new URLSearchParams();
    if (mode) p.set("mode", mode);
    const safeReturn = normalizeLocalPagePath(returnPath);
    if (safeReturn) p.set("return", safeReturn);
    return `login.html?${p}`;
  }

  function resolveCommunityPayPlan() {
    const pay = new URLSearchParams(window.location.search).get("pay");
    return isPaidPlan(pay) ? pay : "";
  }

  /**
   * 校验订阅扫码意图，三档互不串路。
   * @returns {{ state: string, message: string, payPlan?: string, landingHref?: string }}
   */
  function validatePayIntent(requestedPlan) {
    if (!isPaidPlan(requestedPlan)) {
      return {
        state: "invalid",
        message: "无效的订阅链接。请从订阅页选择标准档或专业档。",
        landingHref: "pricing.html",
      };
    }
    const current = getSubscriptionPlan();
    const landing = getPlanHomeHref(requestedPlan);
    const flow = getPlanFlow(requestedPlan);
    const label = CFG.SUBSCRIPTION_PLANS[requestedPlan]?.label || requestedPlan;

    if (current === requestedPlan) {
      return {
        state: "already_active",
        message: `您当前已是${label}，无需重复付款。`,
        payPlan: requestedPlan,
        landingHref: landing,
      };
    }
    if (current === "pro" && requestedPlan === "standard") {
      return {
        state: "blocked_downgrade",
        message: "您已是专业档，标准档订阅入口不适用。请直接使用专业档功能页。",
        landingHref: getPlanHomeHref("pro"),
      };
    }
    if (current === "standard" && requestedPlan === "pro") {
      return {
        state: "upgrade",
        message: `升级至${label}：付款后将覆盖标准档权限，并进入专业档专属回测页。`,
        payPlan: requestedPlan,
        landingHref: getPlanFlow("pro")?.afterPayment,
      };
    }
    if (current === "free") {
      return {
        state: "checkout",
        message: `订阅${label}：付款后将开通${flow?.label || label}，并进入${requestedPlan === "standard" ? "模拟监测" : "历史回测"}。`,
        payPlan: requestedPlan,
        landingHref: landing,
      };
    }
    return {
      state: "checkout",
      message: `订阅${label}：请完成微信扫码付款。`,
      payPlan: requestedPlan,
      landingHref: landing,
    };
  }

  function confirmPaidSubscription(requestedPlan) {
    const check = validatePayIntent(requestedPlan);
    if (check.state === "blocked_downgrade" || check.state === "invalid") {
      return Promise.resolve({ ok: false, ...check });
    }
    if (check.state === "already_active") {
      return Promise.resolve({ ok: false, ...check });
    }
    const token = getAccessToken();
    if (token) {
      return fetchSubscriptionPaymentConfig()
        .then((payConfig) => {
          const mode = payConfig?.confirm_button_mode || "demo_only";
          if (mode === "webhook_pending") {
            return {
              ok: false,
              state: "pending_webhook",
              message: payConfig?.message || "付款后请等待系统自动开通，无需点击确认。",
            };
          }
          if (mode === "redeem_only") {
            return {
              ok: false,
              state: "redeem_only",
              message: payConfig?.message || "当前仅支持兑换码开通。",
            };
          }
          if (mode === "demo_only") {
            return {
              ok: false,
              state: "error",
              message: payConfig?.message || "支付通道未配置，请联系管理员。",
            };
          }
          return fetch(`${CFG.API_BASE}/api/v1/subscriptions/manual-confirm`, {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ plan: requestedPlan }),
          });
        })
        .then(async (resOrResult) => {
          // Distinguish fetch Response (has .json) from inline { ok, message } results.
          if (resOrResult && typeof resOrResult.json === "function" && typeof resOrResult.status === "number") {
            const res = resOrResult;
            if (res.ok) {
              const payload = await res.json();
              setAuthSession(payload);
              const route = paymentSuccessRoute(requestedPlan);
              return {
                ok: true,
                state: check.state === "upgrade" ? "upgrade" : "paid",
                message: route?.hint || "订阅已开通。",
                landingHref: route?.href || getPlanHomeHref(requestedPlan),
                label: route?.label,
              };
            }
            const err = await res.json().catch(() => ({}));
            if (res.status !== 503) {
              return {
                ok: false,
                state: "error",
                message: err.detail || `subscription failed: ${res.status}`,
              };
            }
            return null;
          }
          return resOrResult;
        })
        .catch(() => null)
        .then((serverResult) => {
          if (serverResult) return serverResult;
          if (getAccessToken()) {
            return {
              ok: false,
              state: "error",
              message: "服务端未确认订阅，请稍后重试；若已付款请重新登录后再点「我已完成付款」。",
            };
          }
          return confirmPaidSubscriptionDemo(requestedPlan, check);
        });
    }
    return Promise.resolve(confirmPaidSubscriptionDemo(requestedPlan, check));
  }

  function confirmPaidSubscriptionDemo(requestedPlan, check) {
    const applied = setSubscriptionPlan(requestedPlan);
    if (!applied.ok) {
      return { ok: false, state: "error", message: applied.message || "无法更新订阅档位。" };
    }
    const route = paymentSuccessRoute(requestedPlan);
    return {
      ok: true,
      state: check.state === "upgrade" ? "upgrade" : "paid",
      message: route?.hint || "界面已切换（未登录演示模式：回测仍按免费档，登录并完成付款后才生效）。",
      landingHref: route?.href || getPlanHomeHref(requestedPlan),
      label: route?.label,
    };
  }

  let _paymentConfigCache = null;

  async function fetchSubscriptionPaymentConfig({ force = false } = {}) {
    if (!force && _paymentConfigCache) return _paymentConfigCache;
    try {
      const res = await fetch(`${CFG.API_BASE}/api/v1/subscriptions/payment-config`);
      if (!res.ok) return null;
      _paymentConfigCache = await res.json();
      return _paymentConfigCache;
    } catch {
      return null;
    }
  }

  async function redeemSubscriptionCode(code) {
    const res = await fetch(`${CFG.API_BASE}/api/v1/subscriptions/redeem`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ code: String(code || "").trim() }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `redeem failed: ${res.status}`);
    }
    const payload = await res.json();
    setAuthSession(payload);
    return payload;
  }

  function registerFreeTrial(account) {
    localStorage.setItem("fj-user", account.trim());
    setSubscriptionPlan("free");
    return getPlanFlow("free")?.afterRegister || "backtest.html";
  }

  window.FengJiApp = {
    CFG,
    initShell,
    fetchStrategies,
    fetchSymbolSummary,
    fetchAllSymbolSummary,
    symbolSummaryRowCode,
    symbolSummaryRowLabel,
    catalogDisplayLabel,
    catalogRowToWatchEntry,
    sliceCatalogRows,
    catalogRowMatchesQuery,
    sortCatalogRowsByQuery,
    resolveWatchEntryInput,
    validateSymbolMarketPair,
    lookupSymbolCatalogRow,
    fetchSignalStrength,
    fetchBucketTrades,
    submitBacktestJob,
    fetchBacktestJob,
    submitCustomInstrumentRequest,
    fetchCustomInstrumentRequest,
    fetchPaperWatchlistRuntime,
    monitorWebSocketUrl,
    updatePaperWatchlistStatus,
    authRegister,
    authLogin,
    authLogout,
    clearAuthSession,
    renderNavAuth,
    getAccessToken,
    getAuthSession,
    setAuthSession,
    refreshAuthSessionFromApi,
    authHeaders,
    formatPct,
    formatNum,
    escapeHtml,
    marketLabel,
    getSubscriptionPlan,
    getSubscriptionConfig,
    formatFeatureGateError,
    stripPlanQueryFromUrl,
    getPlanFlow,
    getPlanHomeHref,
    watchlistSymbolKeys,
    ensureSymbolInQuota,
    symbolQuotaHint,
    isSymbolInWatchlist,
    findWatchlistEntry,
    symbolPageUrl,
    monitorRefreshMs,
    monitorPollFetch,
    applyMonitorPolicyFromPayload,
    defaultMonitorStrategy,
    getCurrentUser,
    isPaidPlan,
    setSubscriptionPlan,
    paymentSuccessRoute,
    communityPayUrl,
    normalizeLocalPagePath,
    loginUrlWithReturn,
    resolveCommunityPayPlan,
    validatePayIntent,
    fetchSubscriptionPaymentConfig,
    confirmPaidSubscription,
    redeemSubscriptionCode,
    registerFreeTrial,
    isStrategyAllowed,
    isYearAllowed,
    isPlanActive,
    planGateMessage,
    getMonitorCatalog,
    loadWatchlist,
    saveWatchlist,
    catalogEntry,
    strategyDisplayName,
    normalizeStrategyId,
    strategyAnimPageUrl,
    strategyAnimLinkHtml,
    strategyHelpLinkHtml,
    signalStrengthUrl,
    tierClass,
    backtestUrl,
    setTheme,
    getTheme,
  };
})();
