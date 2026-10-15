"""Restaura um backup do save (por exemplo, para "ressuscitar" o chefe depois de uma vitória).
FECHE O JOGO antes.

    python scripts/restore_save.py              # lista os backups e restaura o mais recente
    python scripts/restore_save.py --nome backup-20261012-0940

Antes de restaurar, o save atual é guardado em saves/antes-de-restaurar-<data>.
Lembre: o save guarda TODOS os personagens da conta.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl import saves  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nome", default=None, help="nome da pasta do backup (padrão: o mais recente)")
    parser.add_argument("--sim", action="store_true", help="não pede confirmação")
    args = parser.parse_args()

    backups = saves.list_backups()
    if not backups:
        print("Nenhum backup em saves/. Rode primeiro: python scripts/backup_save.py")
        sys.exit(1)
    print("Backups disponíveis:")
    for b in backups:
        print(f"   {b.name}")
    chosen = saves.SAVES_DIR / args.nome if args.nome else backups[-1]
    if not (chosen / "ER0000.sl2").exists():
        print(f"Backup não encontrado: {chosen.name}")
        sys.exit(1)
    if saves.game_running():
        print("\nO Elden Ring está aberto. Feche o jogo e rode de novo.")
        sys.exit(1)

    print(f"\nVou restaurar: {chosen.name}")
    if not args.sim and input("Confirma? (s/n) ").strip().lower() != "s":
        print("Cancelado.")
        return
    safety = saves.restore(chosen)
    print(f"Pronto. O save anterior foi guardado em {safety.name}")
    print("Se a Steam perguntar sobre conflito de arquivos na nuvem, escolha os arquivos LOCAIS.")


if __name__ == "__main__":
    main()
