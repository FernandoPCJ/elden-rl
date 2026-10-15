"""Etapa 3: gravação das lutas + ciclo completo de reset, com você lutando.

Rode como administrador, com o personagem na Estaca de Marika:

    python scripts/04_record_test.py --minutes 5

O que acontece:
  1. o script leva o personagem até o chefe (reset automático);
  2. você luta normalmente: a luta é gravada em vídeo;
  3. ao morrer, o script confirma a Estaca e leva o personagem de volta ao chefe sozinho;
  4. repete até acabar o tempo.

Saídas em runs/record_test/: videos/epXXXXX_<resultado>.mp4 e episodes.csv.
No teste todas as lutas são guardadas; no treino, só vitórias e uma amostra das derrotas.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl.controls import Controller  # noqa: E402
from elden_rl.events import EpisodeTracker  # noqa: E402
from elden_rl.hud import HUD, screen_state  # noqa: E402
from elden_rl.recorder import EpisodeRecorder  # noqa: E402
from elden_rl.reset import ResetRoutine  # noqa: E402
from elden_rl.window import GameCapture  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "runs" / "record_test"


def ai_view(frame):
    """Provisório: imagem pequena em tons de cinza, como a que a rede vai receber."""
    return cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (96, 96), interpolation=cv2.INTER_AREA)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--minutes", type=float, default=5)
    args = parser.parse_args()

    cap, hud, ctl = GameCapture(), HUD.load(), Controller()
    tracker = EpisodeTracker()
    rec = EpisodeRecorder(OUT, keep_every=1)

    def observe():
        f = cap.grab()
        return hud.read(f), screen_state(f)

    reset = ResetRoutine(observe, ctl)
    print("Clique na janela do jogo. Começando em 3 s... (Ctrl+C para parar)")
    time.sleep(3)
    try:
        cap.focus()
    except Exception:
        pass

    end_at = time.time() + args.minutes * 60
    need_reset = True
    try:
        while time.time() < end_at:
            if need_reset:
                if not reset.run():
                    print("Reset falhou; parando.")
                    break
                tracker.reset()
                need_reset = False
                print("Sua vez: lute! (a luta está sendo gravada)")

            frame = cap.grab()
            values, screen = hud.read(frame), screen_state(frame)
            event = tracker.update(values, screen, time.time())
            if event == "boss_start":
                rec.start()
                print(f"  episódio {rec.episode}: luta começou")
            elif event in ("death", "victory"):
                video = rec.end(event)
                print(f"  episódio {rec.episode}: {'VITÓRIA' if event == 'victory' else 'morte'}"
                      f" -> {video.name if video else 'sem vídeo'}")
                if event == "death":
                    need_reset = True
                else:
                    print("Vitória! Restaure o backup do save para lutar de novo.")
                    break
            rec.add(frame, values, ai_view(frame), action="(humano)")
    except KeyboardInterrupt:
        pass
    finally:
        ctl.release_all()
        rec.end("interrupted")
    print(f"\nVídeos e episodes.csv em {OUT}")


if __name__ == "__main__":
    main()
