from __future__ import annotations

import copy
from pathlib import Path

import yaml

DEFAULT_CONFIG: dict = {
    "candidat": {"nom": "", "email": "", "telephone": "", "cv_path": ""},
    "recherche": {
        "mots_cles": "",
        "lieu": "",
        "type_contrat": "",
        "max_resultats_par_source": 20,
    },
    "sources": {
        "leforem": {"active": True},
        "indeed": {"active": True, "domaine": "fr.indeed.com"},
        "linkedin": {"active": True},
    },
    "sites_personnalises": [],
    "dossier_brouillons": "job_watch/drafts",
    "fichier_suivi": "job_watch/seen_jobs.json",
}


def default_config() -> dict:
    return copy.deepcopy(DEFAULT_CONFIG)


def load_config(path: Path) -> dict:
    """Charge config.yaml, complété par les valeurs par défaut pour toute
    clé de premier niveau manquante (utile après une mise à jour de l'app
    qui ajoute une nouvelle section, ex: sites_personnalises)."""
    config = default_config()
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        config.update(loaded)
    return config


def save_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def build_active_sources(config: dict) -> list:
    from .sources import SOURCE_CLASSES, GenericSource

    active = []
    for name, cfg in (config.get("sources") or {}).items():
        if cfg and cfg.get("active") and name in SOURCE_CLASSES:
            active.append(SOURCE_CLASSES[name](cfg))
    for site in config.get("sites_personnalises") or []:
        if site.get("active", True):
            active.append(GenericSource(site))
    return active
