from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    headline: str
    published_at: datetime
    source: str
    url: str = ""
    summary: str = ""
    symbols: list[str] = field(default_factory=list)
    kind: str | None = None  # None -> classifier decides
    sentiment: float | None = None
    importance: float | None = None
    sector: str = ""
