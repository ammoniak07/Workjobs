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


def _select_nth(scope, selector: str, index: int):
    """Comme select_one, mais permet de choisir la Nième occurrence
    (0 = la première) quand un même sélecteur CSS matche plusieurs
    éléments dans la carte (fréquent sur les sites générés avec des
    classes utilitaires type Tailwind, réutilisées pour plusieurs champs
    différents)."""
    if not selector:
        return None
    matches = scope.select(selector)
    if index < len(matches):
        return matches[index]
    return None


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
      selecteur_carte  : sélecteur CSS du conteneur répété d'une offre.
                          Peut être un sélecteur d'attribut, ex :
                          'a[href*="/offre/"]' quand la carte est elle-même
                          le lien vers l'offre.
      selecteur_titre / selecteur_entreprise / selecteur_lieu / selecteur_lien :
                          sélecteurs CSS relatifs à la carte. Si le même
                          sélecteur matche plusieurs éléments dans la carte
                          (ex: deux <div> avec la même classe, l'un pour
                          l'entreprise, l'autre pour le lieu), ajoutez
                          selecteur_xxx_index (0 = premier, 1 = second...)
                          pour désambiguïser.
                          selecteur_lien peut être laissé vide : dans ce
                          cas, si la carte elle-même est un lien <a>, son
                          href est utilisé directement.
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
        link_sel = self.config.get("selecteur_lien", "")
        title_idx = int(self.config.get("selecteur_titre_index", 0) or 0)
        company_idx = int(self.config.get("selecteur_entreprise_index", 0) or 0)
        location_idx = int(self.config.get("selecteur_lieu_index", 0) or 0)
        link_idx = int(self.config.get("selecteur_lien_index", 0) or 0)
        max_resultats = criteria.get("max_resultats", 20)

        jobs: list[Job] = []
        for card in cards[:max_resultats]:
            title_el = _select_nth(card, title_sel, title_idx)
            company_el = _select_nth(card, company_sel, company_idx)
            location_el = _select_nth(card, location_sel, location_idx)
            link_el = _select_nth(card, link_sel, link_idx) if link_sel else None

            href = None
            if link_el is not None and link_el.get("href"):
                href = link_el["href"]
            elif card.name == "a" and card.get("href"):
                href = card["href"]

            if not title_el or not href:
                continue

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
