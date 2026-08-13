---
name: fengji-signal-sandbox-audit
description: Reusable FengJi signal verification and sandbox chart workflow. Use when checking whether a DS01-DS08 signal, pending-order fill, Feishu alert, stop price, camp change, peak/extreme line, failed peak/low, or sandbox chart is correct under FengJi OS highest constitution.
---

# FengJi Signal Sandbox Audit

## Non-negotiable rule

Every DS01-DS08 judgment must run under FengJi OS highest constitution. Do not validate a signal from raw geometric highs/lows alone. Use runtime OS fields, hardened peak-extreme line, camp, and legal identity nodes.

## Audit sequence

1. Capture alert facts: symbol, strategy id, timeframe, side, trigger price, latest/fill price, stop, alert time, entry bar time, stated camp, and reason.
2. Load the same data source used by the runtime, not a different market snapshot unless explicitly comparing data vendors.
3. Run FengJi OS on the relevant timeframe.
4. Locate the trigger bar and previous visible OS state.
5. Verify camp, attack line, defense extreme, trigger source, and stop source.
6. Generate a sandbox chart with candles, camp background, hardened peak-extreme line, trigger, stop, and fill/entry mark.
7. State pass/fail and the exact reason.

## Strategy-specific checks

- DS01: Current bar is in camp direction. Previous bar is the trigger stick. Long triggers above previous bullish high in red camp; short triggers below previous bearish low in blue camp. Left-30 line filter means horizontal trigger line crosses at most the allowed number of peak-extreme line segments, not "30 peaks".
- DS03: Two-four-stick logic can break active attack peak/low or a legal failed peak/failed low after a complete in-camp N structure. Long uses red camp and attack peak/failed high. Short mirrors in blue camp.
- DS05: K2 is a possible new extreme in both red and blue camps. K2 is not a possible peak. Peak is the attack direction; extreme is the defense and turn key.
- DS07: D1 grants strategic camp authorization (d1_camp from last closed daily bar). H1 must already be in the same camp before the launch stick (prev_h1_camp matches d1_camp) and must trigger only via DS03 two-four-stick same-camp continuation (LONG_CONTINUE/SHORT_CONTINUE). H1 must have legal hardened N structure (hardened_count >= 4) and a valid defense extreme. Reverse-camp merge (ALIGN_TURN) is forbidden.

## Sandbox chart standard

The chart must show:

- Candles for enough context before and after the signal.
- FengJi hardened peak-extreme line.
- Camp background or camp labels.
- Failed peak/failed low marks when they are the trigger source.
- Trigger price line.
- Initial stop line.
- Entry/fill marker.

If Matplotlib is unavailable on the server, use the project SVG fallback script:

```powershell
scripts\plot_live_ds03_sandbox_svg.py
```

For crypto DS03 live alerts, expected local/remote output paths should be under:

```text
results\sandbox\
```

## Common failure modes

- Using reverse-merge DS07 logic (ALIGN_TURN) that lets H1 turn camp on the launch stick instead of the canonical DS03 two-four-stick same-camp continuation.
- Treating a raw high/low as a FengJi peak/extreme without OS identity.
- Misreading DS01 left-30 as number of peaks instead of number of crossed line segments.
- Treating DS05 K2 as a peak candidate instead of an extreme candidate.
- Checking a stale CSV or different exchange/vendor data than the live monitor used.

## Response format

Use this order:

1. `结论`: valid/invalid/needs-data.
2. `OS证据`: camp, attack node, defense node, failed node if used.
3. `价格证据`: trigger/fill/stop and bar high/low.
4. `沙盒图`: local image/file path.
5. `修正建议`: only if invalid or ambiguous.

