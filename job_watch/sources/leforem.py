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

# Noms de champs confirmés en interrogeant l'API en direct (voir
# debug_sources.py). Ce dataset ne contient pas de description libre :
# la recherche plein texte ne porte donc que sur l'intitulé de poste tel
# qu'écrit par l'employeur, le métier (nomenclature), le secteur, etc. —
# des mots-clés très techniques ("python"...) peuvent ne renvoyer aucun
# résultat même si des offres pertinentes existent, d'où le filtrage de
# la localisation fait ici côté client plutôt qu'ajouté à la recherche
# plein texte (qui devenait alors presque toujours vide).
FIELD_TITLE = "titreoffre"
FIELD_COMPANY = "nomemployeur"
FIELD_LOCALITE = "lieuxtravaillocalite"
FIELD_REGION = "lieuxtravailregion"
FIELD_URL = "url"
FIELD_CONTRACT = "typecontrat"
FIELD_PUBLISHED = "datedebutdiffusion"


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


class LeForemSource(JobSource):
    name = "leforem"

    def search(self, criteria: dict) -> list[Job]:
        lieu = criteria.get("lieu", "")
        max_resultats = criteria.get("max_resultats", 20)
        params = {
            "dataset": DATASET,
            "q": criteria.get("mots_cles", ""),
            # On récupère davantage de lignes que demandé car une partie
            # sera écartée par le filtre de localisation ci-dessous.
            "rows": min(max(max_resultats * 5, 20), 100),
        }

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

        lieu_norm = _normalize(lieu) if lieu else ""

        jobs: list[Job] = []
        for record in payload.get("records", []):
            fields = record.get("fields", {})
            title = fields.get(FIELD_TITLE, "")
            if not title:
                continue

            localite = fields.get(FIELD_LOCALITE, "")
            region = fields.get(FIELD_REGION, "")
            if lieu_norm and lieu_norm not in _normalize(f"{localite} {region}"):
                continue

            jobs.append(
                Job(
                    source=self.name,
                    title=title,
                    company=fields.get(FIELD_COMPANY, "") or "Employeur non précisé",
                    location=localite or region or lieu,
                    url=fields.get(FIELD_URL, ""),
                    contract_type=fields.get(FIELD_CONTRACT, ""),
                    published_at=fields.get(FIELD_PUBLISHED, ""),
                    raw_id=record.get("recordid", ""),
                )
            )
            if len(jobs) >= max_resultats:
                break

        if not jobs:
            print(
                "[leforem] Aucune offre trouvée. Si vos mots-clés sont très "
                "techniques (ex: un nom de langage de programmation), "
                "essayez un terme plus général comme 'développeur' ou "
                "'informatique' : ce dataset ne recherche que l'intitulé de "
                "poste, pas une description détaillée des compétences."
            )
        return jobs
