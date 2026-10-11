"""Ledger, brokers (paper and live) and the hard risk rules.

The add-on keeps its own ledger: cash and coins that belong to the trader. It never spends more than
that, and in live mode also never more than is really on the exchange account.
"""

import csv
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import ccxt

log = logging.getLogger("trader")

MIN_ORDER_EUR = 10.0
# Large, liquid coins; everything else counts as a small coin with a lower position limit.
BIG = {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "TRX", "LINK", "AVAX", "DOT", "LTC", "BCH", "XLM", "TON", "BNB"}


class TradeError(Exception):
    pass


@dataclass
class Rules:
    budget: float
    max_trade_pct: float      # one buy at most this share of the total value
    max_position_pct: float   # one coin at most this share of the total value
    min_cash_pct: float       # always keep this share in cash
    stop_loss_pct: float      # sell a coin that fell this far below its average buy price
    max_drawdown_pct: float   # stop everything when the total fell this far below the start
    fee_pct: float            # paper trading: fee per trade
    max_small_pct: float = 10.0   # one small coin at most this share of the total value
    max_orders_day: int = 12


# -- ledger ------------------------------------------------------------------------
class Ledger:
    def __init__(self, folder: Path):
        self.folder = folder
        self.file = folder / "krypto.json"
        self.csv = folder / "trades.csv"
        self.data: dict = {}
        if self.file.exists():
            try:
                self.data = json.loads(self.file.read_text())
            except ValueError:
                log.error("Ledger beschädigt – wird neu angelegt")

    def fresh(self, mode: str, budget: float, prices: dict[str, float]) -> None:
        if self.data:
            archive = self.folder / f"krypto-{self.data.get('mode', 'alt')}-{int(time.time())}.json"
            archive.write_text(json.dumps(self.data))
        self.data = {
            "mode": mode, "started": time.time(), "start_value": budget, "cash": budget, "positions": {},
            "halted": False, "halt_reason": "", "last_decision": "", "bench": dict(prices),
            "history": [], "decisions": [], "trades_today": {"day": "", "count": 0},
        }
        self.save()

    def save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.file)

    @property
    def ready(self) -> bool:
        return bool(self.data)

    def value(self, prices: dict[str, float]) -> float:
        return self.data["cash"] + sum(p["qty"] * prices.get(c, 0) for c, p in self.data["positions"].items())

    def record_trade(self, fill: dict) -> None:
        new = not self.csv.exists()
        with self.csv.open("a", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            if new:
                writer.writerow(["Zeit", "Modus", "Aktion", "Coin", "Menge", "Kurs EUR", "Betrag EUR", "Gebühr EUR", "Grund"])
            writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(fill["t"])), self.data["mode"],
                             "Kauf" if fill["side"] == "buy" else "Verkauf", fill["coin"],
                             f"{fill['qty']:.8f}", f"{fill['price']:.4f}", f"{fill['eur']:.2f}", f"{fill['fee']:.2f}",
                             fill.get("reason", "")])

    def apply(self, fill: dict) -> None:
        pos = self.data["positions"].setdefault(fill["coin"], {"qty": 0.0, "cost": 0.0})
        cash_fee = fill.get("cash_fee", fill["fee"])
        if fill["side"] == "buy":
            self.data["cash"] -= fill["eur"] + cash_fee
            pos["qty"] += fill["qty"]
            pos["cost"] += fill["eur"] + cash_fee
        else:
            share = min(1.0, fill["qty"] / pos["qty"]) if pos["qty"] else 1.0
            pos["cost"] *= 1 - share
            pos["qty"] -= fill["qty"]
            self.data["cash"] += fill["eur"] - cash_fee
            if pos["qty"] <= 1e-10:
                del self.data["positions"][fill["coin"]]
        self.data["cash"] = round(self.data["cash"], 2)
        self.record_trade(fill)
        self.save()


# -- brokers -------------------------------------------------------------------------
class PaperBroker:
    """Fills at the current market price plus slippage and the configured fee."""

    def __init__(self, fee_pct: float, slippage_pct: float = 0.1):
        self.fee = fee_pct / 100
        self.slip = slippage_pct / 100

    def buy(self, coin: str, eur: float, price: float) -> dict:
        fill_price = price * (1 + self.slip)
        fee = eur * self.fee
        net = eur - fee
        return {"side": "buy", "coin": coin, "qty": net / fill_price, "price": fill_price, "eur": round(net, 2), "fee": round(fee, 2)}

    def sell(self, coin: str, qty: float, price: float) -> dict:
        fill_price = price * (1 - self.slip)
        gross = qty * fill_price
        return {"side": "sell", "coin": coin, "qty": qty, "price": fill_price, "eur": round(gross, 2), "fee": round(gross * self.fee, 2)}

    def free(self, asset: str) -> float | None:
        return None  # no exchange behind it


