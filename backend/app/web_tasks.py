"""Local-only consumer task model. Not wired to production or live merchant accounts.

Page text is evidence, never permission. A plan cannot grant itself a purchase,
login, payment, send or submission action. Execution currently exists only in the
loopback fixture runner under pilot/: public-site execution remains unimplemented.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import urlsplit
import ipaddress


class TaskState(str, Enum):
    DRAFT = 'draft'
    REVIEW_READY = 'review_ready'
    BLOCKED = 'blocked'


SITES = {
    'mercadolibre': frozenset({'mercadolibre.com.ve', 'www.mercadolibre.com.ve', 'listado.mercadolibre.com.ve'}),
    'yummy': frozenset({'yummy-marketplace.com', 'www.yummy-marketplace.com'}),
    'mitickera': frozenset({'mitickera.com', 'www.mitickera.com', 'portal.mitickera.com'}),
}
ALLOWED_ACTIONS = frozenset({'read', 'fill', 'select', 'screenshot'})


def validate_public_url(site: str, url: str) -> str:
    """Destination allowlist only, NOT an SSRF defense for a network client.

    No live client is enabled. A future worker also needs DNS/IP enforcement,
    redirect and subresource isolation and a review of each site's terms.
    """
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError as exc:
        raise ValueError('invalid_url') from exc
    if (p.scheme != 'https' or p.username or p.password or port not in (None, 443)
            or p.hostname not in SITES.get(site, ()) or p.fragment):
        raise ValueError('destination_not_allowed')
    try:
        ipaddress.ip_address(p.hostname or '')
    except ValueError:
        return url
    raise ValueError('ip_destination_not_allowed')


def validate_action(action: str, field_name: str = '') -> None:
    if action not in ALLOWED_ACTIONS:
        raise ValueError('action_not_allowed')
    if action in {'fill', 'select'} and field_name not in {'query', 'quantity', 'variant'}:
        raise ValueError('field_not_allowed')


@dataclass(frozen=True)
class Evidence:
    url: str
    observed_at: str
    text: str
    environment: str  # fixture, never mislabeled as live


@dataclass
class WebTask:
    site: str
    request: str
    facts: dict[str, str] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    state: TaskState = TaskState.DRAFT
    reason: str = ''

    def update_facts(self, **facts: str) -> None:
        self.facts.update({k: v for k, v in facts.items() if k in {'query', 'quantity', 'variant'} and v})

    def missing(self) -> list[str]:
        # Existing answers survive follow-up messages. This is state, not NLP.
        return [k for k in ('query', 'quantity') if not self.facts.get(k)]

    def record(self, url: str, text: str, *, environment: str) -> None:
        if environment != 'fixture':
            raise ValueError('live_execution_not_enabled')
        self.evidence.append(Evidence(url, datetime.now(timezone.utc).isoformat(), text[:10000], environment))

    def ready_for_review(self) -> None:
        if self.missing() or not self.evidence:
            raise ValueError('insufficient_evidence')
        self.state = TaskState.REVIEW_READY

    def block(self, reason: str) -> None:
        self.state, self.reason = TaskState.BLOCKED, reason

    def summary(self) -> str:
        if self.state == TaskState.REVIEW_READY:
            return ('Prueba local con datos ficticios. Selección lista para revisar; '
                    'no es carrito real, reserva, pedido ni compra. El usuario confirma y paga.')
        if self.state == TaskState.BLOCKED:
            return f'No pude completar la tarea: {self.reason}'
        return 'Tarea en preparación; aún no hay resultado verificado.'
