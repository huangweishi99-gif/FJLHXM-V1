/** W15 · 定式示意动画（Lottie 优先 + SVG/CSS 回退，约 10s 循环） */
(function (global) {
  const cfg = global.FengJiConfig?.STRATEGY_ANIM || {};
  const lottieCfg = cfg.LOTTIE || {};
  const DURATION_SEC = cfg.DURATION_SEC || 10;
  const ENGINE_VERSION = cfg.ENGINE_VERSION || "fengji_core@0.1.0";

  const SCENES = {
    DS01: { caption: "N字突破 · 红启动棍" },
    DS02: { caption: "N突破 · 阴阳相吃" },
    DS03: { caption: "N突破 · 假峰" },
    DS04: { caption: "N突破 · 夹棍" },
    DS05: { caption: "N突破 · 指形" },
    DS06: { caption: "N突破 · 外扩峰" },
    DS07: { caption: "N突破 · 共振" },
    DS08: { caption: "N突破 · 五点确定" },
    DS09: { caption: "D1趋势 · M15攻击" },
    TOTAL: { caption: "总定式 · N突破合一" },
  };

  const EXTRA_MARKUP = {
    DS02: `
      <g class="anim-yinyang">
        <rect class="anim-yin" x="54" y="46" width="14" height="22" rx="2"/>
        <rect class="anim-yang" x="72" y="40" width="14" height="28" rx="2"/>
      </g>`,
    DS03: `<path class="anim-fake-peak" d="M72,38 L88,30" fill="none"/>`,
    DS04: `
      <g class="anim-clamp">
        <rect class="anim-clamp-k" x="68" y="42" width="6" height="20" rx="1"/>
        <rect class="anim-clamp-k anim-clamp-k2" x="78" y="36" width="6" height="26" rx="1"/>
        <rect class="anim-clamp-k" x="88" y="42" width="6" height="20" rx="1"/>
      </g>`,
    DS05: `<line class="anim-finger" x1="78" y1="24" x2="78" y2="48"/>`,
    DS06: `<path class="anim-expand-peak" d="M72,50 Q88,18 104,50" fill="none"/>`,
    DS07: `
      <g class="anim-resonance">
        <path class="anim-res-line" d="M20,62 L70,38" fill="none"/>
        <path class="anim-res-line anim-res-line-b" d="M90,38 L140,62" fill="none"/>
      </g>`,
    DS08: `
      <g class="anim-five-point">
        <circle class="anim-pt" cx="24" cy="58" r="2.5"/>
        <circle class="anim-pt" cx="48" cy="42" r="2.5"/>
        <circle class="anim-pt" cx="72" cy="54" r="2.5"/>
        <circle class="anim-pt" cx="96" cy="36" r="2.5"/>
        <circle class="anim-pt anim-pt-confirm" cx="120" cy="48" r="2.5"/>
      </g>`,
    DS09: `
      <g class="anim-nine-heaven">
        <path class="anim-d1-line" d="M8,68 L152,36" fill="none"/>
        <circle class="anim-m15-burst" cx="54" cy="28" r="8"/>
      </g>`,
    TOTAL: `
      <g class="anim-total">
        <circle class="anim-total-ring" cx="80" cy="44" r="22" fill="none"/>
        <text class="anim-total-label" x="80" y="48" text-anchor="middle">TOTAL</text>
      </g>`,
  };

  let lottieScriptPromise = null;

  function normalizeId(strategyId) {
    return String(strategyId || "DS01").toUpperCase();
  }

  function lottieMode() {
    return String(lottieCfg.MODE || "auto").toLowerCase();
  }

  function lottieEnabled() {
    return lottieCfg.ENABLED !== false && lottieMode() !== "svg_only";
  }

  function lottieAssetPath(strategyId) {
    const id = normalizeId(strategyId);
    const sources = lottieCfg.SOURCES || {};
    const file = sources[id];
    if (!file) return "";
    const base = String(lottieCfg.BASE_PATH || "assets/lottie").replace(/\/$/, "");
    return `${base}/${file}`;
  }

  function resolveAssetUrl(relativePath) {
    if (!relativePath) return "";
    if (/^https?:\/\//i.test(relativePath)) return relativePath;
    return new URL(relativePath, global.location.href).href;
  }

  function ensureLottieScript() {
    if (global.lottie) return Promise.resolve(global.lottie);
    if (lottieScriptPromise) return lottieScriptPromise;
    const src = lottieCfg.CDN || "https://unpkg.com/lottie-web@5.12.2/build/player/lottie.min.js";
    lottieScriptPromise = new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-fj-lottie="1"]');
      if (existing) {
        existing.addEventListener("load", () => resolve(global.lottie));
        existing.addEventListener("error", reject);
        if (global.lottie) resolve(global.lottie);
        return;
      }
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.dataset.fjLottie = "1";
      script.onload = () => resolve(global.lottie);
      script.onerror = () => reject(new Error("lottie-web load failed"));
      document.head.appendChild(script);
    });
    return lottieScriptPromise;
  }

  function destroyStage(container) {
    if (!container) return;
    if (container._lottieAnim) {
      container._lottieAnim.destroy();
      container._lottieAnim = null;
    }
    delete container.dataset.animKind;
  }

  function buildSvg(strategyId, options) {
    const opts = options || {};
    const id = normalizeId(strategyId);
    const slug = id.toLowerCase();
    const scene = SCENES[id] || SCENES.DS01;
    const paused = opts.paused ? " is-paused" : "";
    const large = opts.large ? " is-large" : "";
    const extra = EXTRA_MARKUP[id] || "";

    return `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 88" class="strategy-anim-svg strategy-anim-${slug}${paused}${large}" role="img" aria-label="${id} 定式示意动画">
  <rect class="anim-camp-bg" width="160" height="88" rx="8"/>
  <path class="anim-fengji-line" d="M14,28 L42,64 L54,28 L94,22" fill="none"/>
  ${extra}
  <line class="anim-trigger-line" x1="8" y1="28" x2="152" y2="28"/>
  <rect class="anim-stick" x="50" y="12" width="8" height="16" rx="1"/>
  <line class="anim-stop-line" x1="10" y1="72" x2="150" y2="72"/>
  <text class="anim-caption" x="80" y="82" text-anchor="middle">${scene.caption}</text>
</svg>`.trim();
  }

  function engineTagHtml(kind) {
    const label = kind === "lottie" ? `${ENGINE_VERSION} · Lottie` : ENGINE_VERSION;
    return `<span class="strategy-engine-tag" title="动画口径对应引擎版本">${label}</span>`;
  }

  function mountSvgStage(container, strategyId, options) {
    if (!container) return;
    destroyStage(container);
    container.innerHTML = buildSvg(strategyId, options) + engineTagHtml("svg");
    container.dataset.animKind = "svg";
  }

  async function lottieAssetAvailable(url) {
    try {
      const res = await fetch(url, { method: "GET", cache: "force-cache" });
      if (!res.ok) return false;
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("json")) return true;
      const text = await res.text();
      return text.trim().startsWith("{");
    } catch {
      return false;
    }
  }

  function lottieRenderHasShapes(holder) {
    const svg = holder?.querySelector("svg");
    if (!svg) return false;
    if (svg.querySelector("path, rect, circle, ellipse, line, polyline, polygon")) return true;
    const inner = svg.querySelector("g[clip-path] g, g g");
    return !!(inner && inner.children && inner.children.length > 0);
  }

  function waitForLottieRender(holder, anim, timeoutMs) {
    const ms = timeoutMs || 8000;
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (ok, err) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (ok) resolve();
        else reject(err || new Error("lottie render failed"));
      };
      const timer = setTimeout(() => finish(false, new Error("lottie render timeout")), ms);
      anim.addEventListener("DOMLoaded", () => {
        finish(lottieRenderHasShapes(holder), new Error("lottie empty render"));
      });
      anim.addEventListener("data_failed", () => finish(false, new Error("lottie data_failed")));
      anim.addEventListener("error", () => finish(false, new Error("lottie error")));
    });
  }

  async function mountLottieStage(container, strategyId, options) {
    const opts = options || {};
    const rel = lottieAssetPath(strategyId);
    const url = resolveAssetUrl(rel);
    if (!url) throw new Error("missing lottie source");
    await ensureLottieScript();
    if (!(await lottieAssetAvailable(url))) throw new Error("lottie asset unavailable");
    destroyStage(container);
    const holder = document.createElement("div");
    holder.className = "strategy-anim-lottie" + (opts.large ? " is-large" : "") + (opts.paused ? " is-paused" : "");
    holder.setAttribute("role", "img");
    holder.setAttribute("aria-label", `${normalizeId(strategyId)} 定式 Lottie 动画`);
    container.innerHTML = "";
    container.appendChild(holder);
    container.insertAdjacentHTML("beforeend", engineTagHtml("lottie"));
    const anim = global.lottie.loadAnimation({
      container: holder,
      renderer: "svg",
      loop: true,
      autoplay: !opts.paused,
      path: url,
    });
    container._lottieAnim = anim;
    container.dataset.animKind = "lottie";
    await waitForLottieRender(holder, anim, 8000);
  }

  async function mountStageAsync(container, strategyId, options) {
    if (!container) return;
    const mode = lottieMode();
    const tryLottie = lottieEnabled() && lottieAssetPath(strategyId);
    if (tryLottie) {
      try {
        await mountLottieStage(container, strategyId, options);
        return;
      } catch (err) {
        if (mode === "lottie_only") {
          destroyStage(container);
          container.innerHTML =
            `<p class="strategy-anim-miss">Lottie 资产不可用</p>${engineTagHtml("lottie")}`;
          container.dataset.animKind = "missing";
          return;
        }
      }
    }
    mountSvgStage(container, strategyId, options);
  }

  function mountStage(container, strategyId, options) {
    mountStageAsync(container, strategyId, options).catch(() => {
      mountSvgStage(container, strategyId, options || {});
    });
  }

  global.FengJiStrategyAnim = {
    DURATION_SEC,
    ENGINE_VERSION,
    SCENES,
    buildSvg,
    engineTagHtml,
    destroyStage,
    mountSvgStage,
    mountLottieStage,
    mountStage,
    mountStageAsync,
    lottieAssetPath,
  };
})(window);
