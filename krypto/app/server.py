"""Krypto-Trader add-on: Claude decides once a day, hard rules protect the money, paper or live.

Every hour: prices, stop-losses and the drawdown limit are checked (no Claude needed).
Once a day: Claude gets the market and the portfolio and decides what to buy or sell.
"""

import asyncio
import io
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import aiohttp
from aiohttp import web

import brain
import trader
from market import Market, MarketError, make_exchange

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("krypto")

DATA = Path(os.environ.get("KRYPTO_DATA", "/data"))
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("KRYPTO_PORT", "8094"))
INKBOX = os.environ.get("INKBOX_IMESSAGE_URL", "https://inkbox.ai/api/v1/imessage")
LIVE_PHRASE = "ICH TRAGE DAS RISIKO"


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPT = load_options()
COINS_OPT = str(OPT.get("coins") or "auto").strip()
AUTO = COINS_OPT.lower() == "auto"
COINS = [] if AUTO else [c.strip().upper() for c in COINS_OPT.split(",") if c.strip()]
AUTO_TOP = int(OPT.get("auto_top") or 40)
MIN_VOLUME = float(OPT.get("min_volume_eur") or 250000)
EXCHANGE = OPT.get("exchange") or "kraken"
WANT_LIVE = OPT.get("mode") == "live"
LIVE = WANT_LIVE and str(OPT.get("live_confirm") or "").strip().upper() == LIVE_PHRASE and bool(OPT.get("api_key"))
MODE = "live" if LIVE else "paper"
RULES = trader.Rules(
    budget=float(OPT.get("budget_eur") or 500),
    max_trade_pct=float(OPT.get("max_trade_pct") or 25), max_position_pct=float(OPT.get("max_position_pct") or 40),
    min_cash_pct=float(OPT.get("min_cash_pct") if OPT.get("min_cash_pct") is not None else 10),
    stop_loss_pct=float(OPT.get("stop_loss_pct") or 12), max_drawdown_pct=float(OPT.get("max_drawdown_pct") or 20),
    fee_pct=float(OPT.get("fee_pct") if OPT.get("fee_pct") is not None else 0.4),
    max_small_pct=float(OPT.get("max_small_pct") or 10), max_orders_day=int(OPT.get("max_orders_day") or 12),
)
EVERY_HOURS = float(OPT.get("decision_every_hours") or 3)
REPORT_HOUR = int(OPT.get("report_hour") if OPT.get("report_hour") is not None else 20)
CHECK_EVERY = float(os.environ.get("KRYPTO_CHECK_INTERVAL") or 60 * float(OPT.get("check_minutes") or 15))
UNIVERSE_EVERY = 6 * 3600
MODEL = (OPT.get("claude_model") or "").strip()
INKBOX_KEY = (OPT.get("inkbox_api_key") or "").strip()
NOTIFY_TO = (OPT.get("imessage_to") or "").strip()
if OPT.get("claude_oauth_token"):
    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = str(OPT["claude_oauth_token"]).strip()
BRIDGE_URL = (OPT.get("claude_bridge_url") or "").strip()

state = {"market": {}, "prices": {}, "updated": 0.0, "busy": False, "error": ""}
lock = asyncio.Lock()
ledger = trader.Ledger(DATA)
market: Market | None = None
broker = None
routes = web.RouteTableDef()


# -- helpers ---------------------------------------------------------------------------
def risk_level() -> str:
    level = (ledger.data or {}).get("risk", "ausgewogen")
    return level if level in trader.RISK_LEVELS else "ausgewogen"


def rules() -> trader.Rules:
    """The option values adjusted to the risk level chosen in the dashboard."""
    return trader.rules_for(RULES, risk_level())


# -------------------------------------------------------------------------
def fmt_eur(v: float) -> str:
    return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(a: float, b: float) -> float:
    return round((a / b - 1) * 100, 2) if b else 0.0


def fmt_pct(v: float) -> str:
    return f"{v:+.1f} %".replace(".", ",")


