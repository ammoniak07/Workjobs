from __future__ import annotations

import re
from email.message import EmailMessage
from pathlib import Path

from .models import Job

TEMPLATE_PATH = Path(__file__).parent / "templates" / "email_template.txt"

DEFAULT_MOTIVATION = (
    "[Décrivez ici en 2-3 phrases votre profil, votre expérience pertinente "
    "et votre motivation pour ce poste. Adaptez ce paragraphe à chaque offre "
    "avant envoi, ou enregistrez un texte par défaut dans l'onglet "
    "\"Vos informations\".]"
)


def _slugify(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:max_len] or "offre"


def render_draft(job: Job, candidat: dict) -> tuple[str, str]:
    """Construit (objet, corps) du brouillon à partir du template."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template.format(
        title=job.title,
        company=job.company or "l'entreprise",
        location=job.location or "lieu non précisé",
        source=job.source,
        url=job.url or "(lien indisponible)",
        candidat_nom=candidat.get("nom", ""),
        candidat_email=candidat.get("email", ""),
        candidat_telephone=candidat.get("telephone", ""),
        motivation=candidat.get("motivation", "").strip() or DEFAULT_MOTIVATION,
    )
    subject_line, _, body = rendered.partition("\n")
    subject = subject_line.replace("Objet : ", "", 1).strip()
    return subject, body.strip("\n")


def save_draft(job: Job, candidat: dict, drafts_dir: str | Path) -> Path:
    """Génère un fichier .eml (ouvrable dans n'importe quel client mail)
    contenant le brouillon prêt à relire, compléter et envoyer.

    Le champ "À" est volontairement laissé vide : les offres scrapées
    n'exposent en général pas d'adresse e-mail directe du recruteur, il
    faut la récupérer via le lien de l'offre ou le formulaire du site.
    """
    subject, body = render_draft(job, candidat)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = candidat.get("email", "")
    msg["To"] = ""  # à compléter manuellement avant envoi
    msg.set_content(body)

    cv_path = candidat.get("cv_path")
    if cv_path:
        cv_file = Path(cv_path)
        if cv_file.exists():
            data = cv_file.read_bytes()
            maintype, _, subtype = (
                "application/pdf".partition("/")
                if cv_file.suffix.lower() == ".pdf"
                else ("application", "/", "octet-stream")
            )
            msg.add_attachment(
                data, maintype=maintype, subtype=subtype, filename=cv_file.name
            )
        else:
            print(f"[emailer] CV introuvable, non joint : {cv_file}")

    drafts_dir = Path(drafts_dir)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_slugify(job.source)}_{_slugify(job.company)}_{_slugify(job.title)}_{job.id}.eml"
    out_path = drafts_dir / filename
    out_path.write_bytes(bytes(msg))
    return out_path
