"""Localiza a janela do Elden Ring e captura a área do jogo (sem a borda da janela).

Só funciona no Windows. A captura usa ``mss``, que é rápida o bastante para ~30 fps.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

import numpy as np

WINDOW_TITLE = "ELDEN RING"


def _make_dpi_aware() -> None:
    """Sem isso, com a escala do Windows em 125%/150%, as coordenadas saem erradas."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # por monitor
    except Exception:  # Windows antigo
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


@dataclass
class Region:
    left: int
    top: int
    width: int
    height: int

    def as_mss(self) -> dict:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}


def find_game_window(title: str = WINDOW_TITLE) -> int:
    """Devolve o handle da janela cujo título contém ``title`` (sem diferenciar maiúsculas)."""
    import win32gui

    found: list[int] = []

    def _check(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and title.lower() in win32gui.GetWindowText(hwnd).lower():
            found.append(hwnd)

    win32gui.EnumWindows(_check, None)
    if not found:
        raise RuntimeError(
            f"Janela com '{title}' no título não encontrada. O jogo está aberto e em modo janela?"
        )
    return found[0]


def client_region(hwnd: int) -> Region:
    """Área útil da janela (sem barra de título e bordas), em coordenadas de tela."""
    import win32gui

    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    sx, sy = win32gui.ClientToScreen(hwnd, (left, top))
    return Region(sx, sy, right - left, bottom - top)


class GameCapture:
    """Captura quadros da janela do jogo como arrays BGR (formato do OpenCV)."""

    def __init__(self, title: str = WINDOW_TITLE):
        import mss

        _make_dpi_aware()
        self.hwnd = find_game_window(title)
        self.region = client_region(self.hwnd)
        self._sct = mss.mss()

    def refresh_region(self) -> Region:
        """Chame se a janela for movida."""
        self.region = client_region(self.hwnd)
        return self.region

    def grab(self) -> np.ndarray:
        shot = np.asarray(self._sct.grab(self.region.as_mss()))  # BGRA
        return shot[:, :, :3].copy()

    def focus(self) -> None:
        """Traz o jogo para frente: as teclas simuladas só chegam à janela em foco."""
        import win32gui

        win32gui.SetForegroundWindow(self.hwnd)
