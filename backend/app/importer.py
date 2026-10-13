"""Builds a restaurant storefront from its public website: name, logo, color and menu with prices."""
import html
import ipaddress
import json
import re
import socket
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

UA = "Mozilla/5.0 (compatible; SabiBot/0.1; +https://sabi-ecru.vercel.app)"
MAX_BYTES = 3_000_000
MAX_SCRIPTS = 6
MAX_ITEMS = 80

BASE_MENU = [
    ("Plato del día", 10.0, "Platos", "Edita este plato desde tu panel"),
    ("Bebida natural", 2.5, "Bebidas", "Edita esta bebida desde tu panel"),
    ("Postre de la casa", 4.0, "Postres", "Edita este postre desde tu panel"),
]


def normalize_url(url: str) -> str:
    url = url.strip()
    if url and not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def _is_public(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


async def _get(client: httpx.AsyncClient, url: str) -> str:
    if not _is_public(url):
        return ""
    try:
        r = await client.get(url)
    except httpx.HTTPError:
        return ""
    if r.status_code != 200 or not _is_public(str(r.url)):
        return ""
    return r.text[:MAX_BYTES]


def _meta(doc: str, *keys: str) -> str:
    for k in keys:
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(k)}["\'][^>]*content=["\']([^"\']+)', doc, re.I) \
            or re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{re.escape(k)}["\']', doc, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def _logo(doc: str, base: str) -> str:
    for rel in ("apple-touch-icon", "icon", "shortcut icon"):
        m = re.search(rf'<link[^>]+rel=["\'][^"\']*{rel}[^"\']*["\'][^>]*href=["\']([^"\']+)', doc, re.I) \
            or re.search(rf'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\'][^"\']*{rel}', doc, re.I)
        if m and not m.group(1).startswith("data:"):
            return urljoin(base, m.group(1))
    og = _meta(doc, "og:image")
    return urljoin(base, og) if og else ""


def _title(doc: str) -> str:
    name = _meta(doc, "og:site_name", "og:title")
    if not name:
        m = re.search(r"<title[^>]*>([^<]+)</title>", doc, re.I)
        name = html.unescape(m.group(1)) if m else ""
    return re.split(r"\s+[|\-–—·]\s+", name.strip())[0][:120]


def _clean(name: str) -> str:
    name = html.unescape(re.sub(r"\s+", " ", name)).strip(" -–:·.\t\"'")
    return name[:1].upper() + name[1:] if name else name


def _add(items: dict, name: str, price, category: str = "", desc: str = "", image: str = "") -> None:
    name = _clean(name)
    try:
        price = float(str(price).replace(",", "."))
    except ValueError:
        return
    if not (2 < len(name) <= 70) or not (0 < price < 1000) or len(items) >= MAX_ITEMS:
        return
    if re.search(r"https?:|[{}<>=;]|\\u", name):
        return
    items.setdefault(name.lower(), {"name": name, "price": round(price, 2),
                                    "category": _clean(category)[:60] or "Menú",
                                    "description": _clean(desc)[:200],
                                    "image_url": image if re.match(r"^https?://", image) else ""})


def _from_jsonld(doc: str, items: dict) -> None:
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', doc, re.S | re.I):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        stack = [(data, "")]
        while stack:
            node, cat = stack.pop()
            if isinstance(node, list):
                stack.extend((n, cat) for n in node)
            elif isinstance(node, dict):
                t = node.get("@type", "")
                t = " ".join(t) if isinstance(t, list) else t
                if t in ("MenuSection",):
                    cat = node.get("name", cat)
                offers = node.get("offers")
                if isinstance(offers, list):
                    offers = offers[0] if offers else None
                if t in ("MenuItem", "Product") and isinstance(offers, dict) and offers.get("price"):
                    _add(items, node.get("name", ""), offers["price"], cat, node.get("description", ""))
                stack.extend((v, cat) for v in node.values() if isinstance(v, (dict, list)))


Q = r"[\"'`]"
STR = rf"({Q})([^\"'`\\\\]{{3,70}})\1"
NAME_KEY = r"[\"']?(?:name|nombre|title|titulo)[\"']?\s*:\s*"
OBJ_RE = re.compile(
    NAME_KEY + STR
    + rf"(?:(?!{NAME_KEY})[^{{}}]){{0,300}}?"
    + r"[\"']?(?:price|precio)[\"']?\s*:\s*[\"'`]?\$?\s?(\d{1,4}(?:[.,]\d{1,2})?)",
    re.I,
)
SECTION_RE = re.compile(
    r"[\"']?(?:title|name|nombre|category|categoria|categoría)[\"']?\s*:\s*" + STR
    + r"[^{}\[\]]{0,300}?[\"']?(?:items|platos|products|productos|dishes)[\"']?\s*:\s*\[",
    re.I,
)
CAT_RE = re.compile(r"[\"']?(?:category|categoria|categoría)[\"']?\s*:\s*" + STR, re.I)
IMG_RE = re.compile(r"[\"']?(?:image|img|imagen|photo|foto)[\"']?\s*:\s*([\"'`])([^\"'`\s]{3,300})\1", re.I)
DESC_RE = re.compile(r"[\"']?(?:description|descripcion|descripción|desc)[\"']?\s*:\s*([\"'`])([^\"'`\\\\]{0,200})\1", re.I)
TEXT_RE = re.compile(
    r"^([A-Za-zÁÉÍÓÚÑáéíóúñ½][^$\d\n]{2,60}?)\s*[-–:·.…]*\s*(?:\$|USD|REF\.?)\s?(\d{1,4}(?:[.,]\d{1,2})?)\b"
    r"|^([A-Za-zÁÉÍÓÚÑáéíóúñ½][^$\d\n]{2,60}?)\s*[-–:·.…]*\s*(\d{1,4}[.,]\d{2})\s?(?:\$|USD)",
    re.M,
)


def _from_objects(text: str, items: dict, base: str) -> None:
    sections = [(m.start(), m.group(2)) for m in SECTION_RE.finditer(text)]
    for m in OBJ_RE.finditer(text):
        window = text[m.start():m.end() + 300].split("}", 1)[0]
        cat = CAT_RE.search(window)
        desc = DESC_RE.search(window)
        img = IMG_RE.search(window)
        section = next((name for pos, name in reversed(sections) if pos < m.start()), "")
        _add(items, m.group(2), m.group(3), cat.group(2) if cat else section, desc.group(2) if desc else "",
             urljoin(base, img.group(2)) if img else "")


def _from_text(doc: str, items: dict) -> None:
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", doc, flags=re.S | re.I)
    body = re.sub(r"<br\s*/?>|</(p|li|div|h\d|tr|td|span)>", "\n", body, flags=re.I)
    body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    body = "\n".join(line.strip() for line in body.splitlines() if line.strip())
    for m in TEXT_RE.finditer(body):
        _add(items, m.group(1) or m.group(3), m.group(2) or m.group(4))


async def import_site(url: str) -> Optional[dict]:
    url = normalize_url(url)
    if not url:
        return None
    async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": UA}) as client:
        doc = await _get(client, url)
        if not doc:
            return None
        items: dict = {}
        _from_jsonld(doc, items)
        _from_objects(doc, items, url)
        _from_text(doc, items)
        if len(items) < 3:
            host = urlparse(url).hostname
            srcs = [urljoin(url, s) for s in re.findall(r'<script[^>]+src=["\']([^"\']+)', doc, re.I)]
            for src in [s for s in srcs if urlparse(s).hostname == host][:MAX_SCRIPTS]:
                _from_objects(await _get(client, src), items, url)
    return {
        "name": _title(doc),
        "tagline": _meta(doc, "og:description", "description")[:200],
        "logo_url": _logo(doc, url),
        "brand_color": _meta(doc, "theme-color"),
        "items": list(items.values()),
        "website": url,
    }
