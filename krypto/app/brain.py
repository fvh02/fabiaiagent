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


def build_prompt(market: dict, portfolio: dict, rules: dict, recent: list[dict], mode: str) -> str:
    lines = ["coin | price EUR | 1d% | 7d% | 30d% | 90d% | vs SMA20% | vs SMA50% | RSI14 | vol/yr% | vs 30d high%"]
    for coin, m in market.items():
        lines.append(f"{coin} | {m['price']} | {m['chg_1d']} | {m['chg_7d']} | {m['chg_30d']} | {m['chg_90d']} | "
                     f"{m['vs_sma20']} | {m['vs_sma50']} | {m['rsi14']} | {m['vol_annual']} | {m['below_30d_high']}")
    history = "\n".join(f"- {d['date']}: {d['summary']}" for d in recent[-5:]) or "- (first day)"
    return f"""You manage a small crypto portfolio ({'PAPER TRADING – simulated money' if mode == 'paper' else 'REAL MONEY'}) in EUR.
Goal: grow the portfolio over weeks and months while keeping losses small. Capital preservation comes first;
doing nothing is a valid and often the best decision. Every trade costs about {rules['fee_pct']}% fees plus spread,
so only trade when you have a clear reason. Avoid overtrading and chasing pumps.

Hard rules enforced by the system (orders beyond them are cut down or refused):
- Only these coins: {', '.join(market)}
- One buy at most {rules['max_trade_pct']}% of the total value, one coin at most {rules['max_position_pct']}% of it
- Always keep at least {rules['min_cash_pct']}% in cash; minimum order 10 EUR; at most 6 orders per day
- Automatic stop-loss: a coin is sold when it is {rules['stop_loss_pct']}% below its average buy price
- Everything stops when the portfolio is {rules['max_drawdown_pct']}% below its start value

You may use web search for recent important news (regulation, hacks, ETF flows, macro) – keep it short.

Market today (daily candles):
{chr(10).join(lines)}

Portfolio:
{json.dumps(portfolio, ensure_ascii=False, indent=1)}

Your recent decisions:
{history}

Answer only with the JSON object: a German summary and the orders for today (an empty list is fine).
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
