"""Faz backup do save do Elden Ring. FECHE O JOGO antes.

    python scripts/backup_save.py
    python scripts/backup_save.py --nome frascos-de-vida    # dá um nome ao backup

Os backups ficam em saves/ (fora do git).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl import saves  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nome", default="", help="rótulo opcional, ex.: frascos-de-vida")
    args = parser.parse_args()

    if saves.game_running():
        print("O Elden Ring está aberto. Feche o jogo e rode de novo.")
        sys.exit(1)
    src = saves.game_save_dir()
    dest = saves.backup(args.nome)
    print(f"Save copiado de {src}")
    print(f"Backup criado em {dest}")
    for f in sorted(dest.iterdir()):
        print(f"   {f.name}  ({f.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
