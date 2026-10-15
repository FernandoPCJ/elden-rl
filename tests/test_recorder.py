import csv
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elden_rl.recorder import EpisodeRecorder, compose  # noqa: E402


class RecorderTest(unittest.TestCase):
    def test_compose_size(self):
        out = compose(np.zeros((720, 1280, 3), np.uint8), np.zeros((96, 96), np.uint8),
                      {"values": {"player_hp": 0.5}, "action": "attack", "reward": 0.1})
        self.assertEqual(out.shape, (430, 1000, 3))

    def test_keeps_victories_and_samples_deaths(self):
        with tempfile.TemporaryDirectory() as d:
            rec = EpisodeRecorder(Path(d), fps=1000, keep_every=2)
            frame = np.zeros((720, 1280, 3), np.uint8)
            outcomes = ["death", "death", "victory"]
            for o in outcomes:
                rec.start()
                for i in range(5):
                    rec.add(frame, {"player_hp": 1.0, "player_stamina": 1.0, "boss_hp": 1 - i / 10},
                            reward=0.5)
                rec.end(o)
            videos = sorted(p.name for p in (Path(d) / "videos").glob("*.mp4"))
            self.assertEqual(videos, ["ep00002_death.mp4", "ep00003_victory.mp4"])
            with open(Path(d) / "episodes.csv", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([r["outcome"] for r in rows], outcomes)
            self.assertAlmostEqual(float(rows[0]["damage_dealt"]), 0.4)
            self.assertAlmostEqual(float(rows[0]["total_reward"]), 2.5)
            # nova sessão continua a numeração
            self.assertEqual(EpisodeRecorder(Path(d)).episode, 3)


if __name__ == "__main__":
    unittest.main()