def bench_values(prices: dict) -> dict:
    d = ledger.data
    start, bench = d["start_value"], d.get("bench") or {}
    btc = start * prices["BTC"] / bench["BTC"] if "BTC" in prices and bench.get("BTC") else None
    ratios = [prices[c] / bench[c] for c in bench if c in prices and bench[c]]
    basket = start * sum(ratios) / len(ratios) if ratios else None
    return {"btc": btc, "basket": basket}


def summary() -> dict:
    d, prices = ledger.data, state["prices"]
    if not d:
        return {"ready": False, "mode": MODE, "error": state["error"]}
    value = ledger.value(prices) if prices else None
    holdings = []
    for coin, p in sorted(d["positions"].items()):
        price = prices.get(coin)
        now = p["qty"] * price if price else None
        holdings.append({"coin": coin, "qty": p["qty"], "cost": round(p["cost"], 2), "value": round(now, 2) if now else None,
                         "pnl_pct": pct(now, p["cost"]) if now else None, "price": price})
    bench = bench_values(prices) if prices else {}
    return {
        "ready": True, "mode": d["mode"], "want_live": WANT_LIVE, "live_blocked": WANT_LIVE and not LIVE,
        "exchange": EXCHANGE, "coins": state.get("tradable") or COINS, "halted": d["halted"], "halt_reason": d["halt_reason"],
        "start_value": d["start_value"], "started": d["started"], "cash": round(d["cash"], 2),
        "value": round(value, 2) if value is not None else None, "pnl_pct": pct(value, d["start_value"]) if value else None,
        "btc_hold": round(bench["btc"], 2) if bench.get("btc") else None,
        "basket_hold": round(bench["basket"], 2) if bench.get("basket") else None,
        "holdings": holdings, "decisions": d["decisions"][-15:][::-1], "history": d["history"][-24 * 120:],
        "updated": state["updated"], "busy": state["busy"], "error": state["error"],
        "every_hours": EVERY_HOURS, "last_decision": d["last_decision"], "next_decision": next_decision(),
        "auto": AUTO,
        "rules": rules().__dict__, "risk": risk_level(), "risk_levels": list(trader.RISK_LEVELS),
        "claude": brain.claude_source(BRIDGE_URL),
    }


