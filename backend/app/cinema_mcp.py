"""Bounded public Cinve reads. Never exposes accounts, prices, seats or purchases."""
import copy
import json
import re
import time
import logging
from datetime import date

import httpx
from .config import settings

PUBLIC_TOOLS = frozenset({'list_providers', 'list_cities', 'list_cinemas', 'list_movies', 'get_showtimes'})
PROVIDERS = ('cinepic', 'cinesunidos', 'cinex', 'supercines', 'grancine')
_FIELDS = {
    'provider': 20, 'city': 80, 'near': 120, 'query': 120, 'cinema_id': 100,
    'movie_id': 100, 'date': 10, 'limit': 20, 'offset': 100000,
}
_ALLOWED = {
    'list_providers': set(),
    'list_cities': {'provider', 'query', 'limit', 'offset'},
    'list_cinemas': {'provider', 'city', 'near', 'query', 'limit', 'offset'},
    'list_movies': {'provider', 'city', 'cinema_id', 'movie_id', 'date', 'query', 'limit', 'offset'},
    'get_showtimes': {'provider', 'city', 'cinema_id', 'movie_id', 'date', 'query', 'limit', 'offset'},
}
_CACHE: dict[str, tuple[float, dict]] = {}


class CinemaUnavailable(Exception):
    pass


def validate_args(name: str, args: dict) -> dict:
    if name not in PUBLIC_TOOLS or not isinstance(args, dict) or set(args) - _ALLOWED[name]:
        raise CinemaUnavailable('Unsupported public query')
    out = {k: v for k, v in args.items() if v is not None and v != ''}
    if name != 'list_providers' and out.get('provider') not in PROVIDERS:
        raise CinemaUnavailable('Choose a supported provider')
    for k, v in out.items():
        if k in ('offset', 'limit'):
            if type(v) is not int or not (int(k == 'limit') <= v <= _FIELDS[k]):
                raise CinemaUnavailable('Invalid paging')
        elif not isinstance(v, str) or len(v) > _FIELDS[k] or any(ord(c) < 32 for c in v):
            raise CinemaUnavailable('Invalid query field')
        if k in ('cinema_id', 'movie_id') and not re.fullmatch(r'[a-zA-Z0-9._-]{1,100}', v):
            raise CinemaUnavailable('Invalid provider ID')
        if k == 'cinema_id' and v.startswith('directory-'):
            raise CinemaUnavailable('Unverified cinema ID')
        if k == 'date':
            try:
                date.fromisoformat(v)
            except ValueError as exc:
                raise CinemaUnavailable('Invalid date') from exc
    if name != 'list_providers':
        out.setdefault('limit', 12)
    return out


def parse_response(text: str, expected_id: int = 1) -> dict:
    frames = []
    for frame in text.replace('\r\n', '\n').split('\n\n'):
        data = '\n'.join(line[5:].lstrip() for line in frame.splitlines() if line.startswith('data:'))
        if data:
            frames.append(data)
    candidates = frames or [text]
    for raw in candidates:
        msg = json.loads(raw)
        if msg.get('id') != expected_id:
            continue
        if 'error' in msg:
            raise CinemaUnavailable('Cinve query failed')
        res = msg.get('result', {})
        if res.get('isError'):
            raise CinemaUnavailable('Cinve query failed')
        data = res.get('structuredContent')
        if data is None:
            value = ''.join(c.get('text', '') for c in res.get('content', []) if c.get('type') == 'text')
            data = json.loads(value)
        if not isinstance(data, dict):
            raise CinemaUnavailable('Unexpected result')
        return data
    raise CinemaUnavailable('No matching response')


async def call_tool(name: str, args: dict, client: httpx.AsyncClient | None = None) -> dict:
    args = validate_args(name, args)
    key = name + json.dumps(args, sort_keys=True)
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < settings.cinema_cache_seconds:
        return copy.deepcopy(hit[1])
    own = client is None
    client = client or httpx.AsyncClient(timeout=settings.cinema_timeout_seconds, follow_redirects=False)
    try:
        async with client.stream('POST', settings.cinema_mcp_url,
                headers={'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'},
                json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                      'params': {'name': name, 'arguments': args}}) as resp:
            resp.raise_for_status()
            chunks, size = [], 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > 256000:
                    raise CinemaUnavailable('Result too large')
                chunks.append(chunk)
        data = parse_response(b''.join(chunks).decode('utf-8'))
    except (httpx.HTTPError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise CinemaUnavailable('Unable to read Cinve') from exc
    finally:
        if own:
            await client.aclose()
    logging.getLogger('sabi.cinema').info('cinema_tool_result tool=%s provider=%s status=%s items=%s partial=%s', name, args.get('provider', ''), data.get('status',''),len(data.get('items',[])),bool(data.get('partial')))
    if data.get('status') not in (None, 'available', 'partial'):
        raise CinemaUnavailable('Provider unavailable')
    if len(_CACHE) >= 128:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = (time.monotonic(), copy.deepcopy(data))
    return data


def llm_tool_specs() -> list[dict]:
    descs = {
        'list_providers': 'Capacidades y límites de cada proveedor. No es una comprobación de salud en vivo.',
        'list_cities': 'Ciudades del proveedor; usa sus nombres para la siguiente consulta.',
        'list_cinemas': 'Sedes del proveedor; city/near ubican. Usa IDs verificados, nunca directory-*.',
        'list_movies': 'Películas. Cinepic requiere cinema_id; Cines Unidos city. Cinex es catálogo general, no prueba función local.',
        'get_showtimes': 'Funciones verificadas por proveedor y fecha. Cinepic requiere cinema_id; Cines Unidos city; Cinex city/cinema_id/movie_id. Conserva partial, warnings y fuentes.',
    }
    specs = []
    for name in sorted(PUBLIC_TOOLS):
        props = {}
        for k in sorted(_ALLOWED[name]):
            props[k] = ({'type': 'integer', 'minimum': int(k == 'limit'), 'maximum': _FIELDS[k]}
                        if k in ('offset', 'limit') else {'type': 'string', 'maxLength': _FIELDS[k]})
        if 'provider' in props:
            props['provider']['enum'] = list(PROVIDERS)
        specs.append({'name': name, 'description': descs[name], 'input_schema': {
            'type': 'object', 'properties': props, 'required': ['provider'] if props else [],
            'additionalProperties': False}})
    return specs
