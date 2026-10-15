"""Diagnóstico: por que as teclas simuladas não chegam ao jogo?

    python scripts/00_input_diag.py

Faz três verificações:
  1. O PowerShell (Python) está rodando como administrador? E o jogo?
  2. O Windows aceita as teclas simuladas? Teste no Bloco de Notas, fora do jogo.
  3. O jogo aceita? Segura W por 1,5 s e mede se a imagem mudou (personagem andando).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl import winput  # noqa: E402
from elden_rl.window import GameCapture  # noqa: E402


def type_text(text: str) -> None:
    for ch in text:
        key = "space" if ch == " " else ch
        winput.keyDown(key)
        time.sleep(0.03)
        winput.keyUp(key)
        time.sleep(0.03)


def frame_change(cap: GameCapture, seconds: float, key: str | None) -> float:
    def small(f):
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)[int(0.15 * f.shape[0]):]
        return cv2.resize(g, (160, 80)).astype(np.float32)

    first = small(cap.grab())
    if key:
        winput.keyDown(key)
    time.sleep(seconds)
    if key:
        winput.keyUp(key)
    return float(np.abs(small(cap.grab()) - first).mean())


def main() -> None:
    print("1) Privilégios")
    py_admin = winput.is_admin()
    print(f"   Python como administrador: {'SIM' if py_admin else 'NÃO'}")
    cap = GameCapture()
    game_admin = winput.process_elevated(cap.hwnd)
    label = {True: "SIM", False: "NÃO", None: "não deu para saber (processo protegido)"}[game_admin]
    print(f"   Jogo como administrador:   {label}")
    if game_admin and not py_admin:
        print("   >>> O jogo tem mais privilégio que o script: o Windows bloqueia as teclas.")
        print("       Abra o PowerShell como administrador (botão direito > Executar como")
        print("       administrador) e rode este diagnóstico de novo.")

    print("\n2) Teste fora do jogo: abra o Bloco de Notas e clique dentro dele.")
    print("   Em 5 s vou digitar 'teste wasd'...")
    time.sleep(5)
    try:
        type_text("teste wasd")
        print("   Teclas enviadas sem erro. Apareceu 'teste wasd' no Bloco de Notas?")
    except winput.SendInputError as exc:
        print(f"   ERRO: {exc}")
        return

    print("\n3) Teste no jogo: clique na janela do jogo (personagem parado, sem inimigos).")
    print("   Em 5 s vou segurar W por 1,5 s...")
    time.sleep(5)
    try:
        cap.focus()
    except Exception:
        pass
    still = frame_change(cap, 1.5, None)
    walk = frame_change(cap, 1.5, "w")
    moved = walk > max(3.0, 2.5 * still)
    print(f"   Mudança na imagem: parado {still:.1f} x segurando W {walk:.1f} -> "
          f"{'O PERSONAGEM ANDOU' if moved else 'nada aconteceu'}")

    print("\nResumo para mandar ao Claude:")
    print(f"   python_admin={py_admin} jogo_admin={game_admin} andou={moved} "
          f"(parado {still:.1f}, W {walk:.1f})")


if __name__ == "__main__":
    main()