async def notify(session: aiohttp.ClientSession, text: str) -> None:
    if not (INKBOX_KEY and NOTIFY_TO):
        return
    try:
        async with session.post(f"{INKBOX}/messages", json={"to": NOTIFY_TO, "text": text},
                                headers={"X-API-Key": INKBOX_KEY}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status >= 300:
                log.warning("iMessage fehlgeschlagen: %s", resp.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        log.warning("iMessage fehlgeschlagen: %s", err)


def describe(fill: dict) -> str:
    verb = "Kauf" if fill["side"] == "buy" else "Verkauf"
    return f"{verb} {fill['coin']} {fmt_eur(fill['eur'])}" + (f" – {fill['reason']}" if fill.get("reason") else "")


# -- the work ------------------------------------------------------------------------
async def refresh_universe() -> None:
    """Which coins may be bought: the configured list, or the most traded coins (auto)."""
    if AUTO:
        coins = await asyncio.to_thread(market.universe, AUTO_TOP, MIN_VOLUME)
    else:
        coins = await asyncio.to_thread(market.available, COINS)
        missing = [c for c in COINS if c not in coins]
        if missing:
            log.warning("Nicht auf %s in EUR handelbar, wird ignoriert: %s", EXCHANGE, ", ".join(missing))
    if not coins:
        raise MarketError("Keine handelbaren Coins gefunden")
    state["tradable"] = coins
    state["universe_at"] = time.time()


def watched() -> list[str]:
    """Coins whose price we need: tradable ones, everything held, Bitcoin and the benchmark basket."""
    coins = list(state.get("tradable") or [])
    if ledger.ready:
        coins += [c for c in ledger.data["positions"] if c not in coins]
        coins += [c for c in (ledger.data.get("bench") or {}) if c not in coins]
    if "BTC" not in coins:
        coins.append("BTC")
    return coins


async def refresh() -> None:
    """Current prices (one request) – cheap enough for every risk check."""
    if not state.get("tradable") or time.time() - state.get("universe_at", 0) > UNIVERSE_EVERY:
        await refresh_universe()
    prices = await asyncio.to_thread(market.prices, watched())
    if not prices:
        raise MarketError("Keine Kurse erhalten")
    state["prices"].update(prices)
    state["updated"] = time.time()
    if not ledger.ready or ledger.data.get("mode") != MODE:
        # Benchmark basket: the coins tradable at the start.
        ledger.fresh(MODE, RULES.budget, {c: p for c, p in prices.items() if c in state["tradable"] or c == "BTC"})
        log.info("Neues %s-Konto mit %s", "Echtgeld" if LIVE else "Papier", fmt_eur(RULES.budget))
    value = ledger.value(state["prices"])
    bench = bench_values(state["prices"])
    hist = ledger.data["history"]
    if not hist or time.time() - hist[-1]["t"] >= 3600 - 60 or len(hist) < 2:
        hist.append({"t": int(time.time()), "v": round(value, 2), "btc": round(bench["btc"] or 0, 2), "basket": round(bench["basket"] or 0, 2)})
    else:
        hist[-1].update(v=round(value, 2), btc=round(bench["btc"] or 0, 2), basket=round(bench["basket"] or 0, 2))
    del hist[:-24 * 180]
    ledger.save()


def next_decision() -> float | None:
    if not ledger.ready:
        return None
    return ledger.data.get("last_decision_ts", 0) + EVERY_HOURS * 3600


async def check_risk(session) -> None:
    """Stop-loss per coin and the overall drawdown limit – no Claude involved.

    Stop-losses keep protecting the coins even while trading is paused."""
    d, prices = ledger.data, state["prices"]
    value = ledger.value(prices)
    if not d["halted"] and value <= d["start_value"] * (1 - RULES.max_drawdown_pct / 100):
        fills = await asyncio.to_thread(trader.sell_all, ledger, broker, prices, "Verlustgrenze erreicht")
        d["halted"], d["halt_reason"] = True, f"Verlustgrenze −{RULES.max_drawdown_pct:.0f} % erreicht"
        ledger.save()
        await notify(session, f"🛑 Krypto-Trader gestoppt: Verlustgrenze erreicht ({fmt_eur(value)} von {fmt_eur(d['start_value'])}). "
                              f"Alles verkauft ({len(fills)} Orders). Weiter nur, wenn du es freigibst.")
        return
    stop = rules().stop_loss_pct
    for coin, p in list(d["positions"].items()):
        price = prices.get(coin)
        if price and p["qty"] and p["qty"] * price <= p["cost"] * (1 - stop / 100):
            fills, notes = await asyncio.to_thread(trader.execute, ledger, broker, rules(),
                                                   [{"action": "sell", "coin": coin, "fraction": 1, "reason": f"Stop-Loss −{stop:.0f} %"}],
                                                   prices, watched(), True)
            if fills:
                await notify(session, f"⚠️ Stop-Loss: {describe(fills[0])}")


async def decide(session, manual: bool = False) -> dict:
    d = ledger.data
    if d["halted"]:
        return {"error": "Trading ist gestoppt"}
    prices = state["prices"]
    portfolio = {
        "cash_eur": round(d["cash"], 2), "total_eur": round(ledger.value(prices), 2), "start_eur": d["start_value"],
        "holdings": {c: {"qty": round(p["qty"], 8), "value_eur": round(p["qty"] * prices.get(c, 0), 2),
                         "cost_eur": round(p["cost"], 2)} for c, p in d["positions"].items()},
    }
    state["busy"] = True
    try:
        coins = list(state["tradable"]) + [c for c in d["positions"] if c not in state["tradable"]]
        snapshot = await asyncio.to_thread(market.snapshot, coins)
        state["market"] = snapshot
        prompt = brain.build_prompt(snapshot, portfolio, {**rules().__dict__, "every_hours": EVERY_HOURS,
                                    "big": sorted(trader.BIG), "risk_hint": trader.RISK_HINTS[risk_level()]},
                                    d["decisions"], d["mode"], list(d["positions"]))
        result = await asyncio.to_thread(brain.decide, prompt, MODEL, BRIDGE_URL)
    except brain.BrainError as err:
        d["decisions"].append({"date": time.strftime("%Y-%m-%d %H:%M"), "summary": f"Keine Entscheidung: {err}", "fills": [], "notes": []})
        ledger.save()
        d["last_decision_ts"] = time.time()
        ledger.save()
        await notify(session, f"⚠️ Krypto-Trader: Claude konnte diesmal nicht entscheiden ({err}). Es wurde nichts gehandelt.")
        return {"error": str(err)}
    except MarketError as err:
        d["last_decision_ts"] = time.time() - EVERY_HOURS * 3600 + 900  # try again in 15 minutes
        return {"error": str(err)}
    finally:
        state["busy"] = False
    fills, notes = await asyncio.to_thread(trader.execute, ledger, broker, rules(), result["orders"], prices, state["tradable"])
    entry = {"date": time.strftime("%Y-%m-%d %H:%M"), "summary": result["summary"], "orders": result["orders"],
             "fills": [{k: f[k] for k in ("side", "coin", "eur", "qty", "price", "reason")} for f in fills], "notes": notes,
             "manual": manual}
    d["decisions"].append(entry)
    del d["decisions"][:-200]
    d["last_decision"] = time.strftime("%Y-%m-%d %H:%M")
    d["last_decision_ts"] = time.time()
    ledger.save()
    if fills:  # every few hours: only write when something was actually traded
        await notify(session, "\n".join([f"💱 Krypto-Trader: {result['summary']}"] + ["• " + describe(f) for f in fills]
                                         + [status_line()]))
    return entry


def status_line() -> str:
    d, prices = ledger.data, state["prices"]
    value = ledger.value(prices)
    bench = bench_values(prices)
    line = f"{'Papier' if d['mode'] == 'paper' else 'ECHT'}: {fmt_eur(value)} ({fmt_pct(pct(value, d['start_value']))})"
    if bench.get("btc"):
        line += f" · nur Bitcoin halten: {fmt_pct(pct(bench['btc'], d['start_value']))}"
    return line


async def daily_report(session) -> None:
    d = ledger.data
    today = time.strftime("%Y-%m-%d")
    if d.get("report_day") == today or datetime.now().hour < REPORT_HOUR:
        return
    d["report_day"] = today
    ledger.save()
    trades = [f for e in d["decisions"] if e["date"].startswith(today) for f in e.get("fills", [])]
    holdings = ", ".join(f"{c} {fmt_eur(p['qty'] * state['prices'].get(c, 0))}" for c, p in d["positions"].items()) or "nur Bargeld"
    await notify(session, f"📊 Krypto-Trader Tagesbericht\n{status_line()}\nHeute {len(trades)} Trades · Bestand: {holdings}"
                          + (f"\n⏸️ Gestoppt: {d['halt_reason']}" if d["halted"] else ""))


async def loop(app: web.Application) -> None:
    session = app["http"]
    while True:
        try:
            async with lock:
                await refresh()
                await check_risk(session)
                if not ledger.data["halted"] and time.time() >= (next_decision() or 0):
                    await decide(session)
                await daily_report(session)
            state["error"] = ""
        except (MarketError, trader.TradeError) as err:
            state["error"] = str(err)
            log.warning("%s", err)
        except Exception as err:  # keep the loop alive whatever happens
            state["error"] = f"{err.__class__.__name__}: {err}"
            log.exception("Fehler in der Schleife")
        await asyncio.sleep(CHECK_EVERY)


# -- API ------------------------------------------------------------------------------
@routes.get("/")
async def index(_: web.Request) -> web.Response:
    return web.Response(text=(STATIC / "index.html").read_text(encoding="utf-8"), content_type="text/html",
                        headers={"Cache-Control": "no-cache"})


@routes.get("/api/status")
async def api_status(_: web.Request) -> web.Response:
    return web.json_response(summary())


@routes.post("/api/decide")
async def api_decide(request: web.Request) -> web.Response:
    if state["busy"]:
        return web.json_response({"error": "Claude entscheidet gerade schon"}, status=409)
    async with lock:
        await refresh()
        result = await decide(request.app["http"], manual=True)
    return web.json_response(result, status=200 if "error" not in result else 503)


@routes.post("/api/halt")
async def api_halt(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    async with lock:
        ledger.data["halted"], ledger.data["halt_reason"] = True, "Von dir gestoppt"
        fills = []
        if body.get("sell_all"):
            await refresh()
            fills = await asyncio.to_thread(trader.sell_all, ledger, broker, state["prices"], "Not-Aus")
        ledger.save()
    await notify(request.app["http"], "⏸️ Krypto-Trader gestoppt" + (f", alles verkauft ({len(fills)} Orders)." if body.get("sell_all") else "."))
    return web.json_response({"halted": True, "sold": len(fills)})


@routes.post("/api/resume")
async def api_resume(request: web.Request) -> web.Response:
    async with lock:
        d = ledger.data
        if d.get("halt_reason", "").startswith("Verlustgrenze"):
            # After the loss limit: continue from today's value as the new start.
            d["start_value"] = round(ledger.value(state["prices"]), 2)
        d["halted"], d["halt_reason"] = False, ""
        ledger.save()
    await notify(request.app["http"], "▶️ Krypto-Trader läuft wieder.")
    return web.json_response({"halted": False})


@routes.post("/api/risk")
async def api_risk(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    level = str(body.get("level") or "")
    if level not in trader.RISK_LEVELS or not ledger.data:
        return web.json_response({"error": "Unbekannte Stufe"}, status=400)
    async with lock:
        ledger.data["risk"] = level
        ledger.save()
    log.info("Risikobereitschaft: %s", level)
    return web.json_response({"risk": level, "rules": rules().__dict__})


@routes.get("/api/trades.csv")
async def api_csv(_: web.Request) -> web.Response:
    data = ledger.csv.read_bytes() if ledger.csv.exists() else b"Noch keine Trades\n"
    return web.Response(body=data, content_type="text/csv", headers={"Content-Disposition": "attachment; filename=krypto-trades.csv"})


async def on_startup(app: web.Application) -> None:
    global market, broker
    app["http"] = aiohttp.ClientSession()
    market = Market(EXCHANGE)
    if LIVE:
        broker = trader.LiveBroker(make_exchange(EXCHANGE, OPT.get("api_key", ""), OPT.get("api_secret", ""), OPT.get("api_password", "")))
        log.warning("ECHTGELD-MODUS auf %s mit Budget %s", EXCHANGE, fmt_eur(RULES.budget))
    else:
        broker = trader.PaperBroker(RULES.fee_pct)
        if WANT_LIVE:
            log.warning("mode=live gesetzt, aber live_confirm/API-Key fehlen – es bleibt beim Papertrading")
    log.info("Krypto-Trader (%s) – %s, Entscheidung alle %s Stunden, Prüfung alle %s Minuten", MODE,
             f"automatisch die {AUTO_TOP} meistgehandelten Coins" if AUTO else ", ".join(COINS), EVERY_HOURS, round(CHECK_EVERY / 60))
    app["loop"] = asyncio.create_task(loop(app))


async def on_cleanup(app: web.Application) -> None:
    app["loop"].cancel()
    await app["http"].close()


def main() -> None:
    app = web.Application()
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(app, host=None, port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
