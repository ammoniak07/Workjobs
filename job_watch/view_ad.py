"""Fenêtre autonome affichant une offre d'emploi dans l'application,
plutôt que dans le navigateur externe. Lancée dans un processus séparé
par gui.py (un navigateur embarqué ne peut pas partager la boucle
d'événements de Tkinter dans le même processus).

Usage interne :
    python -m job_watch.view_ad "<url>" "<titre>"
"""
from __future__ import annotations

import sys
import webbrowser


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage : python -m job_watch.view_ad <url> [titre]")
        return

    url = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "Offre d'emploi"

    try:
        import webview
    except ImportError:
        print(
            "[view_ad] Le module 'pywebview' n'est pas installé "
            "(pip install pywebview) : ouverture dans le navigateur par défaut."
        )
        webbrowser.open(url)
        return

    webview.create_window(title[:80], url, width=1100, height=800)
    webview.start()


if __name__ == "__main__":
    main()
