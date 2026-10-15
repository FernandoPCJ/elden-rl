"""Gráficos de evolução do treino a partir de runs/<run>/episodes.csv.

    python scripts/07_analyze.py --run treino01

Gera runs/<run>/analise.png com três painéis (média móvel por episódio):
  - dano causado ao chefe (a métrica que mais importa no começo);
  - duração da luta (sobreviver mais tempo também é aprender);
  - retorno (soma das recompensas).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

RUNS = Path(__file__).resolve().parents[1] / "runs"


def rolling(xs: list[float], w: int) -> list[float]:
    out, acc = [], 0.0
    for i, x in enumerate(xs):
        acc += x
        if i >= w:
            acc -= xs[i - w]
        out.append(acc / min(i + 1, w))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True)
    parser.add_argument("--window", type=int, default=20)
    args = parser.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = RUNS / args.run / "episodes.csv"
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["outcome"] in ("death", "victory", "timeout")]
    if not rows:
        raise SystemExit(f"Nenhum episódio completo em {path}")

    ep = list(range(1, len(rows) + 1))
    dmg = [float(r["damage_dealt"]) * 100 for r in rows]
    dur = [float(r["duration_s"]) for r in rows]
    ret = [float(r["total_reward"]) for r in rows]
    wins = sum(r["outcome"] == "victory" for r in rows)
    w = args.window

    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for ax, ys, title, unit in ((axes[0], dmg, "Dano causado ao chefe", "% da barra"),
                                (axes[1], dur, "Duração da luta", "segundos"),
                                (axes[2], ret, "Retorno do episódio", "recompensa")):
        ax.scatter(ep, ys, s=8, color="#9ca3af", label="episódio")
        ax.plot(ep, rolling(ys, w), color="#c2410c", lw=2, label=f"média móvel ({w})")
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_ylabel(unit)
        ax.grid(alpha=0.3)
    axes[0].legend(loc="upper left", fontsize=8)
    axes[2].set_xlabel("episódio")
    fig.suptitle(f"{args.run}: {len(rows)} lutas, {wins} vitória(s)", x=0.01, ha="left")
    fig.tight_layout()
    out = RUNS / args.run / "analise.png"
    fig.savefig(out, dpi=120)

    half = len(rows) // 2 or 1
    print(f"{len(rows)} lutas, {wins} vitória(s)")
    print(f"Dano médio: primeira metade {sum(dmg[:half]) / half:.1f}% | "
          f"segunda metade {sum(dmg[half:]) / max(1, len(dmg) - half):.1f}%")
    print(f"Lutas com algum dano: {sum(d > 1 for d in dmg)} de {len(dmg)}")
    print(f"Gráfico em {out}")


if __name__ == "__main__":
    main()
