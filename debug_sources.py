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
params = {"dataset": "offres-d-emploi-forem", "q": f"{MOTS_CLES} {LIEU}", "rows": 3}
try:
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    print("URL appelée :", r.url)
    print("Statut :", r.status_code)
    data = r.json()
    print("Nombre total (nhits) :", data.get("nhits"))
    print("Nombre de records reçus :", len(data.get("records", [])))
    if data.get("records"):
        print("\nPremier record complet (fields) :")
        print(json.dumps(data["records"][0].get("fields", {}), ensure_ascii=False, indent=2))
    else:
        print("\nRéponse brute complète (tronquée à 1500 caractères) :")
        print(json.dumps(data, ensure_ascii=False)[:1500])
except Exception as exc:
    print("ERREUR :", exc)

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
