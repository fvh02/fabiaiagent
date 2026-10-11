"""Search and download free models from Printables (public GraphQL API used by printables.com)."""

import logging
import os
import re

import aiohttp

log = logging.getLogger("printables")

API = os.environ.get("PRINTABLES_API", "https://api.printables.com/graphql/")
SITE = "https://www.printables.com"
MEDIA = os.environ.get("PRINTABLES_MEDIA", "https://media.printables.com/")
HEADERS = {"Content-Type": "application/json", "Accept": "application/json",
           "User-Agent": "Mozilla/5.0 (HomeAssistant druck3d add-on)", "Origin": SITE, "Referer": SITE + "/"}

SEARCH_QUERIES = [
    # Two shapes of the search query, newest first.
    """query Search($query: String!, $limit: Int) {
      result: searchPrints2(query: $query, limit: $limit, printType: print, ordering: best_match) {
        items { id name slug likesCount downloadCount image { filePath } } } }""",
    """query Search($query: String!, $limit: Int) {
      result: searchModels(query: $query, limit: $limit, printType: print, ordering: best_match) {
        items { id name slug likesCount downloadCount image { filePath } } } }""",
]
FILES_QUERY = """query Files($id: ID!) { print(id: $id) { id name slug
  image { filePath }
  stls { id name fileSize }
  gcodes { id name fileSize }
} }"""
LINK_MUTATION = """mutation Link($id: ID!, $printId: ID!, $fileType: DownloadFileTypeEnum!, $source: DownloadSourceEnum!) {
  getDownloadLink(id: $id, printId: $printId, fileType: $fileType, source: $source) {
    ok errors { field messages } output { link } } }"""


class PrintablesError(Exception):
    pass


async def _gql(session: aiohttp.ClientSession, query: str, variables: dict) -> dict:
    async with session.post(API, json={"query": query, "variables": variables}, headers=HEADERS,
                            timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status >= 400:
            raise PrintablesError(f"Printables antwortet mit {resp.status}")
        data = await resp.json(content_type=None)
    if data.get("errors"):
        raise PrintablesError("; ".join(str(e.get("message")) for e in data["errors"])[:300])
    return data.get("data") or {}


def model_id(text: str) -> str | None:
    text = str(text).strip()
    if text.isdigit():
        return text
    m = re.search(r"printables\.com/(?:[a-z-]+/)?model/(\d+)", text)
    return m.group(1) if m else None


def _image(item: dict) -> str | None:
    path = (item.get("image") or {}).get("filePath")
    return MEDIA + path.lstrip("/") if path else None


async def search(session: aiohttp.ClientSession, query: str, limit: int = 5) -> list[dict]:
    last = None
    for q in SEARCH_QUERIES:
        try:
            data = await _gql(session, q, {"query": query, "limit": limit})
        except PrintablesError as err:
            last = err
            continue
        items = ((data.get("result") or {}).get("items")) or []
        return [{
            "id": str(i["id"]), "name": i.get("name"), "likes": i.get("likesCount"),
            "downloads": i.get("downloadCount"), "image": _image(i),
            "url": f"{SITE}/model/{i['id']}-{i.get('slug') or ''}".rstrip("-"),
        } for i in items[:limit]]
    raise PrintablesError(f"Suche bei Printables fehlgeschlagen: {last}")


async def files(session: aiohttp.ClientSession, mid: str) -> dict:
    data = await _gql(session, FILES_QUERY, {"id": mid})
    model = data.get("print")
    if not model:
        raise PrintablesError("Modell nicht gefunden")
    return {
        "id": str(model["id"]), "name": model.get("name"), "image": _image(model),
        "url": f"{SITE}/model/{model['id']}-{model.get('slug') or ''}",
        "stls": [{"id": str(f["id"]), "name": f["name"], "size": f.get("fileSize")} for f in model.get("stls") or []],
        "gcodes": [{"id": str(f["id"]), "name": f["name"]} for f in model.get("gcodes") or []],
    }


async def download_link(session: aiohttp.ClientSession, mid: str, file_id: str, file_type: str = "stl") -> str:
    data = await _gql(session, LINK_MUTATION, {"id": file_id, "printId": mid, "fileType": file_type, "source": "model_detail"})
    result = data.get("getDownloadLink") or {}
    link = (result.get("output") or {}).get("link")
    if not result.get("ok") or not link:
        raise PrintablesError(f"Kein Download-Link: {result.get('errors')}")
    return link
