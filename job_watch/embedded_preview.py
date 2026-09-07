"""Intègre une vraie fenêtre WebView2 (moteur Edge/Chromium) dans un
widget Tkinter, via l'API Win32 SetParent.

DÉSACTIVÉ : les versions récentes de pywebview (>= 6.x) refusent
explicitement de démarrer leur boucle d'événements ailleurs que sur le
thread principal ("pywebview must be run on a main thread"), qui est
déjà occupé par la boucle Tkinter dans cette application. Il n'y a pas
de contournement propre sans inverser l'architecture complète de l'app
(faire tourner Tkinter dans un thread secondaire et laisser pywebview
posséder le thread principal) — trop risqué à faire sans machine Windows
pour tester. `is_supported()` retourne donc toujours False ; le code
ci-dessous est conservé au cas où une future version de pywebview
assouplirait cette contrainte.

Windows uniquement (nécessite pywebview avec le backend "edgechromium",
et pywin32 pour manipuler les fenêtres natives).
"""
from __future__ import annotations

import sys
import threading
import time

_loop_started = False
_windows: dict[str, object] = {}


def is_supported() -> bool:
    return False and sys.platform.startswith("win")


def _ensure_loop_started() -> None:
    global _loop_started
    if _loop_started:
        return
    import webview

    threading.Thread(
        target=lambda: webview.start(gui="edgechromium"), daemon=True
    ).start()
    _loop_started = True
    # Laisse le temps à la boucle d'événements de pywebview de démarrer
    # avant la première création de fenêtre.
    time.sleep(0.3)


def _find_hwnd(window, title: str) -> int | None:
    # Tentative 1 : chemin interne connu du backend edgechromium.
    try:
        return window.gui.windows[window.uid].Handle.ToInt32()
    except Exception:
        pass
    # Tentative 2 : retrouver la fenêtre native par son titre (fenêtre
    # créée avec un titre suffisamment distinctif pour être fiable).
    try:
        import win32gui

        matches: list[int] = []
        win32gui.EnumWindows(
            lambda h, _: matches.append(h)
            if win32gui.GetWindowText(h) == title
            else None,
            None,
        )
        return matches[0] if matches else None
    except Exception:
        return None


def embed(parent_widget, url: str, key: str = "default") -> bool:
    """Affiche `url` dans une fenêtre WebView2 rattachée à `parent_widget`.

    Réutilise la même fenêtre native d'un appel à l'autre pour un même
    `key` (évite de recréer un WebView2 à chaque clic). Retourne True si
    l'intégration a réussi, False si elle a échoué à une étape quelconque
    (l'appelant doit alors utiliser un autre moyen d'affichage)."""
    if not is_supported():
        return False

    try:
        import webview
        import win32con
        import win32gui
    except ImportError:
        return False

    try:
        window = _windows.get(key)
        window_title = f"workjobs-preview-{key}"

        if window is None:
            _ensure_loop_started()
            window = webview.create_window(window_title, url, width=50, height=50)
            _windows[key] = window
            # Attend que la fenêtre native soit réellement créée.
            hwnd = None
            for _ in range(60):
                hwnd = _find_hwnd(window, window_title)
                if hwnd:
                    break
                time.sleep(0.05)
            if not hwnd:
                del _windows[key]
                return False

            parent_hwnd = parent_widget.winfo_id()
            win32gui.SetParent(hwnd, parent_hwnd)
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            style = (style & ~win32con.WS_POPUP & ~win32con.WS_CAPTION) | win32con.WS_CHILD
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
            _windows[f"{key}_hwnd"] = hwnd
            _resize(hwnd, parent_widget)
            parent_widget.bind(
                "<Configure>", lambda _e, h=hwnd, w=parent_widget: _resize(h, w)
            )
        else:
            window.load_url(url)

        return True
    except Exception:
        return False


def _resize(hwnd: int, widget) -> None:
    try:
        import win32gui

        width = widget.winfo_width()
        height = widget.winfo_height()
        if width > 1 and height > 1:
            win32gui.MoveWindow(hwnd, 0, 0, width, height, True)
    except Exception:
        pass
