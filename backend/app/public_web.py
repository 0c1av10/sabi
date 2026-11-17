"""Anonymous public source reader. Requests never carry credentials or user identity.

Every hop uses fresh DNS validation and a TLS socket pinned to a validated IP.
No caller headers, cookies, credentials, proxies, redirects, or arbitrary methods.
A POST is permitted only for Yummy's public search, with a reconstructed body.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qs, urlencode, unquote

HOSTS = {
    'mitickera': frozenset({'mitickera.com', 'www.mitickera.com'}),
    'yummy': frozenset({'yummy-marketplace.com', 'www.yummy-marketplace.com',
                        'api.yummy-marketplace.com', 'upload.yummy-marketplace.com',
                        'firebasestorage.googleapis.com', 'storage.googleapis.com'}),
    'mercadolibre': frozenset({'www.mercadolibre.com.ve', 'listado.mercadolibre.com.ve'}),
}
MAX_BYTES = 3_000_000


class PublicWebError(ValueError):
    pass


def validate_destination(site, url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url) or '\\' in url:
        raise PublicWebError('invalid_url')
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or p.port not in (443, None) or p.username or p.password or p.fragment or p.hostname not in HOSTS.get(site, ()):
            raise PublicWebError('destination_not_allowed')
    except ValueError as exc:
        raise PublicWebError('destination_not_allowed') from exc
    decoded = unquote(p.path)
    if any(x in decoded for x in ('..', '\\', '\x00', '\r', '\n')):
        raise PublicWebError('invalid_path')
    return p


def public_addresses(host):
    records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    ips = tuple(dict.fromkeys(r[4][0] for r in records))
    if not ips or any(not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast or getattr(ipaddress.ip_address(ip), 'ipv4_mapped', None) is not None for ip in ips):
        raise PublicWebError('non_public_dns')
    return ips


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip):
        super().__init__(host, timeout=4, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        # Numeric address prevents a second resolver lookup (DNS rebinding).
        raw = socket.create_connection((self.ip, 443), timeout=self.timeout)
        try:
            if raw.getpeername()[0] != self.ip:
                raise PublicWebError('unexpected_peer')
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def request_policy(site, url, method='GET', body=None, *, query=''):
    p = validate_destination(site, url)
    path = p.path or '/'
    method = method.upper()
    if method == 'POST':
        if site != 'yummy' or p.hostname != 'api.yummy-marketplace.com' or path != '/search/v1/posts' or p.query:
            raise PublicWebError('method_not_allowed')
        if not query or len(query) > 100 or any(ord(c) < 32 for c in query):
            raise PublicWebError('invalid_search')
        try:
            supplied = json.loads(body or '{}')
            if (not isinstance(supplied,dict) or set(supplied)-{'query','page','hitsPerPage','filters'}
                    or supplied.get('query') != query or supplied.get('page',0) != 0
                    or not isinstance(supplied.get('filters',{}),dict)
                    or set(supplied.get('filters',{}))-{'includeBusinessPosts','sortBy','minPrice'}
                    or supplied.get('filters',{}).get('sortBy','relevance') != 'relevance'
                    or supplied.get('filters',{}).get('minPrice',0) != 0):
                raise PublicWebError('search_scope_mismatch')
        except (TypeError,json.JSONDecodeError) as exc:
            raise PublicWebError('invalid_search_body') from exc
        # Do not forward site-generated fields, tokens, identity, location or IDs.
        body = json.dumps({'query': query, 'page': 0, 'hitsPerPage': 12,
                           'filters': {'includeBusinessPosts': True}}).encode()
        return p, body
    if method != 'GET' or body:
        raise PublicWebError('method_not_allowed')
    if site == 'yummy':
        if p.hostname == 'api.yummy-marketplace.com':
            if (path != '/config/get-config' and not re.fullmatch(r'/post/v2/[a-f0-9]{24}',path)) or p.query:
                raise PublicWebError('endpoint_not_allowed')
            return p, None
        if p.hostname == 'firebasestorage.googleapis.com':
            if not re.fullmatch(r'/v0/b/fortodos-1a822\.appspot\.com/o/posts%2F[\w%.-]+', path, re.I):
                raise PublicWebError('image_bucket_not_allowed')
            if not set(parse_qs(p.query)) <= {'alt', 'token'}:
                raise PublicWebError('image_query_not_allowed')
            return p, None
        if p.hostname == 'storage.googleapis.com':
            if not re.fullmatch(r'/fortodos-1a822\.appspot\.com/(?:uploads|bulk-uploads/url-images)/[\w.-]+\.(?:png|jpe?g|webp)', path, re.I) or p.query:
                raise PublicWebError('image_bucket_not_allowed')
            return p, None
        if p.hostname == 'upload.yummy-marketplace.com':
            ok = bool(re.search(r'\.(?:png|jpe?g|webp)(?:$)', path, re.I))
        else:
            ok = (path == '/' or path == '/productos' or bool(re.fullmatch(r'/producto/[a-f0-9]{24}',path)) or
                  bool(re.fullmatch(r'/assets/[\w.-]+\.(?:js|css|woff2?)', path)) or
                  bool(re.fullmatch(r'/(?:icons|brands)/[\w/.-]+\.(?:png|jpe?g|webp|svg)', path)))
            if path == '/productos':
                params = parse_qs(p.query, keep_blank_values=True)
                ok = set(params) <= {'q'} and params.get('q', [''])[0] == query
        if not ok or (path == '/' and p.query):
            raise PublicWebError('endpoint_not_allowed')
    elif site == 'mitickera':
        ok = path in ('/', '/eventos', '/eventos/') or bool(re.fullmatch(r'/wp-content/[\w/.-]+\.(?:css|png|jpe?g|webp|svg|woff2?|ttf)', path, re.I)) or bool(re.fullmatch(r'/wp-includes/[\w/.-]+\.css', path))
        if not ok or p.query and path in ('/', '/eventos', '/eventos/'):
            raise PublicWebError('endpoint_not_allowed')
    elif site == 'mercadolibre':
        if p.hostname != 'listado.mercadolibre.com.ve' or not re.fullmatch(r'/[\w/-]+', path) or p.query:
            raise PublicWebError('endpoint_not_allowed')
    return p, None


@dataclass(frozen=True)
class PublicResponse:
    url: str
    status: int
    content_type: str
    body: bytes
    observed_at: str
    sha256: str


class PublicReader:
    def __init__(self, site, query='', *, max_requests=45, max_total_bytes=15_000_000):
        if site not in HOSTS:
            raise PublicWebError('unknown_site')
        self.site, self.query = site, query
        self.requests = 0
        self.total_bytes = 0
        self.max_requests, self.max_total_bytes = max_requests, max_total_bytes
        self.started = time.monotonic()
        self.cache = {}

    def fetch(self, url, method='GET', body=None):
        import hashlib
        p, safe_body = request_policy(self.site, url, method, body, query=self.query)
        method = method.upper()
        key = (url, method)
        if key in self.cache:
            return self.cache[key]
        if self.requests >= self.max_requests or time.monotonic() - self.started > 14:
            raise PublicWebError('request_budget_exceeded')
        if self.total_bytes >= self.max_total_bytes:
            raise PublicWebError('byte_budget_exceeded')
        self.requests += 1
        ips = public_addresses(p.hostname)
        conn = PinnedHTTPS(p.hostname, ips[0])
        try:
            headers = {'User-Agent': 'Sabi-Public-Pilot/0.1 (anonymous read-only)',
                       'Accept-Encoding': 'identity', 'Accept': '*/*'}
            if safe_body:
                headers['Content-Type'] = 'application/json'
            target = urlunsplit(('', '', p.path or '/', p.query, ''))
            conn.request(method, target, body=safe_body, headers=headers)
            res = conn.getresponse()
            if res.status in (301, 302, 303, 307, 308):
                dest = urljoin(url, res.getheader('Location', ''))
                # One safe explicit redirect, checked again including method/path/DNS.
                if self.requests > 3 or dest == url or method != 'GET':
                    raise PublicWebError('redirect_rejected')
                return self.fetch(dest)
            if res.getheader('Content-Encoding', 'identity') not in ('identity', ''):
                raise PublicWebError('encoded_response_rejected')
            data = res.read(min(MAX_BYTES, self.max_total_bytes - self.total_bytes) + 1)
            if len(data) > min(MAX_BYTES, self.max_total_bytes - self.total_bytes):
                raise PublicWebError('response_too_large')
            self.total_bytes += len(data)
            content_type = res.getheader('Content-Type', '').split(';')[0].strip().lower()
            allowed = {'text/html','text/css','text/javascript','application/javascript','application/json','image/jpeg','image/png','image/webp','image/svg+xml','font/woff','font/woff2','application/font-woff','font/ttf','application/octet-stream'}
            if content_type not in allowed:
                raise PublicWebError('content_type_not_allowed')
            result = PublicResponse(url, res.status, content_type, data,
                                    datetime.now(timezone.utc).isoformat(), hashlib.sha256(data).hexdigest())
            self.cache[key] = result
            return result
        finally:
            conn.close()


class VisibleHTML(HTMLParser):
    """Text/links only. Never execute or interpret page text as instructions."""
    def __init__(self, base):
        super().__init__(); self.base=base; self.text=[]; self.links=[]; self.skip=0; self.a=None
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript'): self.skip += 1
        if tag=='a' and not self.skip: self.a=[urljoin(self.base,attrs.get('href','')),[]]
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'): self.skip=max(0,self.skip-1)
        if tag=='a' and self.a:
            self.links.append({'url':self.a[0],'text':' '.join(self.a[1]).strip()});self.a=None
    def handle_data(self,data):
        if not self.skip and data.strip():
            self.text.append(data.strip())
            if self.a:self.a[1].append(data.strip())
