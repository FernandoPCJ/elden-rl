"""Etapa 3: roteiro de reset, da morte até o começo da luta.

Rode como administrador, em qualquer um destes pontos:
  - na tela "Escolha o local de renascimento";
  - na tela "Você morreu";
  - parado na Estaca de Marika, de frente para a névoa.

    python scripts/03_reset_test.py

O script confirma a Estaca, espera o carregamento, anda até a névoa, atravessa e trava a mira
no chefe. Depois solta as teclas e você assume (ou deixa o chefe te matar para repetir).
Para parar: Ctrl+C.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl.controls import Controller  # noqa: E402
from elden_rl.hud import HUD, screen_state  # noqa: E402
from elden_rl.reset import ResetConfig, ResetRoutine  # noqa: E402
from elden_rl.window import GameCapture  # noqa: E402


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--andar", type=float, default=ResetConfig.walk_after_fog,
                        help="segundos andando depois da névoa antes de travar a mira")
    args = parser.parse_args()
    cap = GameCapture()
    hud = HUD.load()
    ctl = Controller()

    def observe():
        frame = cap.grab()
        return hud.read(frame), screen_state(frame)

    print("Clique na janela do jogo. Começando em 3 s... (Ctrl+C para parar)")
    time.sleep(3)
    try:
        cap.focus()
    except Exception:
        pass
    t0 = time.time()
    ok = ResetRoutine(observe, ctl, ResetConfig(walk_after_fog=args.andar)).run()
    print(f"\nResultado: {'CHEGOU NO CHEFE' if ok else 'NÃO CHEGOU'} em {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
