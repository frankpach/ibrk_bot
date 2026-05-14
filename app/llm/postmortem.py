# app/llm/postmortem.py
"""
Post-mortem analysis of closed trades.
Extracts learned patterns and suggests attenuated parameter adjustments.
Uses OpenCode via subprocess — no external API key required.
"""
import json
import logging
from datetime import datetime

from app.config.settings import MARKET_TZ, OPENCODE_BIN
from app.db.database import insert_pattern
from app.db.models import Pattern, Trade
from app.notifications.telegram import notify

logger = logging.getLogger(__name__)


def _call_opencode(prompt: str) -> str:
    """Call OpenCode and return text response. Imported from agent to avoid circular import."""
    import subprocess
    from app.config.settings import OPENCODE_MODEL, OPENCODE_CWD
    try:
        result = subprocess.run(
            [OPENCODE_BIN, "run", "--model", OPENCODE_MODEL, "--format", "json", prompt],
            capture_output=True, text=True, timeout=60,
            cwd=OPENCODE_CWD,
        )
        text_parts = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "text":
                    text_parts.append(event["part"]["text"])
            except json.JSONDecodeError:
                continue
        return "".join(text_parts).strip()
    except subprocess.TimeoutExpired:
        logger.error("postmortem opencode call timed out")
        return ""
    except Exception as e:
        logger.error(f"postmortem opencode call failed: {e}")
        return ""


def run_postmortem(trade: Trade, feature_snapshot=None):
    """Analyze a closed trade and extract a learned pattern with parameter suggestions."""
    if not OPENCODE_BIN:
        logger.debug("OPENCODE_BIN not set — skipping postmortem")
        return

    outcome = "WIN" if (trade.pnl_pct or 0) >= 0 else "LOSS"

    from app.ml.postmortem_stats import enrich_postmortem_context
    ctx = enrich_postmortem_context(trade.symbol)
    ctx_str = f"\n\n{ctx.to_prompt_str()}" if ctx is not None else ""

    feature_context = ""
    if feature_snapshot is not None:
        try:
            if hasattr(feature_snapshot, "to_dict"):
                feature_context = f"\nFEATURES AT ENTRY: {json.dumps(feature_snapshot.to_dict(), default=str)[:500]}"
        except Exception:
            pass

    prompt = (
        f"Analyze this closed trade and extract ONE concise learned pattern. "
        f"Also suggest parameter adjustments if warranted.\n\n"
        f"Symbol: {trade.symbol}\n"
        f"Action: {trade.action}\n"
        f"Signal strength: {trade.signal_strength}\n"
        f"Original justification: {trade.llm_justification}\n"
        f"Entry: ${trade.entry_price:.2f}\n"
        f"Stop-loss: ${trade.stop_loss_price:.2f} ({trade.stop_loss_pct:.1%})\n"
        f"Take-profit: ${trade.take_profit_price:.2f} ({trade.take_profit_pct:.1%})\n"
        f"Result: {outcome}\n"
        f"PnL: {(trade.pnl_pct or 0):.2%} (${(trade.pnl_usd or 0):.2f})\n"
        f"Exit reason: {trade.exit_reason}"
        f"{feature_context}"
        f"{ctx_str}\n\n"
        f"Respond ONLY with this JSON (no extra text):\n"
        '{{"pattern_text": "short pattern description", '
        '"suggestions": [{{"dimension": "stop_loss_pct", "suggested_multiplier": 1.1, "confidence": 0.7, "reason": "brief reason"}}]}}'
    )

    response = _call_opencode(prompt)

    # Parse with graceful degradation
    pattern_text = f"{trade.symbol} {trade.action} {outcome} — {trade.exit_reason}"
    suggestions = []

    if response:
        try:
            content = response.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            pattern_text = data.get("pattern_text", pattern_text)
            suggestions = data.get("suggestions", [])
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Postmortem JSON parse failed: {e} — using plain text")
            pattern_text = response.strip()[:200] if response.strip() else pattern_text

    # Save pattern
    is_win = (trade.pnl_pct or 0) >= 0
    now = datetime.now(tz=MARKET_TZ)
    insert_pattern(Pattern(
        id=None,
        symbol=trade.symbol,
        pattern_text=pattern_text,
        win_count=1 if is_win else 0,
        loss_count=0 if is_win else 1,
        created_at=now,
        updated_at=now,
    ))

    # Apply attenuated adjustments
    adjustments_applied = 0
    for s in suggestions:
        if s.get("confidence", 0) >= 0.5:
            try:
                from app.analysis.scorer import update_weights_attenuated
                ok = update_weights_attenuated(
                    symbol=trade.symbol,
                    dimension=s.get("dimension", ""),
                    suggested_multiplier=float(s.get("suggested_multiplier", 1.0)),
                    confidence=float(s.get("confidence", 0.5)),
                )
                if ok:
                    adjustments_applied += 1
            except ImportError:
                # scorer not yet implemented (issue 004) — log and skip
                logger.debug(f"QuantScorer not available yet, skipping adjustment: {s}")
            except Exception as e:
                logger.error(f"Adjustment failed: {e}")

    # Notify Frank
    notify(
        f"Post-mortem <b>{trade.symbol}</b>: pattern saved.\n"
        f"Result: {'✅ WIN' if is_win else '❌ LOSS'} "
        f"({(trade.pnl_pct or 0):.2%} / ${(trade.pnl_usd or 0):.2f})\n"
        f"{adjustments_applied} adjustment(s) applied."
    )

    logger.info(f"Postmortem {trade.symbol}: pattern saved, {adjustments_applied} adjustments applied")
