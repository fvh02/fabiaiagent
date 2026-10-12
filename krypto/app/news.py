"""Headlines from the news sources the owner chose (RSS/Atom feeds or pages that link one).

Everything read here is data from the internet: it is shown to Claude as such, never as instructions.
"""

import asyncio
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime
from urllib.parse import urljoin, urlparse

import aiohttp

log = logging.getLogger("news")

MAX_BYTES = 3_000_000
PER_SOURCE = 10
TOTAL = 40
UA = {"User-Agent": "Mozilla/5.0 (Home Assistant Krypto-Trader news reader)"}
# Common coin names, so "Ethereum" in a headline counts for ETH; symbols are matched directly.
NAMES = {
    "BTC": "bitcoin", "ETH": "ethereum|ether", "SOL": "solana", "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin",
    "TRX": "tron", "LINK": "chainlink", "AVAX": "avalanche", "DOT": "polkadot", "LTC": "litecoin", "BCH": "bitcoin cash",
    "XLM": "stellar", "TON": "toncoin", "BNB": "binance coin|bnb chain", "SHIB": "shiba inu", "PEPE": "pepe",
    "SUI": "sui", "NEAR": "near protocol", "APT": "aptos", "ARB": "arbitrum", "OP": "optimism", "UNI": "uniswap",
    "AAVE": "aave", "ATOM": "cosmos", "HBAR": "hedera", "ICP": "internet computer", "FIL": "filecoin",
    "INJ": "injective", "RNDR": "render", "RENDER": "render", "FET": "fetch.ai", "WIF": "dogwifhat", "BONK": "bonk",
    "SEI": "sei", "TIA": "celestia", "ALGO": "algorand", "XMR": "monero", "ETC": "ethereum classic", "POL": "polygon",
    "MATIC": "polygon", "ONDO": "ondo", "JUP": "jupiter", "TAO": "bittensor", "KAS": "kaspa", "HYPE": "hyperliquid",
}
# Symbols that are also ordinary words: only their names count.
AMBIGUOUS = {"OP", "SEI", "SUI", "ONE", "NEAR", "ATOM", "LINK", "DOT", "UNI", "GAS", "HOT", "FUN", "BOND", "POL", "MOVE", "ME"}


def domain(url: str) -> str:
    host = (urlparse(url if "://" in url else "https://" + url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _text(el, *names) -> str:
    for name in names:
        found = el.find(name)
        if found is not None and (found.text or "").strip():
            return found.text.strip()
    return ""


def _clean(raw: str, limit: int) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _time(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def parse(body: bytes, source: str) -> list[dict]:
    """Items of an RSS 2.0 or Atom feed."""
    root = ET.fromstring(body)
    for el in root.iter():  # drop namespaces, so RSS and Atom read the same way
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    items = []
    for it in list(root.iter("item")) + list(root.iter("entry")):
        link = _text(it, "link")
        if not link:
            for l in it.findall("link"):
                if l.get("href") and l.get("rel", "alternate") == "alternate":
                    link = l.get("href")
                    break
        title = _clean(_text(it, "title"), 200)
        if not title:
            continue
        items.append({"source": source, "title": title, "link": link if link.startswith(("http://", "https://")) else "",
                      "summary": _clean(_text(it, "description", "summary", "content"), 280),
                      "ts": _time(_text(it, "pubDate", "published", "updated", "date"))})
    return items


async def _get(session: aiohttp.ClientSession, url: str) -> tuple[bytes, str]:
    async with session.get(url, headers=UA, timeout=aiohttp.ClientTimeout(total=20), max_redirects=5) as resp:
        resp.raise_for_status()
        body = await resp.content.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("zu groß")
        return body, resp.headers.get("Content-Type", "")


async def fetch_source(session: aiohttp.ClientSession, url: str) -> list[dict]:
    if "://" not in url:
        url = "https://" + url
    source = domain(url)
    body, ctype = await _get(session, url)
    if "html" in ctype or body.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        # A normal web page: follow the feed it announces.
        match = re.search(rb'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', body, re.I)
        href = re.search(rb'href=["\']([^"\']+)', match.group(0)) if match else None
        if not href:
            raise ValueError("kein RSS-Feed auf der Seite gefunden")
        body, _ = await _get(session, urljoin(url, html.unescape(href.group(1).decode(errors="replace"))))
    return parse(body, source)[:PER_SOURCE]


def tag(items: list[dict], coins: list[str]) -> None:
    """Which of the coins a headline mentions: the symbol in capitals ("SOL") or the coin's name."""
    patterns = {}
    for coin in coins:
        symbol = None if coin in AMBIGUOUS or len(coin) < 3 else re.compile(rf"\b{re.escape(coin)}\b")
        name = re.compile(rf"\b(?:{NAMES[coin]})\b", re.I) if coin in NAMES else None
        if symbol or name:
            patterns[coin] = (symbol, name)
    for item in items:
        text = f"{item['title']} {item['summary']}"
        item["coins"] = [c for c, (symbol, name) in patterns.items()
                         if (symbol and symbol.search(text)) or (name and name.search(text))]


async def collect(session: aiohttp.ClientSession, sources: list[str], coins: list[str], hours: float = 24) -> tuple[list[dict], dict]:
    """The newest headlines of all sources (newest first) and a status per source."""
    results = await asyncio.gather(*(fetch_source(session, s) for s in sources), return_exceptions=True)
    items, status = [], {}
    cutoff = time.time() - hours * 3600
    for src, res in zip(sources, results):
        if isinstance(res, BaseException):
            log.warning("Nachrichtenquelle %s: %s", src, res)
            status[src] = {"ok": False, "error": str(res)[:160] or res.__class__.__name__}
            continue
        fresh = [i for i in res if not i["ts"] or i["ts"] >= cutoff]
        status[src] = {"ok": True, "count": len(fresh)}
        items += fresh
    items.sort(key=lambda i: i["ts"], reverse=True)
    items = items[:TOTAL]
    tag(items, coins)
    for n, item in enumerate(items, 1):
        item["n"] = n
    return items, status
