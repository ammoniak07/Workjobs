"""Interface graphique de Workjobs, en pywebview (comme NovaVox) plutôt
qu'en Tkinter : toute l'interface est une page HTML/JS affichée dans une
fenêtre pywebview, ce qui permet d'afficher l'aperçu d'une annonce dans
une vraie iframe (moteur Edge/WebView2 complet, JavaScript inclus) sans
les limitations rencontrées avec Tkinter + tkinterweb.

Lancement :
    python -m job_watch.webapp
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import webview  # noqa: E402

from job_watch.config import build_active_sources, load_config, save_config  # noqa: E402
from job_watch.emailer import save_draft  # noqa: E402
from job_watch.models import Job  # noqa: E402
from job_watch.store import SeenStore  # noqa: E402

CONFIG_PATH = Path(__file__).parent / "config.yaml"
WEBGUI_DIR = Path(__file__).parent / "webgui"


def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source": job.source,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "description": job.description,
        "contract_type": job.contract_type,
    }


class Api:
    def __init__(self) -> None:
        self.config = load_config(CONFIG_PATH)
        self.jobs_by_id: dict[str, Job] = {}
        self.window = None  # renseigné juste après webview.create_window()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def get_config(self) -> dict:
        return self.config

    def save_config(self, config: dict) -> bool:
        self.config = config
        save_config(CONFIG_PATH, config)
        return True

    def browse_cv(self):
        if not self.window:
            return None
        result = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=("Fichiers PDF (*.pdf)", "Tous les fichiers (*.*)"),
        )
        return result[0] if result else None

    def open_drafts_folder(self) -> bool:
        drafts_dir = Path(self.config.get("dossier_brouillons", "job_watch/drafts"))
        drafts_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(drafts_dir)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(drafts_dir)])
        else:
            subprocess.run(["xdg-open", str(drafts_dir)])
        return True

    def reset_history(self) -> bool:
        seen_path = Path(self.config.get("fichier_suivi", "job_watch/seen_jobs.json"))
        if seen_path.exists():
            seen_path.unlink()
        return True

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------
    def start_search(self) -> bool:
        threading.Thread(target=self._search_worker, daemon=True).start()
        return True

    def _search_worker(self) -> None:
        config = self.config
        active_sources = build_active_sources(config)
        if not active_sources:
            self._call_js("onLog", "Aucune source active (sections 'sources' / 'sites_personnalises').")
            self._call_js("onSearchDone", [])
            return

        store = SeenStore(config.get("fichier_suivi", "job_watch/seen_jobs.json"))
        recherche = config.get("recherche", {})
        criteria = {
            "mots_cles": recherche.get("mots_cles", ""),
            "lieu": recherche.get("lieu", ""),
            "max_resultats": recherche.get("max_resultats_par_source", 20),
        }
        type_contrat = recherche.get("type_contrat", "")

        all_jobs: list[Job] = []
        for source in active_sources:
            self._call_js("onLog", f"Recherche sur {source.name}...")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                found = source.search(criteria)
            for line in buffer.getvalue().splitlines():
                self._call_js("onLog", line)
            self._call_js("onLog", f"  -> {len(found)} offre(s) trouvée(s)")
            all_jobs.extend(found)

        seen_ids: set[str] = set()
        new_jobs: list[Job] = []
        for job in all_jobs:
            if job.id in seen_ids or store.has(job.id):
                continue
            if type_contrat and type_contrat.lower() not in f"{job.contract_type} {job.description}".lower():
                continue
            seen_ids.add(job.id)
            new_jobs.append(job)

        self.jobs_by_id = {job.id: job for job in new_jobs}
        self._call_js("onSearchDone", [_job_to_dict(j) for j in new_jobs])

    def _call_js(self, func_name: str, payload) -> None:
        if not self.window:
            return
        try:
            self.window.evaluate_js(f"{func_name}({json.dumps(payload)})")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Actions sur une offre
    # ------------------------------------------------------------------
    def prepare_draft(self, job_id: str) -> dict:
        job = self.jobs_by_id.get(job_id)
        if not job:
            return {"ok": False, "error": "Offre introuvable (relancez une recherche)."}
        candidat = self.config.get("candidat", {})
        drafts_dir = self.config.get("dossier_brouillons", "job_watch/drafts")
        store = SeenStore(self.config.get("fichier_suivi", "job_watch/seen_jobs.json"))
        try:
            path = save_draft(job, candidat, drafts_dir)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        store.mark(job.id, "brouillon_prepare", url=job.url)
        return {"ok": True, "path": str(path)}

    def skip(self, job_id: str) -> dict:
        job = self.jobs_by_id.get(job_id)
        if not job:
            return {"ok": False}
        store = SeenStore(self.config.get("fichier_suivi", "job_watch/seen_jobs.json"))
        store.mark(job.id, "ignoree", url=job.url)
        return {"ok": True}

    def open_full(self, url: str, title: str) -> dict:
        if not url:
            return {"ok": False, "error": "Cette offre n'a pas de lien enregistré."}
        try:
            webview.create_window((title or "Offre d'emploi")[:80], url, width=1100, height=800)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def main() -> None:
    api = Api()
    window = webview.create_window(
        "Workjobs — recherche d'emploi",
        str(WEBGUI_DIR / "index.html"),
        js_api=api,
        width=1200,
        height=800,
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    main()
