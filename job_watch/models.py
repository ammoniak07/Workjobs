from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Job:
    """Une offre d'emploi normalisée, quelle que soit sa source."""

    source: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    contract_type: str = ""
    published_at: str = ""
    raw_id: str = ""

    @property
    def id(self) -> str:
        """Identifiant stable utilisé pour le suivi des offres déjà vues."""
        base = self.raw_id or self.url or f"{self.source}:{self.title}:{self.company}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
