/** 峰极 Web · K 线 chart-bundle 渲染 */
window.FengJiChart = (function () {
  let chart = null;
  let candleSeries = null;
  let equityChart = null;
  let equitySeries = null;
  let clickHandler = null;
  let chartResizeHandler = null;
  let equityResizeHandler = null;
  let markerIndex = [];

  function escapeHtml(value) {
    if (window.FengJiApp?.escapeHtml) return window.FengJiApp.escapeHtml(value);
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeTimeKey(value) {
    if (value == null || value === "") return "";
    if (typeof value === "object" && value.year != null) {
      const y = value.year;
      const m = String(value.month).padStart(2, "0");
      const d = String(value.day).padStart(2, "0");
      return `${y}-${m}-${d}`;
    }
    const s = String(value);
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    if (/^\d+$/.test(s)) {
      const n = Number(s);
      const ms = n > 1e12 ? n : n * 1000;
      return new Date(ms).toISOString().slice(0, 10);
    }
    const parsed = Date.parse(s);
    if (!Number.isNaN(parsed)) return new Date(parsed).toISOString().slice(0, 10);
    return s.slice(0, 10);
  }

  function buildMarkerIndex(markers, trades) {
    const index = new Map();
    (markers || []).forEach((m) => {
      const day = normalizeTimeKey(m.t);
      if (!day) return;
      if (!index.has(day)) index.set(day, m);
    });
    (trades || []).forEach((t) => {
      const entryDay = normalizeTimeKey(t.entry_time);
      const exitDay = normalizeTimeKey(t.exit_time);
      if (entryDay && !index.has(entryDay)) index.set(entryDay, { t: entryDay, trade: t });
      if (exitDay && !index.has(exitDay)) index.set(exitDay, { t: exitDay, trade: t });
    });
    return index;
  }

  function findTradeAtTime(time, markers, trades) {
    const day = normalizeTimeKey(time);
    if (!day) return null;
    const marker = (markers || []).find((m) => normalizeTimeKey(m.t) === day);
    if (marker?.trade_no != null) {
      const byNo = (trades || []).find((t) => Number(t.trade_no) === Number(marker.trade_no));
      if (byNo) return byNo;
    }
    return (trades || []).find((t) => {
      return normalizeTimeKey(t.entry_time) === day || normalizeTimeKey(t.exit_time) === day;
    }) || null;
  }

  function isDark() {
    return document.documentElement.getAttribute("data-theme") === "dark";
  }

  function colors() {
    const dark = isDark();
    return {
      bg: dark ? "#000000" : "#f5f5f7",
      text: dark ? "#f5f5f7" : "#1d1d1f",
      grid: dark ? "#2c2c2e" : "#e8e8ed",
      border: dark ? "#38383a" : "#d2d2d7",
      up: "#34c759",
      down: "#ff3b30",
      line: "#007aff",
      equity: "#5eb0ff",
    };
  }

  function destroyChart(panel) {
    if (chart) {
      if (clickHandler) {
        try { chart.unsubscribeClick(clickHandler); } catch { /* noop */ }
        clickHandler = null;
      }
      chart.remove();
      chart = null;
      candleSeries = null;
    }
    if (chartResizeHandler) {
      window.removeEventListener("resize", chartResizeHandler);
      chartResizeHandler = null;
    }
    markerIndex = [];
    if (panel) {
      panel.querySelectorAll("canvas").forEach((c) => c.remove());
      panel.querySelectorAll(".loading-overlay, .empty-state").forEach((el) => el.remove());
    }
  }

  function destroyEquity(panel) {
    if (equityChart) {
      equityChart.remove();
      equityChart = null;
      equitySeries = null;
    }
    if (equityResizeHandler) {
      window.removeEventListener("resize", equityResizeHandler);
      equityResizeHandler = null;
    }
    if (panel) {
      panel.querySelectorAll("canvas").forEach((c) => c.remove());
      panel.querySelectorAll(".loading-overlay, .empty-state").forEach((el) => el.remove());
    }
  }

  function showMessage(panel, msg) {
    destroyChart(panel);
    const el = document.createElement("div");
    el.className = "empty-state";
    el.innerHTML = `<div class="icon">📊</div><p>${escapeHtml(msg)}</p>`;
    panel.appendChild(el);
  }

  function showEquityMessage(panel, msg) {
    destroyEquity(panel);
    const el = document.createElement("div");
    el.className = "empty-state compact";
    el.innerHTML = `<p>${escapeHtml(msg)}</p>`;
    panel.appendChild(el);
  }

  function initChart(panel) {
    destroyChart(panel);
    const c = colors();
    chart = LightweightCharts.createChart(panel, {
      layout: { background: { color: c.bg }, textColor: c.text },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, timeVisible: true, secondsVisible: false },
      handleScroll: { vertTouchDrag: true, horzTouchDrag: true },
      handleScale: { axisPressedMouseMove: true, pinch: true },
    });
    chartResizeHandler = () => {
      const w = panel.clientWidth;
      const h = panel.clientHeight;
      if (w > 0 && h > 0) chart.resize(w, h);
    };
    chartResizeHandler();
    window.addEventListener("resize", chartResizeHandler);
    return chart;
  }

  function initEquityChart(panel) {
    destroyEquity(panel);
    const c = colors();
    equityChart = LightweightCharts.createChart(panel, {
      layout: { background: { color: c.bg }, textColor: c.text },
      grid: { vertLines: { visible: false }, horzLines: { color: c.grid } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { borderColor: c.border, scaleMargins: { top: 0.15, bottom: 0.05 } },
      timeScale: { borderColor: c.border, timeVisible: true, secondsVisible: false },
      handleScroll: { vertTouchDrag: false, horzTouchDrag: true },
      handleScale: { axisPressedMouseMove: true, pinch: true },
    });
    equityResizeHandler = () => {
      const w = panel.clientWidth;
      const h = panel.clientHeight;
      if (w > 0 && h > 0) equityChart.resize(w, h);
    };
    equityResizeHandler();
    window.addEventListener("resize", equityResizeHandler);
    return equityChart;
  }

  function render(panel, bundle, options = {}) {
    const clean = options.clean !== false;
    const c = colors();
    initChart(panel);
    panel.style.height = panel.style.height || "100%";

    const bars = (bundle.bars || []).map((b) => ({
      time: b.t,
      open: b.o,
      high: b.h,
      low: b.l,
      close: b.c,
      camp: b.camp ?? 0,
    }));

    if (!bars.length) {
      showMessage(panel, "暂无 K 线数据");
      return null;
    }

    candleSeries = chart.addCandlestickSeries({
      upColor: c.up,
      downColor: c.down,
      borderUpColor: c.up,
      borderDownColor: c.down,
      wickUpColor: c.up,
      wickDownColor: c.down,
    });
    candleSeries.setData(bars);

    if (!clean && bundle.hardened_segments?.length) {
      function segmentStyle(segment) {
        if (segment.style === "dashed" || segment.style === "solid") return segment.style;
        return segment.type === "trail" || segment.kind === "provisional" ? "dashed" : "solid";
      }
      function segmentsToPoints(styleName) {
        const points = [];
        for (const s of bundle.hardened_segments) {
          if (segmentStyle(s) !== styleName) continue;
          points.push({ time: s.t0, value: s.p0 });
          points.push({ time: s.t1, value: s.p1 });
        }
        const dedup = [];
        const seen = new Set();
        for (const p of points) {
          const k = `${p.time}|${p.value}`;
          if (!seen.has(k)) {
            seen.add(k);
            dedup.push(p);
          }
        }
        dedup.sort((a, b) => a.time.localeCompare(b.time));
        return dedup;
      }
      const solid = segmentsToPoints("solid");
      if (solid.length) {
        chart.addLineSeries({
          color: c.line,
          lineWidth: 2,
          lineStyle: LightweightCharts.LineStyle.Solid,
          crosshairMarkerVisible: false,
          lastValueVisible: false,
          priceLineVisible: false,
        }).setData(solid);
      }
      const dashed = segmentsToPoints("dashed");
      if (dashed.length) {
        chart.addLineSeries({
          color: c.line,
          lineWidth: 2,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          crosshairMarkerVisible: false,
          lastValueVisible: false,
          priceLineVisible: false,
        }).setData(dashed);
      }
    }

    if (bundle.markers?.length) {
      const markers = bundle.markers.map((m) => ({
        time: m.t,
        position: m.kind === "entry" ? "belowBar" : "aboveBar",
        color: m.kind === "entry" ? (m.side === "short" ? c.down : c.up) : c.text,
        shape: m.kind === "entry" ? "arrowUp" : "arrowDown",
        text: m.kind === "entry" ? "买" : "卖",
        size: clean ? 1.2 : 1,
      }));
      candleSeries.setMarkers(markers);
    }

    const trades = options.trades || [];
    markerIndex = buildMarkerIndex(bundle.markers, trades);
    if (typeof options.onTradeClick === "function") {
      clickHandler = (param) => {
        if (!param?.time) return;
        options.onTradeClick(param.time);
      };
      chart.subscribeClick(clickHandler);
    }

    chart.timeScale().fitContent();
    return { chart, candleSeries, bars };
  }

  function renderEquity(panel, points) {
    const c = colors();
    const rows = (points || [])
      .filter((p) => p && p.t != null && p.v != null)
      .map((p) => ({ time: p.t, value: Number(p.v) }))
      .sort((a, b) => a.time.localeCompare(b.time));

    if (!rows.length) {
      showEquityMessage(panel, "暂无收益曲线");
      return null;
    }

    initEquityChart(panel);
    equitySeries = equityChart.addAreaSeries({
      lineColor: c.equity,
      topColor: "rgba(94, 176, 255, 0.35)",
      bottomColor: "rgba(94, 176, 255, 0.02)",
      lineWidth: 2,
      crosshairMarkerVisible: true,
      lastValueVisible: true,
      priceLineVisible: false,
    });
    equitySeries.setData(rows);
    equityChart.timeScale().fitContent();
    return { chart: equityChart, series: equitySeries };
  }

  function scrollToTime(entryTime) {
    if (!chart || !entryTime) return;
    void String(entryTime).slice(0, 10);
    try {
      chart.timeScale().scrollToPosition(-10, false);
    } catch {
      /* lightweight-charts version differences */
    }
  }

  return {
    render,
    renderEquity,
    destroyChart,
    destroyEquity,
    showMessage,
    showEquityMessage,
    scrollToTime,
    normalizeTimeKey,
    findTradeAtTime,
    getChart: () => chart,
    getSeries: () => candleSeries,
  };
})();
