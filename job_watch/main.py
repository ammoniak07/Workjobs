from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_watch.config import build_active_sources, load_config  # noqa: E402
from job_watch.emailer import render_draft, save_draft  # noqa: E402
from job_watch.store import SeenStore  # noqa: E402


def matches_contract_type(job, type_contrat: str) -> bool:
    if not type_contrat:
        return True
    haystack = f"{job.contract_type} {job.description}".lower()
    return type_contrat.lower() in haystack


def prompt_decision(job) -> str:
    print("\n" + "-" * 70)
    print(f"[{job.source}] {job.title}")
    print(f"  Entreprise : {job.company or '(non précisée)'}")
    print(f"  Lieu       : {job.location or '(non précisé)'}")
    print(f"  Lien       : {job.url or '(indisponible)'}")
    print("-" * 70)
    while True:
        answer = input(
            "Préparer un brouillon de candidature pour cette offre ? "
            "[o]ui / [n]on / [q]uitter : "
        ).strip().lower()
        if answer in ("o", "oui", "y", "yes"):
            return "oui"
        if answer in ("n", "non", "no"):
            return "non"
        if answer in ("q", "quit", "quitter"):
            return "quitter"
        print("Réponse non reconnue, tapez o, n ou q.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            Scanne plusieurs sites d'offres d'emploi (Le Forem, Indeed,
            LinkedIn, plus tout site personnalisé ajouté dans config.yaml)
            selon les critères de config.yaml, et pour chaque
            nouvelle offre propose de préparer un brouillon de candidature
            (fichier .eml) dans le dossier de brouillons. Aucun e-mail
            n'est jamais envoyé automatiquement : c'est vous qui relisez,
            complétez le destinataire et envoyez depuis votre messagerie.
            """
        )
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Chemin du fichier de configuration (défaut : job_watch/config.yaml)",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        example = config_path.parent / "config.example.yaml"
        sys.exit(
            f"Fichier de config introuvable : {config_path}\n"
            f"Copiez {example} vers {config_path} puis personnalisez-le "
            "(ou utilisez l'interface graphique : python -m job_watch.gui)."
        )
    config = load_config(config_path)
    candidat = config.get("candidat", {})
    recherche = config.get("recherche", {})
    criteria = {
        "mots_cles": recherche.get("mots_cles", ""),
        "lieu": recherche.get("lieu", ""),
        "max_resultats": recherche.get("max_resultats_par_source", 20),
    }
    type_contrat = recherche.get("type_contrat", "")

    store = SeenStore(config.get("fichier_suivi", "job_watch/seen_jobs.json"))
    drafts_dir = config.get("dossier_brouillons", "job_watch/drafts")

    active_sources = build_active_sources(config)
    if not active_sources:
        sys.exit(
            "Aucune source active dans config.yaml (sections 'sources' / "
            "'sites_personnalises')."
        )

    all_jobs = []
    for source in active_sources:
        print(f"Recherche sur {source.name}...")
        found = source.search(criteria)
        print(f"  -> {len(found)} offre(s) trouvée(s)")
        all_jobs.extend(found)

    new_jobs = [
        job
        for job in all_jobs
        if not store.has(job.id) and matches_contract_type(job, type_contrat)
    ]

    if not new_jobs:
        print("\nAucune nouvelle offre correspondant aux critères.")
        return

    prepared, skipped = 0, 0
    for job in new_jobs:
        decision = prompt_decision(job)
        if decision == "quitter":
            break
        if decision == "oui":
            subject, body = render_draft(job, candidat)
            print("\n--- Aperçu du brouillon ---")
            print(f"Objet : {subject}\n")
            print(body)
            print("--- Fin de l'aperçu ---\n")
            path = save_draft(job, candidat, drafts_dir)
            store.mark(job.id, "brouillon_prepare", url=job.url)
            prepared += 1
            print(f"Brouillon enregistré : {path}")
        else:
            store.mark(job.id, "ignoree", url=job.url)
            skipped += 1

    print(
        f"\nTerminé. {prepared} brouillon(s) préparé(s) dans "
        f"{drafts_dir}/, {skipped} offre(s) ignorée(s)."
    )
    print(
        "Pensez à relire chaque brouillon, compléter le destinataire "
        "et personnaliser le paragraphe de motivation avant envoi."
    )


if __name__ == "__main__":
    main()
