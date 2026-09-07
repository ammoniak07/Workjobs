"""Interface graphique de Workjobs (Tkinter, inclus avec Python — aucune
dépendance supplémentaire à installer).

Lancement :
    python -m job_watch.gui
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_watch import embedded_preview  # noqa: E402
from job_watch.config import build_active_sources, load_config, save_config  # noqa: E402
from job_watch.emailer import save_draft  # noqa: E402
from job_watch.store import SeenStore  # noqa: E402

try:
    from tkinterweb import HtmlFrame
except ImportError:
    HtmlFrame = None

CONFIG_PATH = Path(__file__).parent / "config.yaml"

SITE_FIELDS = [
    ("nom", "Nom du site"),
    ("url_recherche", "URL de recherche (utilisez {mots_cles} et {lieu})"),
    ("base_url", "URL de base (pour les liens relatifs, optionnel)"),
    ("selecteur_carte", "Sélecteur CSS d'une offre (obligatoire)"),
    ("selecteur_titre", "Sélecteur CSS du titre du poste"),
    ("selecteur_entreprise", "Sélecteur CSS de l'entreprise (optionnel)"),
    ("selecteur_lieu", "Sélecteur CSS du lieu (optionnel)"),
    ("selecteur_lien", "Sélecteur CSS du lien vers l'offre (défaut : a)"),
]


class CustomSiteDialog(tk.Toplevel):
    """Formulaire modal d'ajout/modification d'un site personnalisé."""

    def __init__(self, parent, site: dict | None = None):
        super().__init__(parent)
        self.title("Site personnalisé")
        self.resizable(False, False)
        self.result: dict | None = None
        self.entries: dict[str, tk.Entry] = {}

        site = site or {}
        row = 0
        for key, label in SITE_FIELDS:
            ttk.Label(self, text=label).grid(
                row=row, column=0, sticky="w", padx=8, pady=4
            )
            entry = ttk.Entry(self, width=55)
            entry.insert(0, site.get(key, ""))
            entry.grid(row=row, column=1, padx=8, pady=4)
            self.entries[key] = entry
            row += 1

        self.active_var = tk.BooleanVar(value=site.get("active", True))
        ttk.Checkbutton(self, text="Actif", variable=self.active_var).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )
        row += 1

        btns = ttk.Frame(self)
        btns.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="Enregistrer", command=self._on_save).pack(
            side="left", padx=5
        )
        ttk.Button(btns, text="Annuler", command=self.destroy).pack(
            side="left", padx=5
        )

        self.transient(parent)
        self.grab_set()

    def _on_save(self) -> None:
        nom = self.entries["nom"].get().strip()
        url = self.entries["url_recherche"].get().strip()
        carte = self.entries["selecteur_carte"].get().strip()
        if not nom or not url or not carte:
            messagebox.showerror(
                "Champs manquants",
                "Le nom, l'URL de recherche et le sélecteur CSS d'une "
                "offre sont obligatoires.",
                parent=self,
            )
            return
        self.result = {key: self.entries[key].get().strip() for key, _ in SITE_FIELDS}
        self.result["selecteur_lien"] = self.result["selecteur_lien"] or "a"
        self.result["active"] = self.active_var.get()
        self.destroy()


class JobWatchApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Workjobs — recherche d'emploi")
        self.root.geometry("900x700")

        self.config = load_config(CONFIG_PATH)
        self.job_by_iid: dict[str, object] = {}
        self.search_running = False

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.config_tab = ttk.Frame(notebook)
        self.results_tab = ttk.Frame(notebook)
        notebook.add(self.config_tab, text="Recherche & sites")
        notebook.add(self.results_tab, text="Résultats")

        self._build_config_tab()
        self._build_results_tab()
        self._load_config_into_widgets()

    # ------------------------------------------------------------------
    # Onglet configuration
    # ------------------------------------------------------------------
    def _build_config_tab(self) -> None:
        frame = self.config_tab

        recherche_box = ttk.LabelFrame(frame, text="Recherche")
        recherche_box.pack(fill="x", padx=8, pady=6)

        ttk.Label(recherche_box, text="Poste recherché :").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.mots_cles_var = tk.StringVar()
        ttk.Entry(recherche_box, textvariable=self.mots_cles_var, width=40).grid(
            row=0, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Label(recherche_box, text="Région / ville :").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.lieu_var = tk.StringVar()
        ttk.Entry(recherche_box, textvariable=self.lieu_var, width=40).grid(
            row=1, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Label(recherche_box, text="Type de contrat (optionnel) :").grid(
            row=2, column=0, sticky="w", padx=6, pady=4
        )
        self.type_contrat_var = tk.StringVar()
        ttk.Entry(recherche_box, textvariable=self.type_contrat_var, width=40).grid(
            row=2, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Label(recherche_box, text="Résultats max. par site :").grid(
            row=3, column=0, sticky="w", padx=6, pady=4
        )
        self.max_resultats_var = tk.IntVar(value=20)
        ttk.Spinbox(
            recherche_box, from_=1, to=100, textvariable=self.max_resultats_var, width=6
        ).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        sites_box = ttk.LabelFrame(frame, text="Sites intégrés")
        sites_box.pack(fill="x", padx=8, pady=6)

        self.leforem_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sites_box, text="Le Forem", variable=self.leforem_var).grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )

        self.indeed_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sites_box, text="Indeed", variable=self.indeed_var).grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.indeed_domaine_var = tk.StringVar(value="fr.indeed.com")
        ttk.Entry(sites_box, textvariable=self.indeed_domaine_var, width=20).grid(
            row=1, column=1, sticky="w", padx=6, pady=4
        )
        ttk.Label(sites_box, text="(ex: fr.indeed.com ou be.indeed.com)").grid(
            row=1, column=2, sticky="w", padx=6
        )

        self.linkedin_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sites_box, text="LinkedIn", variable=self.linkedin_var).grid(
            row=2, column=0, sticky="w", padx=6, pady=4
        )

        custom_box = ttk.LabelFrame(frame, text="Sites personnalisés")
        custom_box.pack(fill="both", padx=8, pady=6)

        columns = ("nom", "actif", "url")
        self.custom_tree = ttk.Treeview(
            custom_box, columns=columns, show="headings", height=5
        )
        self.custom_tree.heading("nom", text="Nom")
        self.custom_tree.heading("actif", text="Actif")
        self.custom_tree.heading("url", text="URL de recherche")
        self.custom_tree.column("nom", width=120)
        self.custom_tree.column("actif", width=50, anchor="center")
        self.custom_tree.column("url", width=450)
        self.custom_tree.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        custom_btns = ttk.Frame(custom_box)
        custom_btns.pack(side="left", fill="y", padx=6)
        ttk.Button(custom_btns, text="Ajouter...", command=self._add_custom_site).pack(
            fill="x", pady=2
        )
        ttk.Button(
            custom_btns, text="Modifier...", command=self._edit_custom_site
        ).pack(fill="x", pady=2)
        ttk.Button(
            custom_btns, text="Supprimer", command=self._remove_custom_site
        ).pack(fill="x", pady=2)

        candidat_box = ttk.LabelFrame(frame, text="Vos informations")
        candidat_box.pack(fill="x", padx=8, pady=6)

        ttk.Label(candidat_box, text="Nom :").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.nom_var = tk.StringVar()
        ttk.Entry(candidat_box, textvariable=self.nom_var, width=30).grid(
            row=0, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Label(candidat_box, text="Email :").grid(row=0, column=2, sticky="w", padx=6, pady=4)
        self.email_var = tk.StringVar()
        ttk.Entry(candidat_box, textvariable=self.email_var, width=30).grid(
            row=0, column=3, sticky="w", padx=6, pady=4
        )

        ttk.Label(candidat_box, text="Téléphone :").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.telephone_var = tk.StringVar()
        ttk.Entry(candidat_box, textvariable=self.telephone_var, width=30).grid(
            row=1, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Label(candidat_box, text="CV (PDF) :").grid(
            row=1, column=2, sticky="w", padx=6, pady=4
        )
        self.cv_path_var = tk.StringVar()
        ttk.Entry(candidat_box, textvariable=self.cv_path_var, width=30).grid(
            row=1, column=3, sticky="w", padx=6, pady=4
        )
        ttk.Button(
            candidat_box, text="Importer un CV...", command=self._browse_cv
        ).grid(row=1, column=4, padx=6)

        ttk.Label(
            candidat_box, text="Paragraphe de motivation par défaut :"
        ).grid(row=2, column=0, columnspan=4, sticky="w", padx=6, pady=(10, 0))
        ttk.Label(
            candidat_box,
            text=(
                "Utilisé dans chaque brouillon à la place du texte à "
                "compléter. Vous pouvez toujours l'adapter offre par offre "
                "en éditant le fichier .eml généré."
            ),
            foreground="gray",
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=6)
        self.motivation_text = tk.Text(candidat_box, height=4, width=80, wrap="word")
        self.motivation_text.grid(
            row=4, column=0, columnspan=5, sticky="we", padx=6, pady=(2, 6)
        )

        action_box = ttk.Frame(frame)
        action_box.pack(fill="x", padx=8, pady=10)
        ttk.Button(
            action_box, text="Enregistrer la configuration", command=self._save_config
        ).pack(side="left", padx=4)
        self.search_btn = ttk.Button(
            action_box, text="Lancer la recherche", command=self._start_search
        )
        self.search_btn.pack(side="left", padx=4)
        self.status_var = tk.StringVar(value="Prêt.")
        ttk.Label(action_box, textvariable=self.status_var).pack(side="left", padx=12)

    def _browse_cv(self) -> None:
        path = filedialog.askopenfilename(
            title="Choisir votre CV",
            filetypes=[("PDF", "*.pdf"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self.cv_path_var.set(path)

    def _add_custom_site(self) -> None:
        dialog = CustomSiteDialog(self.root)
        self.root.wait_window(dialog)
        if dialog.result:
            self.config.setdefault("sites_personnalises", []).append(dialog.result)
            self._refresh_custom_tree()

    def _edit_custom_site(self) -> None:
        selection = self.custom_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        site = self.config["sites_personnalises"][index]
        dialog = CustomSiteDialog(self.root, site)
        self.root.wait_window(dialog)
        if dialog.result:
            self.config["sites_personnalises"][index] = dialog.result
            self._refresh_custom_tree()

    def _remove_custom_site(self) -> None:
        selection = self.custom_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        del self.config["sites_personnalises"][index]
        self._refresh_custom_tree()

    def _refresh_custom_tree(self) -> None:
        self.custom_tree.delete(*self.custom_tree.get_children())
        for i, site in enumerate(self.config.get("sites_personnalises", [])):
            self.custom_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    site.get("nom", ""),
                    "oui" if site.get("active", True) else "non",
                    site.get("url_recherche", ""),
                ),
            )

    def _load_config_into_widgets(self) -> None:
        recherche = self.config.get("recherche", {})
        self.mots_cles_var.set(recherche.get("mots_cles", ""))
        self.lieu_var.set(recherche.get("lieu", ""))
        self.type_contrat_var.set(recherche.get("type_contrat", ""))
        self.max_resultats_var.set(recherche.get("max_resultats_par_source", 20))

        sources = self.config.get("sources", {})
        self.leforem_var.set(sources.get("leforem", {}).get("active", True))
        self.indeed_var.set(sources.get("indeed", {}).get("active", True))
        self.indeed_domaine_var.set(
            sources.get("indeed", {}).get("domaine", "fr.indeed.com")
        )
        self.linkedin_var.set(sources.get("linkedin", {}).get("active", True))

        candidat = self.config.get("candidat", {})
        self.nom_var.set(candidat.get("nom", ""))
        self.email_var.set(candidat.get("email", ""))
        self.telephone_var.set(candidat.get("telephone", ""))
        self.cv_path_var.set(candidat.get("cv_path", ""))
        self.motivation_text.delete("1.0", "end")
        self.motivation_text.insert("1.0", candidat.get("motivation", ""))

        self._refresh_custom_tree()

    def _collect_config_from_widgets(self) -> dict:
        self.config["recherche"] = {
            "mots_cles": self.mots_cles_var.get().strip(),
            "lieu": self.lieu_var.get().strip(),
            "type_contrat": self.type_contrat_var.get().strip(),
            "max_resultats_par_source": self.max_resultats_var.get(),
        }
        self.config["sources"] = {
            "leforem": {"active": self.leforem_var.get()},
            "indeed": {
                "active": self.indeed_var.get(),
                "domaine": self.indeed_domaine_var.get().strip() or "fr.indeed.com",
            },
            "linkedin": {"active": self.linkedin_var.get()},
        }
        self.config["candidat"] = {
            "nom": self.nom_var.get().strip(),
            "email": self.email_var.get().strip(),
            "telephone": self.telephone_var.get().strip(),
            "cv_path": self.cv_path_var.get().strip(),
            "motivation": self.motivation_text.get("1.0", "end").strip(),
        }
        # sites_personnalises est déjà tenu à jour directement dans self.config
        return self.config

    def _save_config(self) -> None:
        config = self._collect_config_from_widgets()
        save_config(CONFIG_PATH, config)
        self.status_var.set("Configuration enregistrée.")

    # ------------------------------------------------------------------
    # Onglet résultats
    # ------------------------------------------------------------------
    def _build_results_tab(self) -> None:
        frame = self.results_tab

        paned = ttk.PanedWindow(frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=2)
        paned.add(right, weight=3)

        columns = ("source", "titre", "entreprise", "lieu")
        self.results_tree = ttk.Treeview(
            left, columns=columns, show="headings", height=14, selectmode="extended"
        )
        for col, label, width in [
            ("source", "Source", 90),
            ("titre", "Poste", 180),
            ("entreprise", "Entreprise", 130),
            ("lieu", "Lieu", 110),
        ]:
            self.results_tree.heading(col, text=label)
            self.results_tree.column(col, width=width)
        self.results_tree.pack(fill="both", expand=True, padx=8, pady=6)
        self.results_tree.bind("<<TreeviewSelect>>", self._on_select_result)
        self.results_tree.bind("<Double-1>", lambda _e: self._view_selected_ad())

        self.detail_text = tk.Text(left, height=4, wrap="word")
        self.detail_text.pack(fill="x", padx=8, pady=4)
        self.detail_text.configure(state="disabled")

        btns = ttk.Frame(left)
        btns.pack(fill="x", padx=8, pady=4)
        ttk.Button(
            btns, text="Ouvrir en grand", command=self._view_selected_ad
        ).pack(side="left", padx=4)
        ttk.Button(
            btns, text="Préparer un brouillon", command=self._prepare_selected
        ).pack(side="left", padx=4)
        ttk.Button(btns, text="Ignorer", command=self._skip_selected).pack(
            side="left", padx=4
        )
        ttk.Button(
            btns, text="Ouvrir le dossier des brouillons", command=self._open_drafts
        ).pack(side="left", padx=4)
        ttk.Button(
            btns, text="Vider les résultats", command=self._clear_results
        ).pack(side="left", padx=4)
        ttk.Button(
            btns, text="Réinitialiser l'historique", command=self._reset_history
        ).pack(side="left", padx=4)

        ttk.Label(left, text="Journal :").pack(anchor="w", padx=8)
        log_frame = ttk.Frame(left)
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_text = tk.Text(log_frame, height=6, state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(right, text="Aperçu de l'annonce :").pack(anchor="w", padx=4, pady=(4, 0))
        self.preview_frame = ttk.Frame(right)
        self.preview_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.preview = None
        self.preview_mode = None
        preview_error = None

        try:
            if embedded_preview.is_supported() and embedded_preview.embed(
                self.preview_frame, "about:blank", key="results"
            ):
                self.preview_mode = "webview2"
        except Exception:
            pass

        if self.preview_mode is None and HtmlFrame is not None:
            try:
                self.preview = HtmlFrame(
                    self.preview_frame, messages_enabled=False, threading_enabled=True
                )
                self.preview.pack(fill="both", expand=True)
                self.preview.load_html(
                    "<p style='font-family:sans-serif;color:gray;padding:1em'>"
                    "Cliquez sur une offre pour afficher son aperçu ici.</p>"
                )
                self.preview_mode = "tkinterweb"
            except Exception as exc:  # ex: Tkhtml non compilé pour Tcl/Tk 9
                preview_error = str(exc)

        if self.preview_mode is None:
            message = (
                "Aperçu intégré indisponible.\n"
                "Installez : pip install tkinterweb pywebview pywin32\n"
                "En attendant, utilisez \"Ouvrir en grand\"."
                if not preview_error
                else (
                    "Aperçu intégré indisponible sur cette installation de "
                    "Python (composant tkinterweb incompatible avec votre "
                    "version de Tcl/Tk) :\n"
                    f"{preview_error}\n\n"
                    "Utilisez \"Ouvrir en grand\" à la place."
                )
            )
            ttk.Label(
                self.preview_frame,
                text=message,
                foreground="gray",
                justify="left",
                wraplength=350,
            ).pack(padx=12, pady=12, anchor="nw")

    def _on_select_result(self, _event=None) -> None:
        selection = self.results_tree.selection()
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        job = None
        if len(selection) == 1:
            job = self.job_by_iid.get(selection[0])
        if job:
            self.detail_text.insert(
                "end",
                f"Lien : {job.url or '(indisponible)'}\n"
                f"Type de contrat : {job.contract_type or '(non précisé)'}\n"
                f"{job.description}",
            )
        self.detail_text.configure(state="disabled")

        if self.preview_mode == "webview2" and job and job.url:
            try:
                embedded_preview.embed(self.preview_frame, job.url, key="results")
            except Exception as exc:
                self._log(f"Aperçu impossible pour cette offre : {exc}")
        elif self.preview_mode == "tkinterweb" and self.preview is not None:
            if job and job.url:
                try:
                    self.preview.load_url(job.url)
                except Exception as exc:  # tkinterweb peut lever divers types selon la page
                    self._log(f"Aperçu impossible pour cette offre : {exc}")
            elif not job:
                self.preview.load_html(
                    "<p style='font-family:sans-serif;color:gray;padding:1em'>"
                    "Sélectionnez une seule offre pour afficher son aperçu.</p>"
                )

    def _log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _start_search(self) -> None:
        if self.search_running:
            return
        config = self._collect_config_from_widgets()
        save_config(CONFIG_PATH, config)

        active_sources = build_active_sources(config)
        if not active_sources:
            messagebox.showwarning(
                "Aucune source active",
                "Activez au moins un site (intégré ou personnalisé) avant "
                "de lancer une recherche.",
            )
            return

        self.search_running = True
        self.search_btn.configure(state="disabled")
        self.status_var.set("Recherche en cours...")
        self._log("--- Nouvelle recherche ---")

        criteria = {
            "mots_cles": config["recherche"]["mots_cles"],
            "lieu": config["recherche"]["lieu"],
            "max_resultats": config["recherche"]["max_resultats_par_source"],
        }
        type_contrat = config["recherche"]["type_contrat"]

        thread = threading.Thread(
            target=self._search_worker,
            args=(active_sources, criteria, type_contrat, config),
            daemon=True,
        )
        thread.start()

    def _search_worker(self, active_sources, criteria, type_contrat, config) -> None:
        store = SeenStore(config.get("fichier_suivi", "job_watch/seen_jobs.json"))
        buffer = io.StringIO()
        all_jobs = []
        with contextlib.redirect_stdout(buffer):
            for source in active_sources:
                print(f"Recherche sur {source.name}...")
                found = source.search(criteria)
                print(f"  -> {len(found)} offre(s) trouvée(s)")
                all_jobs.extend(found)

        new_jobs = [
            job
            for job in all_jobs
            if not store.has(job.id)
            and (
                not type_contrat
                or type_contrat.lower() in f"{job.contract_type} {job.description}".lower()
            )
        ]

        self.root.after(0, self._on_search_done, new_jobs, buffer.getvalue())

    def _on_search_done(self, jobs, log_output: str) -> None:
        self.search_running = False
        self.search_btn.configure(state="normal")
        self.status_var.set(f"{len(jobs)} nouvelle(s) offre(s) trouvée(s).")
        for line in log_output.splitlines():
            self._log(line)

        self.results_tree.delete(*self.results_tree.get_children())
        self.job_by_iid.clear()
        for i, job in enumerate(jobs):
            iid = str(i)
            self.job_by_iid[iid] = job
            self.results_tree.insert(
                "",
                "end",
                iid=iid,
                values=(job.source, job.title, job.company, job.location),
            )

        if not jobs:
            self._log("Aucune nouvelle offre correspondant aux critères.")

    def _selected_jobs(self):
        return [
            (iid, self.job_by_iid[iid])
            for iid in self.results_tree.selection()
            if iid in self.job_by_iid
        ]

    def _view_selected_ad(self) -> None:
        selected = self._selected_jobs()
        if not selected:
            return
        job = selected[0][1]
        if not job.url:
            messagebox.showinfo(
                "Annonce indisponible", "Cette offre n'a pas de lien enregistré."
            )
            return
        try:
            subprocess.Popen(
                [sys.executable, "-m", "job_watch.view_ad", job.url, job.title]
            )
        except OSError as exc:
            self._log(
                f"Impossible d'ouvrir la fenêtre intégrée ({exc}), "
                "ouverture dans le navigateur par défaut."
            )
            webbrowser.open(job.url)

    def _prepare_selected(self) -> None:
        selected = self._selected_jobs()
        if not selected:
            return
        config = self.config
        candidat = config.get("candidat", {})
        drafts_dir = config.get("dossier_brouillons", "job_watch/drafts")
        store = SeenStore(config.get("fichier_suivi", "job_watch/seen_jobs.json"))

        for iid, job in selected:
            path = save_draft(job, candidat, drafts_dir)
            store.mark(job.id, "brouillon_prepare", url=job.url)
            self._log(f"Brouillon préparé pour « {job.title} » -> {path}")
            self.results_tree.delete(iid)
            del self.job_by_iid[iid]

        messagebox.showinfo(
            "Brouillons préparés",
            f"{len(selected)} brouillon(s) enregistré(s) dans {drafts_dir}/.\n"
            "Relisez-les, complétez le destinataire et personnalisez le "
            "paragraphe de motivation avant envoi.",
        )

    def _skip_selected(self) -> None:
        selected = self._selected_jobs()
        if not selected:
            return
        config = self.config
        store = SeenStore(config.get("fichier_suivi", "job_watch/seen_jobs.json"))
        for iid, job in selected:
            store.mark(job.id, "ignoree", url=job.url)
            self.results_tree.delete(iid)
            del self.job_by_iid[iid]
        self._log(f"{len(selected)} offre(s) ignorée(s).")

    def _open_drafts(self) -> None:
        drafts_dir = Path(self.config.get("dossier_brouillons", "job_watch/drafts"))
        drafts_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(drafts_dir)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(drafts_dir)])
        else:
            subprocess.run(["xdg-open", str(drafts_dir)])

    def _clear_results(self) -> None:
        """Vide la liste affichée sans marquer les offres comme traitées :
        elles pourront réapparaître lors d'une prochaine recherche."""
        self.results_tree.delete(*self.results_tree.get_children())
        self.job_by_iid.clear()
        self._log("Résultats affichés vidés.")

    def _reset_history(self) -> None:
        seen_path = Path(
            self.config.get("fichier_suivi", "job_watch/seen_jobs.json")
        )
        if not seen_path.exists():
            messagebox.showinfo("Historique", "Aucun historique à réinitialiser.")
            return
        if not messagebox.askyesno(
            "Réinitialiser l'historique",
            "Toutes les offres déjà acceptées ou ignorées pourront réapparaître "
            "lors de la prochaine recherche. Continuer ?",
        ):
            return
        seen_path.unlink()
        self._log("Historique des offres déjà traitées réinitialisé.")


def main() -> None:
    root = tk.Tk()
    JobWatchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