class LiveBroker:
    """Real market orders through ccxt. The API key should be allowed to trade, never to withdraw."""

    def __init__(self, exchange, quote: str = "EUR"):
        self.ex = exchange
        self.quote = quote
        self.ex.load_markets()

    def free(self, asset: str) -> float:
        balance = self.ex.fetch_balance()
        return float((balance.get("free") or {}).get(asset) or 0)

    def _fill(self, order: dict, side: str, coin: str, fallback_qty: float, fallback_price: float) -> dict:
        try:
            if order.get("id"):
                time.sleep(1.5)
                order = self.ex.fetch_order(order["id"], f"{coin}/{self.quote}") or order
        except ccxt.BaseError:
            pass
        qty = float(order.get("filled") or fallback_qty)
        price = float(order.get("average") or order.get("price") or fallback_price)
        cost = float(order.get("cost") or qty * price)
        fee_quote = fee_base = 0.0
        for f in order.get("fees") or ([order["fee"]] if order.get("fee") else []):
            if not f or not f.get("cost"):
                continue
            if f.get("currency") == coin:
                fee_base += float(f["cost"])
            else:
                fee_quote += float(f["cost"])
        if side == "buy":
            qty -= fee_base  # coins actually received
        return {"side": side, "coin": coin, "qty": qty, "price": price, "eur": round(cost, 2),
                "fee": round(fee_quote + fee_base * price, 2), "cash_fee": round(fee_quote, 2), "order_id": order.get("id")}

    def buy(self, coin: str, eur: float, price: float) -> dict:
        symbol = f"{coin}/{self.quote}"
        try:
            if self.ex.has.get("createMarketBuyOrderWithCost"):
                order = self.ex.create_market_buy_order_with_cost(symbol, float(self.ex.cost_to_precision(symbol, eur)))
            else:
                amount = float(self.ex.amount_to_precision(symbol, eur / price))
                order = self.ex.create_order(symbol, "market", "buy", amount)
        except ccxt.BaseError as err:
            raise TradeError(f"Kauf {coin} abgelehnt: {err}") from err
        return self._fill(order, "buy", coin, eur / price, price)

    def sell(self, coin: str, qty: float, price: float) -> dict:
        symbol = f"{coin}/{self.quote}"
        try:
            amount = float(self.ex.amount_to_precision(symbol, qty))
            order = self.ex.create_order(symbol, "market", "sell", amount)
        except ccxt.BaseError as err:
            raise TradeError(f"Verkauf {coin} abgelehnt: {err}") from err
        return self._fill(order, "sell", coin, qty, price)


# -- risk rules + execution ------------------------------------------------------------
def execute(ledger: Ledger, broker, rules: Rules, orders: list[dict], prices: dict[str, float], allowed: list[str],
            emergency: bool = False) -> tuple[list[dict], list[str]]:
    """Check every order against the hard rules, then execute sells before buys.

    Returns the fills and notes about orders that were cut down or refused."""
    data = ledger.data
    notes: list[str] = []
    fills: list[dict] = []
    if data["halted"] and not emergency:
        return [], ["Trading ist gestoppt – keine Orders ausgeführt"]
    today = time.strftime("%Y-%m-%d")
    counter = data.setdefault("trades_today", {"day": today, "count": 0})
    if counter["day"] != today:
        counter.update(day=today, count=0)

    sells = [o for o in orders if o.get("action") == "sell"]
    buys = [o for o in orders if o.get("action") == "buy"]
    for order in sells + buys:
        coin = str(order.get("coin", "")).upper()
        reason = str(order.get("reason", ""))[:300]
        held_coin = coin in data["positions"]
        if coin not in prices or (order["action"] == "buy" and coin not in allowed) or (order["action"] == "sell" and not held_coin and coin not in allowed):
            notes.append(f"{coin}: nicht erlaubt oder kein Kurs")
            continue
        # Stop-loss and emergency sells never count towards (or wait for) the daily limit.
        if not emergency and counter["count"] >= rules.max_orders_day:
            notes.append(f"{coin}: höchstens {rules.max_orders_day} Orders pro Tag")
            continue
        price = prices[coin]
        try:
            if order["action"] == "sell":
                held = data["positions"].get(coin, {}).get("qty", 0.0)
                fraction = max(0.0, min(1.0, float(order.get("fraction") or 1.0)))
                qty = held if fraction >= .98 else held * fraction
                free = broker.free(coin)
                if free is not None:
                    qty = min(qty, free)
                if qty <= 0 or qty * price < MIN_ORDER_EUR / 2:
                    notes.append(f"{coin}: nichts zu verkaufen")
                    continue
                fill = broker.sell(coin, qty, price)
            else:
                total = ledger.value(prices)
                eur = float(order.get("eur") or 0)
                cash_free = data["cash"] - total * rules.min_cash_pct / 100
                exchange_cash = broker.free("EUR")
                if exchange_cash is not None:
                    cash_free = min(cash_free, exchange_cash * 0.995)
                held_value = data["positions"].get(coin, {}).get("qty", 0.0) * price
                position_pct = rules.max_position_pct if coin in BIG else min(rules.max_position_pct, rules.max_small_pct)
                limit = min(cash_free, total * rules.max_trade_pct / 100, total * position_pct / 100 - held_value)
                if eur > limit:
                    notes.append(f"{coin}: Kauf von {eur:.0f} € auf {max(0, limit):.0f} € begrenzt (Regeln)")
                    eur = limit
                if eur < MIN_ORDER_EUR:
                    notes.append(f"{coin}: Kauf zu klein oder kein Spielraum mehr")
                    continue
                fill = broker.buy(coin, round(eur, 2), price)
        except (TradeError, ValueError, TypeError) as err:
            notes.append(str(err))
            continue
        fill.update(t=time.time(), reason=reason)
        ledger.apply(fill)
        fills.append(fill)
        if not emergency:
            counter["count"] += 1
    ledger.save()
    return fills, notes


def sell_all(ledger: Ledger, broker, prices: dict[str, float], reason: str) -> list[dict]:
    orders = [{"action": "sell", "coin": c, "fraction": 1, "reason": reason} for c in ledger.data["positions"]]
    fills, _ = execute(ledger, broker, Rules(0, 0, 0, 0, 0, 0, 0), orders, prices, list(prices), emergency=True)
    return fills
