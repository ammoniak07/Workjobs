from __future__ import annotations

import unicodedata

import requests

from ..models import Job
from .base import JobSource

# API Open Data officielle du Forem (portail Opendatasoft), aucune
# authentification requise : https://www.leforem.be/open-data.html
API_URL = (
    "https://leforem-digitalwallonia.opendatasoft.com/api/records/1.0/search/"
)
DATASET = "offres-d-emploi-forem"


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _pick(fields: dict, *keywords: str) -> str:
    """Cherche dans les champs du dataset une clé contenant un des mots-clés
    donnés (le nom exact des colonnes peut varier légèrement dans le
    catalogue Open Data du Forem, d'où cette recherche tolérante)."""
    for key, value in fields.items():
        norm_key = _normalize(key)
        if any(kw in norm_key for kw in keywords) and value:
            return str(value)
    return ""


class LeForemSource(JobSource):
    name = "leforem"

    def search(self, criteria: dict) -> list[Job]:
        params = {
            "dataset": DATASET,
            "q": criteria.get("mots_cles", ""),
            "rows": criteria.get("max_resultats", 20),
        }
        lieu = criteria.get("lieu")
        if lieu:
            # Recherche géographique approximative en plus du texte libre.
            params["q"] = f"{params['q']} {lieu}".strip()

        try:
            response = requests.get(API_URL, params=params, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"[leforem] Erreur lors de l'appel à l'API Open Data : {exc}")
            return []

        try:
            payload = response.json()
        except ValueError:
            print("[leforem] Réponse inattendue (pas du JSON), source ignorée.")
            return []

        jobs: list[Job] = []
        for record in payload.get("records", []):
            fields = record.get("fields", {})
            title = _pick(fields, "intitule", "titre", "title", "fonction")
            company = _pick(fields, "employeur", "societe", "entreprise", "company")
            location = _pick(fields, "commune", "localite", "lieu", "location")
            url = _pick(fields, "url", "lien", "link")
            description = _pick(fields, "description", "descriptif", "profil")
            contract_type = _pick(fields, "type_contrat", "contrat", "contract")
            published_at = _pick(fields, "date_publication", "date_debut", "date")

            if not title:
                continue

            jobs.append(
                Job(
                    source=self.name,
                    title=title,
                    company=company or "Employeur non précisé",
                    location=location or criteria.get("lieu", ""),
                    url=url,
                    description=description,
                    contract_type=contract_type,
                    published_at=published_at,
                    raw_id=record.get("recordid", ""),
                )
            )
        return jobs
