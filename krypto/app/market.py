"""Market data in EUR from a crypto exchange (public data, no key needed), plus simple indicators."""

import json
import logging
import math
import os
import time

import ccxt

log = logging.getLogger("market")


class MarketError(Exception):
    pass


def make_exchange(exchange_id: str, key: str = "", secret: str = "", password: str = ""):
    if exchange_id not in ccxt.exchanges:
        raise MarketError(f"Unbekannte Börse: {exchange_id}")
    params = {"enableRateLimit": True, "timeout": 30000}
    if key and secret:
        params.update(apiKey=key, secret=secret)
        if password:
            params["password"] = password
    return getattr(ccxt, exchange_id)(params)


class Market:
    def __init__(self, exchange_id: str, quote: str = "EUR"):
        self.quote = quote
        self.mock = os.environ.get("KRYPTO_MOCK_MARKET")  # tests: JSON file {coin: [daily closes]}
        self.exchange = None if self.mock else make_exchange(exchange_id)
        self._markets_loaded = 0.0

    def _load(self):
        if self.exchange and time.time() - self._markets_loaded > 6 * 3600:
            self.exchange.load_markets(True)
            self._markets_loaded = time.time()

    def symbol(self, coin: str) -> str:
        return f"{coin}/{self.quote}"

    def available(self, coins: list[str]) -> list[str]:
        if self.mock:
            data = json.loads(open(self.mock).read())
            return [c for c in coins if c in data]
        self._load()
        return [c for c in coins if self.symbol(c) in self.exchange.markets]

    def universe(self, top: int, min_volume_eur: float) -> list[str]:
        """The most traded coins against EUR (stablecoins and fiat left out)."""
        if self.mock:
            return list(json.loads(open(self.mock).read()))[:top]
        self._load()
        symbols = [m["symbol"] for m in self.exchange.markets.values()
                   if m.get("quote") == self.quote and m.get("spot", True) and m.get("active", True) is not False
                   and m.get("base") not in STABLE]
        try:
            tickers = self.exchange.fetch_tickers(symbols)
        except ccxt.BaseError as err:
            raise MarketError(f"Coin-Liste nicht abrufbar: {err}") from err
        ranked = []
        for sym, t in tickers.items():
            volume = t.get("quoteVolume") or ((t.get("baseVolume") or 0) * (t.get("last") or 0))
            if volume and volume >= min_volume_eur:
                ranked.append((volume, sym.split("/")[0]))
        ranked.sort(reverse=True)
        return [coin for _, coin in ranked[:top]]

    def prices(self, coins: list[str]) -> dict[str, float]:
        """Current prices, one request for all coins."""
        if self.mock:
            data = json.loads(open(self.mock).read())
            return {c: data[c][-1] for c in coins if c in data}
        try:
            tickers = self.exchange.fetch_tickers([self.symbol(c) for c in coins])
        except ccxt.BaseError as err:
            raise MarketError(f"Kurse nicht abrufbar: {err}") from err
        return {sym.split("/")[0]: float(t["last"]) for sym, t in tickers.items() if t.get("last")}

    def hourly(self, coin: str, hours: int = 72) -> list[float]:
        if self.mock:
            return json.loads(open(self.mock).read())[coin][-hours:]
        rows = self.exchange.fetch_ohlcv(self.symbol(coin), "1h", limit=hours)
        return [r[4] for r in rows if r and r[4]]

    def closes(self, coin: str, days: int = 90) -> list[float]:
        if self.mock:
            return json.loads(open(self.mock).read())[coin][-days:]
        try:
            rows = self.exchange.fetch_ohlcv(self.symbol(coin), "1d", limit=days)
        except ccxt.BaseError as err:
            raise MarketError(f"Kurse für {coin} nicht abrufbar: {err}") from err
        closes = [r[4] for r in rows if r and r[4]]
        # The last candle is today's and still moving: use the live price for it.
        try:
            ticker = self.exchange.fetch_ticker(self.symbol(coin))
            if ticker.get("last"):
                closes[-1:] = [float(ticker["last"])]
        except ccxt.BaseError:
            pass
        return closes

    def snapshot(self, coins: list[str]) -> dict[str, dict]:
        out = {}
        for coin in coins:
            try:
                out[coin] = indicators(self.closes(coin))
                out[coin].update(intraday(self.hourly(coin)))
            except (MarketError, IndexError, KeyError, ValueError, ZeroDivisionError) as err:
                log.warning("%s: %s", coin, err)
        if not out:
            raise MarketError("Keine Kursdaten erhältlich")
        return out


STABLE = {"USDT", "USDC", "DAI", "EURC", "EURT", "PYUSD", "TUSD", "USDS", "FDUSD", "USDE", "USDD", "EUR", "USD", "GBP",
          "CHF", "EURQ", "EURR", "RLUSD", "USDG", "PAXG", "XAUT"}


def intraday(closes: list[float]) -> dict:
    """Short-term view from hourly candles."""
    if len(closes) < 15:
        return {}
    price = closes[-1]
    gains = losses = 0.0
    for a, b in zip(closes[-15:-1], closes[-14:]):
        gains += max(b - a, 0)
        losses += max(a - b, 0)
    return {"chg_3h": _pct(price, closes[-4]), "chg_24h": _pct(price, closes[-25] if len(closes) > 25 else closes[0]),
            "rsi14_1h": round(100.0 if losses == 0 else 100 - 100 / (1 + gains / losses), 1)}


def _pct(a: float, b: float) -> float:
    return round((a / b - 1) * 100, 2) if b else 0.0


def indicators(closes: list[float]) -> dict:
    if len(closes) < 15:
        raise ValueError("zu wenig Kursdaten")
    price = closes[-1]

    def back(n):
        return closes[-1 - n] if len(closes) > n else closes[0]

    def sma(n):
        part = closes[-n:]
        return sum(part) / len(part)

    gains = losses = 0.0
    for a, b in zip(closes[-15:-1], closes[-14:]):
        change = b - a
        gains += max(change, 0)
        losses += max(-change, 0)
    rsi = 100.0 if losses == 0 else 100 - 100 / (1 + gains / losses)
    rets = [b / a - 1 for a, b in zip(closes[-31:-1], closes[-30:]) if a]
    mean = sum(rets) / len(rets)
    vol = math.sqrt(sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)) * math.sqrt(365) * 100
    high30 = max(closes[-30:])
    return {
        "price": float(f"{price:.6g}"), "chg_1d": _pct(price, back(1)), "chg_7d": _pct(price, back(7)),
        "chg_30d": _pct(price, back(30)), "chg_90d": _pct(price, closes[0]),
        "vs_sma20": _pct(price, sma(20)), "vs_sma50": _pct(price, sma(min(50, len(closes)))),
        "rsi14": round(rsi, 1), "vol_annual": round(vol, 1), "below_30d_high": _pct(price, high30),
    }
