import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elden_rl.controls import Controller  # noqa: E402
from elden_rl.events import EpisodeTracker  # noqa: E402


def v(hp, fp=1.0, st=1.0, boss=0.0):
    return {"player_hp": hp, "player_fp": fp, "player_stamina": st, "boss_hp": boss}


def run(tracker, segments, fps=20):
    """segments: lista de (segundos, valores, tela). Devolve [(tempo, evento)]."""
    t, events = 0.0, []
    for secs, values, screen in segments:
        for _ in range(int(secs * fps)):
            e = tracker.update(values, screen, t)
            if e:
                events.append((round(t, 2), e))
            t += 1 / fps
    return events


class EventsTest(unittest.TestCase):
    def test_real_fight_then_death(self):
        # sequência parecida com a luta gravada em 12/10/2026
        segs = [
            (5, v(1.0), "game"),
            (5, v(1.0, boss=1.0), "game"),
            (3, v(0.48, boss=0.54), "game"),
            (8, v(0.0, boss=0.54), "game"),          # "Você morreu": vida 0, HUD na tela
            (3, v(0, 0, 0), "black"),
            (2, v(0, 0, 0), "respawn_prompt"),
            (2, v(0, 0, 0), "black"),
            (5, v(1.0), "game"),
        ]
        names = [e for _, e in run(EpisodeTracker(), segs)]
        self.assertEqual(names, ["boss_start", "death", "respawn_prompt"])

    def test_victory(self):
        segs = [(2, v(0.8, boss=0.3), "game"), (1, v(0.8, boss=0.0), "game"),
                (3, v(0.8, boss=0.0), "game")]
        names = [e for _, e in run(EpisodeTracker(), segs)]
        self.assertEqual(names, ["boss_start", "victory"])

    def test_hud_fading_is_not_death(self):
        # quadros de transição: vida 0 por um instante com o resto ainda visível
        segs = [(1, v(1.0), "game"), (0.2, v(0.0, fp=0.9), "game"), (1, v(1.0), "game"),
                (1.0, v(0.0, fp=0.9), "game"), (1, v(0.3), "game")]  # até 1 s com vida 0 não é morte
        self.assertEqual(run(EpisodeTracker(), segs), [])


class FakeIO:
    def __init__(self):
        self.log = []

    def keyDown(self, k):
        self.log.append(("down", k))

    def keyUp(self, k):
        self.log.append(("up", k))


class ControllerTest(unittest.TestCase):
    def test_tap_and_release(self):
        io = FakeIO()
        c = Controller({"attack": "c", "forward": "w"}, backend=io)
        c.tap("attack", 0.0)
        c.set_held({"forward"})
        c.release_all()
        self.assertEqual(io.log, [("down", "c"), ("up", "c"), ("down", "w"), ("up", "w")])

    def test_unknown_action(self):
        with self.assertRaises(KeyError):
            Controller({}, backend=FakeIO()).tap("jump")


if __name__ == "__main__":
    unittest.main()
