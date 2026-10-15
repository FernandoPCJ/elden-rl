"""Converte um vídeo gravado para publicar (LinkedIn, YouTube, WhatsApp).

O OpenCV grava em MPEG-4 antigo ("mp4v"), que o LinkedIn não aceita. Este script gera uma
cópia em H.264, ampliada para 1920 px de largura e a 30 quadros por segundo:

    python scripts/08_export_video.py runs/treino02/videos/ep00003_victory.mp4
    python scripts/08_export_video.py VIDEO --fps-original 15   # vídeos gravados antes de 12/10

Precisa do pacote imageio-ffmpeg (pip install imageio-ffmpeg), que já traz o ffmpeg.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("--saida", type=Path, help="padrão: <nome>_publicar.mp4 ao lado do original")
    parser.add_argument("--fps-original", type=float, default=5.0,
                        help="quadros por segundo reais da gravação (5 = um por decisão do agente)")
    parser.add_argument("--largura", type=int, default=1920)
    args = parser.parse_args()

    import imageio_ffmpeg

    out = args.saida or args.video.with_name(args.video.stem + "_publicar.mp4")
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error",
           "-r", str(args.fps_original), "-i", str(args.video),
           "-vf", f"scale={args.largura}:-2:flags=lanczos,fps=30",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-an", str(out)]
    subprocess.run(cmd, check=True)
    print(f"Pronto: {out}")


if __name__ == "__main__":
    main()
