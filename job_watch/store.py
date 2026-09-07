from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class SeenStore:
    """Suivi persistant (JSON) des offres déjà traitées, pour ne jamais
    reproposer deux fois la même offre entre deux exécutions."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def has(self, job_id: str) -> bool:
        return job_id in self._data

    def mark(self, job_id: str, status: str, **extra) -> None:
        self._data[job_id] = {
            "status": status,
            "date": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
