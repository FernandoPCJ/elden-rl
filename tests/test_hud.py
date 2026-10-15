import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elden_rl.hud import HUD, Bar  # noqa: E402


def fake_frame(player=1.0, boss=1.0, W=1280, H=720, player_len=0.30):
    """Quadro escuro com barras pintadas onde o HUD padrão espera."""
    f = np.full((H, W, 3), 20, np.uint8)
    hud = HUD()
    red = (30, 30, 200)  # BGR
    b = hud.bars["player_hp"]
    x0, y0, x1, y1 = b.rect_px(f)
    f[y0:y1, x0:x0 + int(player_len * W * player)] = red
    b = hud.bars["boss_hp"]
    x0, y0, x1, y1 = b.rect_px(f)
    f[y0:y1, x0:x0 + int((x1 - x0) * boss)] = red
    s = hud.bars["player_stamina"]
    x0, y0, x1, y1 = s.rect_px(f)
    f[y0:y1, x0:x0 + int(0.2 * W)] = (40, 180, 40)
    return f


class HudTest(unittest.TestCase):
    def test_boss_bar_fraction(self):
        hud = HUD()
        self.assertAlmostEqual(hud.read(fake_frame(boss=1.0))["boss_hp"], 1.0, delta=0.02)
        self.assertAlmostEqual(hud.read(fake_frame(boss=0.4))["boss_hp"], 0.4, delta=0.02)
        self.assertAlmostEqual(hud.read(fake_frame(boss=0.0))["boss_hp"], 0.0, delta=0.02)

    def test_player_bar_uses_calibrated_length(self):
        hud = HUD()
        hud.calibrate_full(fake_frame(player=1.0))
        self.assertAlmostEqual(hud.read(fake_frame(player=0.5))["player_hp"], 0.5, delta=0.02)
        self.assertAlmostEqual(hud.read(fake_frame(player=1.0))["player_stamina"], 1.0, delta=0.02)

    def test_calibration_works_at_other_resolution(self):
        hud = HUD()
        hud.calibrate_full(fake_frame(player=1.0, W=1280, H=720), names=("player_hp",))
        half_1080p = fake_frame(player=0.5, boss=1.0, W=1920, H=1080)
        self.assertAlmostEqual(hud.read(half_1080p)["player_hp"], 0.5, delta=0.03)

    def test_save_load_roundtrip(self):
        import tempfile
        hud = HUD()
        hud.calibrate_full(fake_frame())
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            hud.save(p)
            again = HUD.load(p)
        self.assertEqual(again.bars["player_hp"].full_columns, hud.bars["player_hp"].full_columns)
        self.assertIsInstance(again.bars["boss_hp"], Bar)

    def test_draw_does_not_crash(self):
        out = HUD().draw(fake_frame())
        self.assertEqual(out.shape, (720, 1280, 3))




class RobustnessTest(unittest.TestCase):
    def test_scattered_noise_is_ignored(self):
        f = fake_frame(boss=0.0)
        hud = HUD()
        x0, y0, x1, y1 = hud.bars["boss_hp"].rect_px(f)
        for x in range(x0 + 40, x1, 37):  # pixels vermelhos soltos, longe do início
            f[y0:y1, x:x + 2] = (30, 30, 200)
        self.assertEqual(hud.read(f)["boss_hp"], 0.0)

    def test_hidden_hud(self):
        self.assertFalse(HUD.hud_visible({"player_hp": 0, "player_fp": 0, "player_stamina": 0}))
        self.assertTrue(HUD.hud_visible({"player_hp": 0, "player_fp": 0.2, "player_stamina": 0.9}))




class ScreenStateTest(unittest.TestCase):
    def test_states(self):
        from elden_rl.hud import screen_state
        black = np.zeros((720, 1280, 3), np.uint8)
        self.assertEqual(screen_state(black), "black")
        prompt = black.copy()
        prompt[560:600, 400:900] = 200  # faixa de texto claro
        self.assertEqual(screen_state(prompt), "respawn_prompt")
        self.assertEqual(screen_state(fake_frame()), "game")

    def test_dark_red_boss_bar(self):
        f = np.full((720, 1280, 3), 20, np.uint8)
        hud = HUD()
        x0, y0, x1, y1 = hud.bars["boss_hp"].rect_px(f)
        f[y0:y1, x0:x0 + (x1 - x0) // 2] = (0, 0, 80)  # vermelho escuro, como no jogo
        self.assertAlmostEqual(hud.read(f)["boss_hp"], 0.5, delta=0.02)


if __name__ == "__main__":
    unittest.main()
