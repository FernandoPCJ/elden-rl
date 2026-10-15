import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elden_rl.controls import Controller  # noqa: E402
from elden_rl.reset import ResetConfig, ResetRoutine  # noqa: E402


class FakeIO:
    def __init__(self):
        self.log = []

    def keyDown(self, k):
        self.log.append(("down", k))

    def keyUp(self, k):
        self.log.append(("up", k))


class FakeGame:
    """Simula: renascimento -> tela preta -> Estaca -> anda -> névoa (E) -> chefe."""

    def __init__(self, io, confirm_key="e"):
        self.io, self.t, self.phase, self.walked = io, 0.0, "prompt", 0.0
        self.confirm_key = confirm_key
        self.seen = 0

    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += s
        new = self.io.log[self.seen:]
        self.seen = len(self.io.log)
        held = set()
        for kind, k in self.io.log:
            held.add(k) if kind == "down" else held.discard(k)
        if self.phase == "prompt" and ("down", self.confirm_key) in new:
            self.phase, self.load_until = "black", self.t + 2
        elif self.phase == "black" and self.t >= self.load_until:
            self.phase = "stake"
        elif self.phase == "stake":
            if "w" in held:
                self.walked += s
            if self.walked >= 3 and ("down", "e") in new:
                self.phase = "boss"

    def observe(self):
        full = {"player_hp": 1.0, "player_fp": 1.0, "player_stamina": 1.0, "boss_hp": 0.0}
        if self.phase == "prompt":
            return {k: 0.0 for k in full}, "respawn_prompt"
        if self.phase == "black":
            return {k: 0.0 for k in full}, "black"
        if self.phase == "boss":
            return {**full, "boss_hp": 1.0}, "game"
        return full, "game"


def make(confirm_key="e"):
    io = FakeIO()
    keys = {"forward": "w", "interact": "e", "confirm": "enter", "lock_on": "q"}
    game = FakeGame(io, confirm_key)
    ctl = Controller(keys, backend=io, sleep=lambda s: None)  # toques instantâneos no teste
    r = ResetRoutine(game.observe, ctl, ResetConfig(timeout=30), clock=game.clock,
                     sleep=game.sleep, log=lambda m: None)
    return r, io, game


class ResetTest(unittest.TestCase):
    def test_reaches_boss_and_locks_on(self):
        r, io, game = make()
        self.assertTrue(r.run())
        self.assertIn(("down", "q"), io.log)
        self.assertEqual(game.phase, "boss")

    def test_falls_back_to_enter(self):
        r, io, game = make(confirm_key="enter")
        self.assertTrue(r.run())
        self.assertIn(("down", "enter"), io.log)

    def test_releases_keys_at_end(self):
        r, io, _ = make()
        r.run()
        held = set()
        for kind, k in io.log:
            held.add(k) if kind == "down" else held.discard(k)
        self.assertEqual(held, set())


if __name__ == "__main__":
    unittest.main()
