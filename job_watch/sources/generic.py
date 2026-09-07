from __future__ import annotations

from urllib.parse import quote

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


class GenericSource(JobSource):
    """Site d'offres d'emploi ajouté par l'utilisateur (sans code dédié),
    piloté uniquement par des sélecteurs CSS renseignés dans la config.

    Configuration attendue (voir config.example.yaml, section
    'sites_personnalises') :
      nom              : nom affiché de la source
      url_recherche    : URL de recherche avec {mots_cles} et {lieu}
                          comme emplacements à remplacer, ex :
                          "https://exemple.com/emplois?q={mots_cles}&l={lieu}"
      base_url         : préfixe à ajouter si les liens trouvés sont relatifs
      selecteur_carte  : sélecteur CSS du conteneur répété d'une offre
      selecteur_titre  : sélecteur CSS (relatif à la carte) du titre
      selecteur_entreprise : sélecteur CSS de l'entreprise (optionnel)
      selecteur_lieu   : sélecteur CSS du lieu (optionnel)
      selecteur_lien   : sélecteur CSS du lien <a> vers l'offre (défaut "a")
    """

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self.name = source_config.get("nom") or "site_personnalise"

    def search(self, criteria: dict) -> list[Job]:
        url_template = self.config.get("url_recherche", "")
        card_selector = self.config.get("selecteur_carte", "")
        if not url_template or not card_selector:
            print(
                f"[{self.name}] Configuration incomplète "
                "(url_recherche et selecteur_carte sont obligatoires), "
                "source ignorée."
            )
            return []

        url = url_template.format(
            mots_cles=quote(criteria.get("mots_cles", "")),
            lieu=quote(criteria.get("lieu", "")),
        )

        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        except requests.RequestException as exc:
            print(f"[{self.name}] Erreur réseau : {exc}")
            return []

        if response.status_code != 200:
            print(
                f"[{self.name}] Statut HTTP {response.status_code} reçu, "
                "source ignorée."
            )
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select(card_selector)
        if not cards:
            print(
                f"[{self.name}] Aucune offre trouvée : le sélecteur "
                f"'{card_selector}' ne correspond à rien sur la page. "
                "Vérifiez les sélecteurs CSS de ce site."
            )
            return []

        base_url = self.config.get("base_url", "")
        title_sel = self.config.get("selecteur_titre", "")
        company_sel = self.config.get("selecteur_entreprise", "")
        location_sel = self.config.get("selecteur_lieu", "")
        link_sel = self.config.get("selecteur_lien", "a")
        max_resultats = criteria.get("max_resultats", 20)

        jobs: list[Job] = []
        for card in cards[:max_resultats]:
            title_el = card.select_one(title_sel) if title_sel else None
            company_el = card.select_one(company_sel) if company_sel else None
            location_el = card.select_one(location_sel) if location_sel else None
            link_el = card.select_one(link_sel) if link_sel else None

            if not title_el or not link_el or not link_el.get("href"):
                continue

            href = link_el["href"]
            full_url = href if href.startswith("http") else f"{base_url}{href}"

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
