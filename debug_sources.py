"""Script de diagnostic pour comprendre pourquoi Le Forem / Indeed renvoient
0 résultat. Lance-le depuis la racine du dépôt Workjobs :

    python debug_sources.py

Il n'a besoin d'aucune config.yaml. Colle-moi la sortie complète.
"""
from __future__ import annotations

import json

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

MOTS_CLES = "développeur python"
LIEU = "Bruxelles"

print("=" * 70)
print("LE FOREM")
print("=" * 70)
url = "https://leforem-digitalwallonia.opendatasoft.com/api/records/1.0/search/"


def try_query(label: str, q: str) -> None:
    params = {"dataset": "offres-d-emploi-forem", "q": q, "rows": 2}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        print(f"\n--- {label} ---")
        print("URL appelée :", r.url)
        print("Statut :", r.status_code)
        data = r.json()
        print("Nombre total (nhits) :", data.get("nhits"))
        if data.get("records"):
            print("Premier record complet (fields) :")
            print(
                json.dumps(
                    data["records"][0].get("fields", {}), ensure_ascii=False, indent=2
                )
            )
        else:
            print("Réponse brute (tronquée) :", json.dumps(data, ensure_ascii=False)[:500])
    except Exception as exc:
        print(f"ERREUR ({label}) :", exc)


try_query("q vide (juste pour voir la taille totale du dataset)", "")
try_query("q = 'python' seul", "python")
try_query("q = mots-clés + lieu combinés (ce que fait le script normalement)", f"{MOTS_CLES} {LIEU}")

print()
print("=" * 70)
print("INDEED")
print("=" * 70)
url = "https://fr.indeed.com/jobs"
params = {"q": MOTS_CLES, "l": LIEU}
try:
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    print("URL appelée :", r.url)
    print("Statut :", r.status_code)
    print("Longueur HTML :", len(r.text))
    lowered = r.text.lower()
    for hint in ["captcha", "verification", "cloudflare", "just a moment", "blocked"]:
        if hint in lowered:
            print(f"  -> contient le mot '{hint}' (probable page de blocage)")
    soup = BeautifulSoup(r.text, "html.parser")
    for sel in ["div.job_seen_beacon", "td.resultContent", "div.jobsearch-SerpJobCard",
                "a.jcs-JobTitle", "h2.jobTitle"]:
        found = soup.select(sel)
        print(f"  sélecteur '{sel}' : {len(found)} élément(s)")
    with open("indeed_debug.html", "w", encoding="utf-8") as f:
        f.write(r.text)
    print("\nHTML complet sauvegardé dans indeed_debug.html")
except Exception as exc:
    print("ERREUR :", exc)
