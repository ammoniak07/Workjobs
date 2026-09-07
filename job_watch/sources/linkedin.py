from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from ..models import Job
from .base import JobSource

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# Endpoint HTML public utilisé par la pagination "Voir plus d'offres" de
# LinkedIn. Il ne nécessite pas de connexion (donc aucun risque de
# blocage de compte), mais reste non documenté officiellement par
# LinkedIn : sa disponibilité et sa structure peuvent changer sans
# préavis. À utiliser avec modération (pas d'appels en boucle rapprochée).
SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


class LinkedInSource(JobSource):
    name = "linkedin"

    def search(self, criteria: dict) -> list[Job]:
        params = {
            "keywords": criteria.get("mots_cles", ""),
            "location": criteria.get("lieu", ""),
            "start": 0,
        }

        try:
            response = requests.get(
                SEARCH_URL, params=params, headers=DEFAULT_HEADERS, timeout=20
            )
        except requests.RequestException as exc:
            print(f"[linkedin] Erreur réseau : {exc}")
            return []

        if response.status_code != 200:
            print(
                f"[linkedin] Statut HTTP {response.status_code} reçu : "
                "source ignorée (LinkedIn bloque parfois ces requêtes)."
            )
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("div.base-card")
        if not cards:
            print(
                "[linkedin] Aucune offre trouvée : soit pas de résultat, "
                "soit LinkedIn a changé sa mise en page (sélecteurs CSS à "
                "mettre à jour dans job_watch/sources/linkedin.py)."
            )
            return []

        max_resultats = criteria.get("max_resultats", 20)
        jobs: list[Job] = []
        for card in cards[:max_resultats]:
            title_el = card.select_one("h3.base-search-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle")
            location_el = card.select_one("span.job-search-card__location")
            link_el = card.select_one("a.base-card__full-link") or card.select_one(
                "a"
            )

            if not title_el or not link_el or not link_el.get("href"):
                continue

            jobs.append(
                Job(
                    source=self.name,
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "",
                    location=location_el.get_text(strip=True) if location_el else "",
                    url=link_el["href"].split("?")[0],
                    raw_id=link_el["href"].split("?")[0],
                )
            )
        return jobs
