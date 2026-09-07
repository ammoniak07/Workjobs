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


class IndeedSource(JobSource):
    """Scraping des pages de résultats publiques d'Indeed.

    Indeed ne propose plus d'API publique et protège ses pages contre les
    robots (Cloudflare, pages de vérification). Cette source peut donc
    retourner 0 résultat ou se faire bloquer sans préavis : ce n'est pas
    un bug de ce script mais une limite connue et documentée dans le
    README. Les sélecteurs CSS sont volontairement regroupés ici pour être
    faciles à corriger si Indeed change sa mise en page.
    """

    name = "indeed"

    def search(self, criteria: dict) -> list[Job]:
        domaine = self.config.get("domaine", "fr.indeed.com")
        url = f"https://{domaine}/jobs"
        params = {
            "q": criteria.get("mots_cles", ""),
            "l": criteria.get("lieu", ""),
        }

        try:
            response = requests.get(
                url, params=params, headers=DEFAULT_HEADERS, timeout=20
            )
        except requests.RequestException as exc:
            print(f"[indeed] Erreur réseau : {exc}")
            return []

        if response.status_code != 200:
            print(
                f"[indeed] Statut HTTP {response.status_code} reçu "
                "(page de vérification anti-robot possible) : source ignorée."
            )
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("div.job_seen_beacon") or soup.select(
            "td.resultContent"
        )
        if not cards:
            print(
                "[indeed] Aucune offre trouvée dans la page : soit il n'y a "
                "pas de résultat, soit Indeed a changé sa mise en page "
                "(sélecteurs CSS à mettre à jour dans job_watch/sources/indeed.py)."
            )
            return []

        max_resultats = criteria.get("max_resultats", 20)
        jobs: list[Job] = []
        for card in cards[:max_resultats]:
            title_el = card.select_one("h2.jobTitle span") or card.select_one(
                "h2.jobTitle"
            )
            company_el = card.select_one("span.companyName")
            location_el = card.select_one("div.companyLocation")
            link_el = card.select_one("h2.jobTitle a") or card.select_one("a")

            if not title_el or not link_el or not link_el.get("href"):
                continue

            href = link_el["href"]
            full_url = href if href.startswith("http") else f"https://{domaine}{href}"

            jobs.append(
                Job(
                    source=self.name,
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "",
                    location=location_el.get_text(strip=True) if location_el else "",
                    url=full_url,
                    raw_id=full_url,
                )
            )
        return jobs
