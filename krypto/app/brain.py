"""Ask Claude (Claude Code, headless) for today's trading decisions as structured JSON."""

import json
import logging
import os
import re
import subprocess

log = logging.getLogger("brain")

CLAUDE = os.environ.get("KRYPTO_CLAUDE", "claude")
TIMEOUT = 900

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "2-4 sentences in German: market view and what you do today"},
        "orders": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["buy", "sell"]},
                "coin": {"type": "string"},
                "eur": {"type": "number", "description": "buy: amount in EUR"},
                "fraction": {"type": "number", "description": "sell: share of the holding, 0-1"},
                "reason": {"type": "string", "description": "one short sentence in German"},
            },
            "required": ["action", "coin", "reason"],
        }},
    },
    "required": ["summary", "orders"],
}


class BrainError(Exception):
    pass


def build_prompt(market: dict, portfolio: dict, rules: dict, recent: list[dict], mode: str, held: list[str]) -> str:
    lines = ["coin | price EUR | 3h% | 24h% | RSI14 1h | 7d% | 30d% | 90d% | vs SMA20% | vs SMA50% | RSI14 1d | vol/yr% | vs 30d high%"]
    for coin, m in market.items():
        tag = "" if coin in rules["big"] else " (small)"
        lines.append(f"{coin}{tag} | {m['price']} | {m.get('chg_3h', '?')} | {m.get('chg_24h', '?')} | {m.get('rsi14_1h', '?')} | "
                     f"{m['chg_7d']} | {m['chg_30d']} | {m['chg_90d']} | {m['vs_sma20']} | {m['vs_sma50']} | {m['rsi14']} | "
                     f"{m['vol_annual']} | {m['below_30d_high']}")
    history = "\n".join(f"- {d['date']}: {d['summary']}" for d in recent[-8:]) or "- (first decision)"
    return f"""You manage a small crypto portfolio ({'PAPER TRADING – simulated money' if mode == 'paper' else 'REAL MONEY'}) in EUR.
You are asked every {rules['every_hours']:g} hours. Goal: grow the portfolio while keeping losses small. Capital
preservation comes first; doing nothing is a valid and often the best decision. Every trade costs about
{rules['fee_pct']}% fees plus spread, so a round trip needs more than {2 * rules['fee_pct'] + 0.2:.1f}% move just to break even –
do not trade back and forth without a clear edge. Avoid chasing pumps; small coins can drop 30% in hours.

Hard rules enforced by the system (orders beyond them are cut down or refused):
- Buy only coins from the table (the most traded coins on the exchange); sell only what you hold
- One buy at most {rules['max_trade_pct']:g}% of the total value; one large coin at most {rules['max_position_pct']:g}%,
  one coin marked (small) at most {rules['max_small_pct']:g}% of the total value
- Always keep at least {rules['min_cash_pct']:g}% in cash; minimum order 10 EUR; at most {rules['max_orders_day']} orders per day
- Automatic stop-loss: a coin is sold when it is {rules['stop_loss_pct']:g}% below its average buy price (checked every few minutes)
- Everything stops when the portfolio is {rules['max_drawdown_pct']:g}% below its start value

You may use web search for important recent news (regulation, hacks, listings, ETF flows, macro) – keep it short.

Market now (3h/24h/RSI 1h from hourly candles, the rest from daily candles):
{chr(10).join(lines)}

Portfolio:
{json.dumps(portfolio, ensure_ascii=False, indent=1)}

Your recent decisions:
{history}

Answer only with the JSON object: a German summary and the orders for now (an empty list is fine).
Buys: "eur" amount. Sells: "fraction" of the holding (1 = everything). Give each order a short German reason."""


def decide(prompt: str, model: str = "") -> dict:
    cmd = [CLAUDE, "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
           "--allowedTools", "WebSearch", "WebFetch", "--max-turns", "12"]
    if model:
        cmd += ["--model", model]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, cwd="/tmp", stdin=subprocess.DEVNULL)
    except FileNotFoundError as err:
        raise BrainError("Claude Code ist nicht installiert") from err
    except subprocess.TimeoutExpired as err:
        raise BrainError("Claude hat zu lange gebraucht") from err
    if proc.returncode != 0 and not proc.stdout.strip():
        raise BrainError(f"Claude-Fehler: {(proc.stderr or '').strip()[-300:]}")
    try:
        envelope = json.loads(proc.stdout)
    except ValueError as err:
        raise BrainError("Antwort von Claude nicht lesbar") from err
    if envelope.get("is_error"):
        raise BrainError(f"Claude-Fehler: {str(envelope.get('result'))[:300]}")
    result = envelope.get("structured_output")
    if not isinstance(result, dict):
        text = str(envelope.get("result") or "")
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise BrainError("Claude hat keine Entscheidung geliefert")
        result = json.loads(match.group(0))
    orders = [o for o in result.get("orders") or [] if isinstance(o, dict) and o.get("action") in ("buy", "sell")]
    return {"summary": str(result.get("summary") or "")[:1000], "orders": orders[:10],
            "cost_usd": envelope.get("total_cost_usd")}
