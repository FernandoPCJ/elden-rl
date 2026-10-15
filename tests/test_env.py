import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elden_rl.controls import Controller  # noqa: E402
from elden_rl.env import ACTION_NAMES, BossDefeated, EldenBossEnv, EnvConfig  # noqa: E402


class FakeIO:
    def __init__(self):
        self.log = []

    def keyDown(self, k):
        self.log.append(("down", k))

    def keyUp(self, k):
        self.log.append(("up", k))


class FakeFight:
    """Luta simulada: cada ataque (tecla c) tira 10% do chefe; o chefe tira 20% do
    personagem a cada 2 s; vida 0 vira "Você morreu"."""

    def __init__(self, io, boss_hits_back=True):
        self.io, self.t = io, 0.0
        self.hp, self.boss = 1.0, 1.0
        self.seen = 0
        self.hits_back = boss_hits_back
        self.next_hit = 2.0
        self.resets = 0

    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0.0)
        new = self.io.log[self.seen:]
        self.seen = len(self.io.log)
        for kind, k in new:
            if kind == "down" and k == "c" and self.hp > 0:
                self.boss = max(0.0, round(self.boss - 0.1, 3))
        if self.hits_back and self.hp > 0 and self.boss > 0 and self.t >= self.next_hit:
            self.hp = max(0.0, round(self.hp - 0.2, 3))
            self.next_hit = self.t + 2.0

    def grab(self):
        return np.full((72, 128, 3), int(self.boss * 200), np.uint8)

    def read(self, frame):
        return {"player_hp": self.hp, "player_fp": 1.0, "player_stamina": 1.0,
                "boss_hp": self.boss}


class FakeReset:
    def __init__(self, fight):
        self.fight = fight

    def run(self):
        f = self.fight
        f.hp, f.boss, f.next_hit = 1.0, 1.0, f.t + 2.0
        f.resets += 1
        return True


def make(hits_back=True, recorder=None):
    io = FakeIO()
    fight = FakeFight(io, hits_back)
    ctl = Controller({"forward": "w", "back": "s", "left": "a", "right": "d", "dodge": "space",
                      "attack": "c", "heavy": "v", "guard": "x", "flask": "r"},
                     backend=io, sleep=fight.sleep)
    hud = type("H", (), {"read": staticmethod(fight.read)})()
    env = EldenBossEnv(fight.grab, hud, ctl, FakeReset(fight), lambda f: "game",
                       EnvConfig(max_steps=500), recorder=recorder, clock=fight.clock,
                       sleep=fight.sleep)
    return env, fight, io


class EnvTest(unittest.TestCase):
    def test_spaces_and_obs(self):
        env, _, _ = make()
        obs, info = env.reset(seed=0)
        self.assertTrue(env.observation_space.contains(obs))
        self.assertEqual(obs["image"].shape, (4, 96, 96))
        self.assertEqual(env.action_space.n, len(ACTION_NAMES))

    def test_idle_agent_dies_with_negative_return(self):
        env, fight, _ = make()
        env.reset()
        total, done, steps = 0.0, False, 0
        while not done:
            _, r, term, trunc, info = env.step(0)  # parado
            total += r
            done = term or trunc
            steps += 1
        self.assertEqual(info["event"], "death")
        self.assertLess(total, -5)

    def test_attacking_agent_wins_and_then_reset_refuses(self):
        env, fight, _ = make(hits_back=False)
        env.reset()
        total, done = 0.0, False
        attack = ACTION_NAMES.index("ataque")
        while not done:
            _, r, term, trunc, info = env.step(attack)
            total += r
            done = term or trunc
        self.assertEqual(info["event"], "victory")
        self.assertGreater(total, 25)         # ~ +10 de dano + 20 da vitória
        with self.assertRaises(BossDefeated):
            env.reset()

    def test_dodge_holds_direction_while_tapping(self):
        env, _, io = make()
        env.reset()
        io.log.clear()
        env.step(ACTION_NAMES.index("rolar_esquerda"))
        self.assertEqual(io.log[:3], [("down", "a"), ("down", "space"), ("up", "space")])

    def test_keys_released_on_episode_end(self):
        env, _, io = make()
        env.reset()
        done = False
        while not done:
            _, _, t, tr, _ = env.step(ACTION_NAMES.index("frente"))
            done = t or tr
        held = set()
        for kind, k in io.log:
            held.add(k) if kind == "down" else held.discard(k)
        self.assertEqual(held, set())

    def test_recorder_integration(self):
        from elden_rl.recorder import EpisodeRecorder
        with tempfile.TemporaryDirectory() as d:
            rec = EpisodeRecorder(Path(d), fps=1000, keep_every=1)
            env, _, _ = make(recorder=rec)
            env.reset()
            done = False
            while not done:
                _, _, t, tr, _ = env.step(0)
                done = t or tr
            rows = (Path(d) / "episodes.csv").read_text().splitlines()
            self.assertEqual(len(rows), 2)
            self.assertIn("death", rows[1])


if __name__ == "__main__":
    unittest.main()
