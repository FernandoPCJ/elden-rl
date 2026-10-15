"""Etapa 4: um agente que escolhe ações AO ACASO luta contra o chefe.

Serve para validar o ambiente inteiro antes de treinar: observação, ações, recompensa,
morte, reset e gravação. Rode como administrador, com o personagem na Estaca de Marika:

    python scripts/05_random_agent.py --episodes 3

Não precisa de PyTorch. O agente aleatório quase sempre morre, e é isso que esperamos.
Resultados em runs/random_agent/ (vídeos de todas as lutas e episodes.csv).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl.env import ACTION_NAMES, BossDefeated  # noqa: E402
from elden_rl.factory import make_env  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "runs" / "random_agent"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    print("Clique na janela do jogo. Começando em 3 s... (Ctrl+C para parar)")
    time.sleep(3)
    env = make_env(OUT, keep_every=1)
    rng = np.random.default_rng(args.seed)
    try:
        for ep in range(args.episodes):
            obs, _ = env.reset()
            assert env.observation_space.contains(obs), "observação fora do formato declarado"
            total, steps, done, t0 = 0.0, 0, False, time.time()
            actions: Counter = Counter()
            rewards = []
            while not done:
                a = int(rng.integers(env.action_space.n))
                obs, r, term, trunc, info = env.step(a)
                actions[ACTION_NAMES[a]] += 1
                rewards.append(r)
                total += r
                steps += 1
                done = term or trunc
            dur = time.time() - t0
            end = info["event"] or ("tempo esgotado" if trunc else "?")
            print(f"\nEpisódio {ep + 1}: {end}, {steps} passos em {dur:.1f} s "
                  f"({steps / dur:.1f} passos/s), retorno {total:+.2f}")
            print(f"   maior recompensa num passo {max(rewards):+.2f}, menor {min(rewards):+.2f}")
            print(f"   chefe terminou com {info['values'].get('boss_hp', 0):.0%}")
    except BossDefeated as exc:
        print(f"\n{exc}")
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        env.close()
    print(f"\nVídeos e episodes.csv em {OUT}")


if __name__ == "__main__":
    main()
