"""Outil d'exploration générique pour trouver les sélecteurs CSS d'un
nouveau site de recherche d'emploi à ajouter à job_watch.

Étape 1 — repérer le conteneur d'une offre :
    python inspect_site.py "URL_DE_RECHERCHE"

Colle-moi le résultat : ça liste les blocs HTML qui se répètent plusieurs
fois sur la page (candidats probables pour "une offre"), avec un aperçu du
texte et du lien qu'ils contiennent.

Étape 2 — une fois qu'on a identifié le bon sélecteur (ex: "div.job-card"),
détailler sa structure interne pour trouver titre/entreprise/lieu :
    python inspect_site.py "URL_DE_RECHERCHE" "div.job-card"

Colle-moi ce deuxième résultat aussi.
"""
from __future__ import annotations

import sys
from collections import Counter

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}


def selector_of(tag) -> str | None:
    classes = tag.get("class") or []
    if not classes:
        return None
    return f"{tag.name}." + ".".join(classes)


def own_or_child_href(tag) -> str:
    if tag.name == "a" and tag.get("href"):
        return tag["href"]
    link = tag.find("a")
    return link.get("href") if link and link.get("href") else "aucun"


def ancestor_chain(tag, depth: int = 4) -> str:
    chain = []
    node = tag.parent
    for _ in range(depth):
        if node is None or not getattr(node, "name", None) or node.name in ("body", "html"):
            break
        sel = selector_of(node) or node.name
        chain.append(sel)
        node = node.parent
    return " < ".join(chain) if chain else "(aucun parent avec classe)"


def step1_find_candidates(soup: BeautifulSoup) -> None:
    counter: Counter[str] = Counter()
    examples = {}
    for tag in soup.find_all(True):
        sel = selector_of(tag)
        if not sel:
            continue
        counter[sel] += 1
        if sel not in examples:
            examples[sel] = tag

    candidates = [(sel, count) for sel, count in counter.items() if 3 <= count <= 200]
    candidates.sort(key=lambda x: -x[1])

    print(
        f"\n{len(candidates)} sélecteur(s) répété(s) (entre 3 et 200 fois). "
        "Les plus probables pour représenter UNE offre :\n"
    )
    for sel, count in candidates[:15]:
        tag = examples[sel]
        text_preview = " | ".join(t.strip() for t in tag.stripped_strings if t.strip())[:200]
        print(f"- {sel}  (x{count})")
        print(f"    lien       : {own_or_child_href(tag)}")
        print(f"    texte      : {text_preview}")
        print(f"    parents    : {ancestor_chain(tag)}")
        print()


def step2_detail_selector(soup: BeautifulSoup, card_selector: str) -> None:
    cards = soup.select(card_selector)
    print(f"\n'{card_selector}' correspond à {len(cards)} élément(s).")
    if not cards:
        return
    card = cards[0]
    print("\nDétail du premier élément trouvé (tag.classe -> texte) :\n")
    seen = set()
    for tag in card.find_all(True):
        own_text = tag.find(string=True, recursive=False)
        own_text = own_text.strip() if own_text else ""
        if not own_text:
            continue
        sel = selector_of(tag) or tag.name
        key = (sel, own_text)
        if key in seen:
            continue
        seen.add(key)
        print(f"  {sel:40s} -> {own_text[:80]}")
    if card.name == "a" and card.get("href"):
        print(f"\nLa carte elle-même est un lien : href={card['href']}")
    links = card.find_all("a")
    print("\nLiens trouvés dans cette carte :")
    for a in links:
        classes = a.get("class") or []
        sel = "a." + ".".join(classes) if classes else "a"
        print(f"  {sel:30s} href={a.get('href')}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    url = sys.argv[1]
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as exc:
        print("ERREUR réseau :", exc)
        return

    print("Statut :", r.status_code)
    print("Longueur HTML :", len(r.text))
    if r.status_code != 200:
        print(
            "Statut non 200 : le contenu ci-dessous est peut-être une page "
            "de blocage/erreur plutôt que les vrais résultats."
        )

    soup = BeautifulSoup(r.text, "html.parser")

    if len(sys.argv) >= 3:
        step2_detail_selector(soup, sys.argv[2])
    else:
        step1_find_candidates(soup)


if __name__ == "__main__":
    main()
