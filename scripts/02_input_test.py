"""Etapa 2: o script aperta teclas no jogo e confere, pelo HUD, se o jogo obedeceu.

Rode com o personagem na área da Estaca de Marika, FORA da névoa e sem inimigos por perto:

    python scripts/02_input_test.py

O teste: anda para frente e para trás, rola, e ataca. Ataques gastam vigor mesmo fora de
combate, então "o vigor caiu depois do ataque" prova que a tecla chegou ao jogo.
Para interromper a qualquer momento: leve o mouse para um canto da tela.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl.controls import Controller, load_keys  # noqa: E402
from elden_rl.hud import HUD  # noqa: E402
from elden_rl.window import GameCapture  # noqa: E402


def watch(cap: GameCapture, hud: HUD, seconds: float) -> dict[str, float]:
    """Lê o HUD por ``seconds`` e devolve o menor valor de cada barra."""
    lows: dict[str, float] = {}
    end = time.time() + seconds
    while time.time() < end:
        values = hud.read(cap.grab())
        if not hud.hud_visible(values):
            continue
        for k, v in values.items():
            lows[k] = min(lows.get(k, 1.0), v)
    return lows


def motion(cap: GameCapture, seconds: float) -> float:
    """Quanto a imagem muda (0-255) ao longo de ``seconds``, ignorando o HUD do topo.

    Parado, o cenário quase não muda; andando, a câmera acompanha o personagem e a imagem
    inteira se desloca. Serve para saber se a tecla de movimento chegou ao jogo.
    """
    def small(f):
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)[int(0.15 * f.shape[0]):]
        return cv2.resize(g, (160, 80)).astype(np.float32)

    first = small(cap.grab())
    time.sleep(seconds)
    return float(np.abs(small(cap.grab()) - first).mean())


def center_motion(cap: GameCapture, seconds: float) -> float:
    """Mudança da imagem só no centro da tela, onde fica o personagem."""
    def crop(f):
        h, w = f.shape[:2]
        g = cv2.cvtColor(f[int(0.35 * h):int(0.95 * h), int(0.30 * w):int(0.70 * w)], cv2.COLOR_BGR2GRAY)
        return cv2.resize(g, (128, 108)).astype(np.float32)

    first = crop(cap.grab())
    time.sleep(seconds)
    return float(np.abs(crop(cap.grab()) - first).mean())


def main() -> None:
    keys = load_keys()
    print("Teclas em uso:", ", ".join(f"{a}={k}" for a, k in keys.items()))
    cap = GameCapture()
    hud = HUD.load()
    ctl = Controller(keys)

    print("Clique na janela do jogo. Começando em 3 s... (mouse no canto da tela = parar)")
    time.sleep(3)
    try:
        cap.focus()  # garante que as teclas vão para o jogo
    except Exception as exc:  # o Windows às vezes recusa trazer a janela para frente
        print(f"(não consegui focar a janela automaticamente: {exc})")
    results: list[tuple[str, bool, str]] = []
    try:
        base = watch(cap, hud, 0.5)
        if not base:
            print("HUD não encontrado. O jogo está na tela, com o HUD em 'Ligado'?")
            return
        print(f"Início: vida {base['player_hp']:.0%}, vigor {base['player_stamina']:.0%}")

        print("1) Andando para frente 1 s e para trás 1 s")
        still = motion(cap, 1.0)
        ctl.down("forward")
        moving = motion(cap, 1.0)
        ctl.up("forward")
        ctl.hold(["back"], 1.0)
        ok = moving > max(3.0, 2.5 * still)
        results.append(("andar", ok, f"mudança na imagem: parado {still:.1f}, andando {moving:.1f}"))
        print(f"   {'OK' if ok else 'FALHOU'}: imagem parado {still:.1f} x andando {moving:.1f}")
        time.sleep(0.5)

        print("2) Rolando para o lado (confira na tela)")
        ctl.hold(["left"], 0.15)
        ctl.down("left")
        ctl.tap("dodge", 0.08)
        ctl.up("left")
        time.sleep(1.5)

        for action in ("attack", "heavy"):
            print(f"3) Testando '{action}' (tecla {keys[action]})")
            watch(cap, hud, 1.5)                  # espera o vigor encher e o personagem parar
            idle = center_motion(cap, 0.6)
            ctl.tap(action, 0.08)
            swing = center_motion(cap, 0.6)
            lows = watch(cap, hud, 0.8)
            st = lows.get("player_stamina", 1.0)
            # Fora de combate o jogo pode não gastar vigor; o golpe aparece como movimento
            # do personagem no centro da tela.
            ok = st < 0.95 or swing > max(4.0, 2.5 * idle)
            info = f"movimento parado {idle:.1f} x golpe {swing:.1f}, vigor mínimo {st:.0%}"
            results.append((action, ok, info))
            print(f"   {'OK' if ok else 'FALHOU'}: {info}")
            time.sleep(1.0)
    finally:
        ctl.release_all()

    print("\nResumo:")
    for action, ok, info in results:
        print(f"  {action:<7} {'OK' if ok else 'FALHOU'} ({info})")
    walked = next((ok for a, ok, _ in results if a == "andar"), None)
    if walked is False:
        print("\nNem o movimento chegou ao jogo: o problema é o envio de teclas, não os atalhos. "
              "Feche o PowerShell, abra de novo COMO ADMINISTRADOR e rode outra vez.")
    elif walked and not all(ok for _, ok, _ in results):
        print("\nO movimento funcionou, mas os ataques não: confira os atalhos de ataque no jogo.")


if __name__ == "__main__":
    main()
