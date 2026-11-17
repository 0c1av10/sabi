"""Bounded presentation of one restaurant reply. Never changes an order or generates text."""
import re
import unicodedata

NUMBERS={'dos':2,'tres':3,'cuatro':4,'cinco':5}

def requested_parts(body: str) -> int | None:
    from .auth import response_format_request
    if not response_format_request(body):return None
    text=''.join(c for c in unicodedata.normalize('NFD',body.lower()) if unicodedata.category(c)!='Mn')
    match=re.search(r'\ben\s+(dos|tres|cuatro|cinco|[2-5])\s+mensajes?\b',text)
    if not match:return None
    return int(match[1]) if match[1].isdigit() else NUMBERS[match[1]]

def split_reply(text: str, count: int) -> list[str]:
    """Keep content/order, preferring blank-line, then line, then word boundaries.

    May return fewer parts for very short content. No content duplication,
    invented filler, labels, automatic retries or out-of-band destinations.
    """
    if not text.strip():return []
    if count not in range(2,6):return [text]
    # Capture whitespace with its preceding unit so joining restores the text.
    units=re.findall(r'\S.*?(?:\n\s*\n|\Z)',text,flags=re.S)
    if len(units)<count:units=re.findall(r'.+?(?:\n|\Z)',text,flags=re.S)
    if len(units)<count:units=re.findall(r'\S+\s*',text)
    if len(units)<count:return [text]
    # Avoid silently losing leading whitespace in extraction. Whitespace-only
    # edges do not carry message content, and are stripped at send boundaries.
    parts=[];start=0
    for index in range(count-1):
        remaining=count-index
        target=sum(len(u) for u in units[start:])/remaining
        end=start+1
        while end<len(units)-(remaining-1) and abs(sum(len(u) for u in units[start:end+1])-target)<abs(sum(len(u) for u in units[start:end])-target):end+=1
        parts.append(''.join(units[start:end]).strip());start=end
    parts.append(''.join(units[start:]).strip())
    return [part for part in parts if part]
