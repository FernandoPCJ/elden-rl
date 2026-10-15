"""Envia teclas ao jogo.

Usa ``elden_rl.winput`` (SendInput do Windows com scan codes), o formato que jogos com
DirectInput, como o Elden Ring, reconhecem. As teclas ficam em ``keys.json``, para combinar com os
atalhos configurados no jogo (Sistema > Controles > Teclado).

Para interromper um teste: Ctrl+C no PowerShell (as teclas são soltas no ``finally``).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

KEYS_PATH = Path(__file__).resolve().parents[1] / "keys.json"

# Atalhos sugeridos. Ataques no teclado (e não no mouse) deixam o controle mais simples.
DEFAULT_KEYS = {
    "forward": "w",
    "back": "s",
    "left": "a",
    "right": "d",
    "dodge": "space",
    "attack": "c",       # ataque (R1)
    "heavy": "v",        # ataque forte (R2)
    "guard": "x",        # defender (L1)
    "lock_on": "mouse_middle",  # travar a mira (clique da rodinha, padrão do jogo)
    "flask": "r",        # usar o frasco
    "interact": "e",     # interagir / atravessar a névoa
    "confirm": "enter",  # confirmar em menus (se o "interagir" não servir)
}


def load_keys(path: Path = KEYS_PATH) -> dict[str, str]:
    keys = dict(DEFAULT_KEYS)
    if Path(path).exists():
        keys.update(json.loads(Path(path).read_text()))
    return keys


class Controller:
    """Aperta e solta teclas por nome lógico (``"attack"``, ``"dodge"``...)."""

    def __init__(self, keys: dict[str, str] | None = None, backend=None, sleep=time.sleep):
        self.sleep = sleep
        if backend is None:
            from . import winput as backend  # só funciona no Windows
        self.io = backend
        self.keys = keys or load_keys()
        self.held: set[str] = set()

    def _key(self, action: str) -> str:
        if action not in self.keys:
            raise KeyError(f"Ação {action!r} sem tecla em keys.json")
        return self.keys[action]

    def down(self, action: str) -> None:
        k = self._key(action)
        if k not in self.held:
            self.io.keyDown(k)
            self.held.add(k)

    def up(self, action: str) -> None:
        k = self._key(action)
        if k in self.held:
            self.io.keyUp(k)
            self.held.discard(k)

    def tap(self, action: str, duration: float = 0.06) -> None:
        """Aperta e solta. Toques curtos demais às vezes não são registrados pelo jogo."""
        self.down(action)
        self.sleep(duration)
        self.up(action)

    def hold(self, actions: list[str] | tuple[str, ...], seconds: float) -> None:
        for a in actions:
            self.down(a)
        self.sleep(seconds)
        for a in actions:
            self.up(a)

    def set_held(self, actions: set[str]) -> None:
        """Deixa apertadas exatamente as teclas de ``actions`` (útil para movimento contínuo)."""
        wanted = {self._key(a) for a in actions}
        for k in list(self.held - wanted):
            self.io.keyUp(k)
            self.held.discard(k)
        for k in wanted - self.held:
            self.io.keyDown(k)
            self.held.add(k)

    def release_all(self) -> None:
        for k in list(self.held):
            self.io.keyUp(k)
        self.held.clear()
