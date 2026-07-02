/** 峰极 Web · 国内模拟监测 K 线（同花顺式拖动/缩放 + 中文标注） */
window.FengJiMonitorChart = (function () {
  let chart = null;
  let candleSeries = null;
  let stopLine = null;
  let resizeHandler = null;

  function escapeHtml(value) {
    if (window.FengJiApp?.escapeHtml) return window.FengJiApp.escapeHtml(value);
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function isDark() {
    return document.documentElement.getAttribute("data-theme") !== "light";
  }

  function colors() {
    const dark = isDark();
    return {
      bg: dark ? "#000000" : "#ffffff",
      text: dark ? "#d1d4dc" : "#333333",
      grid: dark ? "#1a1a1c" : "#f0f0f2",
      border: dark ? "#2b2b2e" : "#e0e0e3",
      up: "#e53935",
      down: "#00a65a",
      fengji: "#ff9500",
      fengji2: "#0a84ff",
      buy: "#e53935",
      stop: "#ff9500",
    };
  }

  function destroy(panel) {
    if (resizeHandler) {
      window.removeEventListener("resize", resizeHandler);
      resizeHandler = null;
    }
    if (chart) {
      chart.remove();
      chart = null;
      candleSeries = null;
      stopLine = null;
    }
    panel.querySelectorAll(".empty-state, .chart-hint").forEach((el) => el.remove());
  }

  function showMessage(panel, msg) {
    destroy(panel);
    const el = document.createElement("div");
    el.className = "empty-state monitor-empty";
    el.innerHTML = `<div class="icon">📊</div><p>${escapeHtml(msg)}</p>`;
    panel.appendChild(el);
  }

  function initChart(panel) {
    destroy(panel);
    const c = colors();
    chart = LightweightCharts.createChart(panel, {
      layout: {
        background: { color: c.bg },
        textColor: c.text,
        fontFamily: '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
      },
      grid: {
        vertLines: { color: c.grid, visible: true },
        horzLines: { color: c.grid, visible: true },
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { width: 1, color: "#758696", style: LightweightCharts.LineStyle.Dashed },
        horzLine: { width: 1, color: "#758696", style: LightweightCharts.LineStyle.Dashed },
      },
      rightPriceScale: {
        borderColor: c.border,
        scaleMargins: { top: 0.08, bottom: 0.12 },
      },
      timeScale: {
        borderColor: c.border,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 8,
        barSpacing: 8,
        minBarSpacing: 2,
        tickMarkFormatter: formatChartDate,
      },
      localization: {
        timeFormatter: formatChartDate,
      },
      handleScroll: {
        mouseWheel: false,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: { time: true, price: true },
        mouseWheel: true,
        pinch: true,
      },
      kineticScroll: { mouse: true, touch: true },
    });

    resizeHandler = () => {
      const w = panel.clientWidth;
      const h = panel.clientHeight;
      if (w > 0 && h > 0) chart.resize(w, h);
    };
    resizeHandler();
    window.addEventListener("resize", resizeHandler);

    if (!panel.querySelector(".chart-hint")) {
      const hint = document.createElement("div");
      hint.className = "chart-hint";
      hint.textContent = "按住左键拖动 · 滚轮缩放";
      panel.appendChild(hint);
    }
    return chart;
  }

  function formatChartDate(time) {
    if (typeof time === "string") return time;
    if (time && typeof time === "object") {
      const year = String(time.year).padStart(4, "0");
      const month = String(time.month).padStart(2, "0");
      const day = String(time.day).padStart(2, "0");
      return `${year}-${month}-${day}`;
    }
    if (typeof time === "number") {
      const d = new Date(time * 1000);
      const year = d.getUTCFullYear();
      const month = String(d.getUTCMonth() + 1).padStart(2, "0");
      const day = String(d.getUTCDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    }
    return "";
  }

  function segmentStyle(segment) {
    if (segment.style === "dashed" || segment.style === "solid") return segment.style;
    return segment.type === "trail" || segment.kind === "provisional" ? "dashed" : "solid";
  }

  function segmentsToPoints(segments, styleName) {
    const points = [];
    for (const s of segments) {
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

  function renderFengjiLines(bars, segments) {
    const c = colors();
    if (!segments?.length) return;

    const solid = segmentsToPoints(segments, "solid");
    if (solid.length) {
      const line = chart.addLineSeries({
        color: c.fengji,
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        crosshairMarkerVisible: true,
        lastValueVisible: false,
        priceLineVisible: false,
        title: "峰极连线",
      });
      line.setData(solid);
    }

    const dashed = segmentsToPoints(segments, "dashed");
    if (dashed.length) {
      const provisional = chart.addLineSeries({
        color: c.fengji2,
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        crosshairMarkerVisible: true,
        lastValueVisible: false,
        priceLineVisible: false,
        title: "橡皮筋·可能走势",
      });
      provisional.setData(dashed);
    }
  }

  function render(panel, bundle, position) {
    const c = colors();
    initChart(panel);

    const bars = (bundle.bars || []).map((b) => ({
      time: b.t,
      open: b.o,
      high: b.h,
      low: b.l,
      close: b.c,
    }));

    if (!bars.length) {
      showMessage(panel, "暂无日线数据");
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

    renderFengjiLines(bars, bundle.hardened_segments);

    const markers = [];
    const entryT = String(position?.entry_time || "").slice(0, 10);
    const entryPrice = Number(position?.entry_price || 0);
    const stopPrice = Number(position?.current_stop || bundle.stop_line?.price || 0);
    const isLong = (position?.direction || "long") === "long";

    if (entryT && entryPrice) {
      markers.push({
        time: entryT,
        position: isLong ? "belowBar" : "aboveBar",
        color: c.buy,
        shape: isLong ? "arrowUp" : "arrowDown",
        text: "买入",
        size: 2,
      });
    }

    if (entryT && stopPrice > 0) {
      stopLine = candleSeries.createPriceLine({
        price: stopPrice,
        color: c.stop,
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: "",
      });
    }

    if (markers.length) {
      markers.sort((a, b) => a.time.localeCompare(b.time));
      candleSeries.setMarkers(markers);
    }

    if (entryT) {
      const idx = bars.findIndex((b) => b.time >= entryT);
      const center = idx >= 0 ? idx : bars.length - 30;
      chart.timeScale().setVisibleLogicalRange({
        from: Math.max(0, center - 45),
        to: Math.min(bars.length, center + 45),
      });
    } else {
      chart.timeScale().fitContent();
    }

    return { chart, candleSeries, bars };
  }

  return { render, destroy, showMessage };
})();
