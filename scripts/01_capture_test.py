"""Etapa 1: capturar a janela do Elden Ring e ler as barras do HUD.

Rode no PowerShell, com o jogo aberto em modo janela (o script não aperta nenhuma tecla):

    python scripts/01_capture_test.py --screenshot     # salva um quadro com grade, para calibrar
    python scripts/01_capture_test.py --calibrate      # com vida e vigor CHEIOS: grava o tamanho das barras
    python scripts/01_capture_test.py --seconds 30     # lê as barras em tempo real enquanto você joga
    python scripts/01_capture_test.py --seconds 10 --frames   # + recortes do HUD para diagnóstico

Saídas em ``runs/capture/``: ``grade.png`` (quadro com grade de coordenadas) e
``leitura.png`` (quadro com as regiões das barras e os valores lidos).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl.events import EpisodeTracker  # noqa: E402
from elden_rl.hud import CONFIG_PATH, HUD, draw_grid, screen_state  # noqa: E402
from elden_rl.window import GameCapture  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "runs" / "capture"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--screenshot", action="store_true")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--delay", type=float, default=3, help="segundos para você voltar ao jogo")
    parser.add_argument("--frames", action="store_true",
                        help="salva recortes do HUD a cada 0,2 s em runs/capture/seq/ (diagnóstico)")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cap = GameCapture()
    r = cap.region
    print(f"Janela encontrada: {r.width}x{r.height} na posição ({r.left}, {r.top})")
    if (r.width, r.height) != (1280, 720):
        print("Aviso: o recomendado é janela de 1280x720 (Sistema > Gráficos no jogo).")
    hud = HUD.load()

    print(f"Clique na janela do jogo. Começando em {args.delay:.0f} s...")
    time.sleep(args.delay)
    frame = cap.grab()

    if args.screenshot:
        cv2.imwrite(str(OUT / "grade.png"), draw_grid(frame))
        cv2.imwrite(str(OUT / "leitura.png"), hud.draw(frame))
        print(f"Salvos {OUT / 'grade.png'} e {OUT / 'leitura.png'}")
        return

    if args.calibrate:
        sizes = hud.calibrate_full(frame)
        hud.save()
        cv2.imwrite(str(OUT / "leitura.png"), hud.draw(frame))
        print(f"Barras cheias medidas (pixels): {sizes}")
        print(f"Configuração gravada em {CONFIG_PATH}")
        if any(v < 20 for v in sizes.values()):
            print("Aviso: barra muito curta. As regiões provavelmente estão fora do lugar; "
                  "mande o grade.png para ajustar o hud_config.json.")
        return

    print("Lendo as barras (Ctrl+C para parar). Cada linha mostra o valor atual e o MÍNIMO")
    print("visto desde a linha anterior, para pegar quedas rápidas como a do vigor ao rolar.")
    t0, n, last = time.time(), 0, time.time()
    seq_dir, last_seq, seq_i = OUT / "seq", 0.0, 0
    if args.frames:
        seq_dir.mkdir(parents=True, exist_ok=True)
        for old in seq_dir.glob("*.png"):
            old.unlink()
    tracker = EpisodeTracker()
    names = {"boss_start": "LUTA COMEÇOU", "death": "MORTE", "victory": "VITÓRIA",
             "respawn_prompt": "TELA DE RENASCIMENTO"}
    lows: dict[str, float] = {}
    lowest: dict[str, tuple[float, object]] = {}
    hidden = 0
    try:
        while time.time() - t0 < args.seconds:
            frame = cap.grab()
            values = hud.read(frame)
            n += 1
            event = tracker.update(values, screen_state(frame), time.time())
            if event:
                print(f"  >>> {names[event]} ({time.time() - t0:.1f} s)")
            if args.frames and time.time() - last_seq >= 0.2:
                h, w = frame.shape[:2]
                crop = hud.draw(frame)[: int(0.12 * h), : int(0.55 * w)]
                cv2.imwrite(str(seq_dir / f"{seq_i:03d}.png"), crop)
                seq_i, last_seq = seq_i + 1, time.time()
            if not hud.hud_visible(values):
                hidden += 1
            else:
                for k, v in values.items():
                    lows[k] = min(lows.get(k, 1.0), v)
                    if k != "boss_hp" and v < lowest.get(k, (1.01, None))[0]:
                        lowest[k] = (v, frame)
            if time.time() - last >= 0.5:
                fps = n / (time.time() - t0)
                parts = [f"{k}={values[k]:4.0%} (mín {lows.get(k, values[k]):4.0%})" for k in values]
                extra = f"  [HUD oculto em {hidden} quadros]" if hidden else ""
                print("  " + "  ".join(parts) + f"  ({fps:.0f} fps){extra}")
                last, lows, hidden = time.time(), {}, 0
    except KeyboardInterrupt:
        pass
    for k, (v, f) in lowest.items():
        if f is not None and v < 0.99:
            cv2.imwrite(str(OUT / f"minimo_{k}.png"), hud.draw(f))
            print(f"Menor {k}: {v:.0%} (quadro salvo em runs/capture/minimo_{k}.png)")
    cv2.imwrite(str(OUT / "leitura.png"), hud.draw(frame))
    print(f"Último quadro com as leituras em {OUT / 'leitura.png'}")


if __name__ == "__main__":
    main()
