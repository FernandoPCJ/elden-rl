import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elden_rl import saves  # noqa: E402


class SavesTest(unittest.TestCase):
    def test_backup_and_restore_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            game, store = Path(d) / "game", Path(d) / "saves"
            game.mkdir()
            (game / "ER0000.sl2").write_bytes(b"original")
            (game / "ER0000.sl2.bak").write_bytes(b"original-bak")
            b = saves.backup("teste", game_dir=game, saves_dir=store)
            self.assertTrue(b.name.startswith("backup-") and b.name.endswith("-teste"))

            (game / "ER0000.sl2").write_bytes(b"depois-da-vitoria")
            safety = saves.restore(b, game_dir=game, saves_dir=store)
            self.assertEqual((game / "ER0000.sl2").read_bytes(), b"original")
            self.assertEqual((safety / "ER0000.sl2").read_bytes(), b"depois-da-vitoria")
            self.assertEqual(saves.list_backups(store), [b])


if __name__ == "__main__":
    unittest.main()
