#!/usr/bin/env python3
"""Render a motion composition (HTML exposing window.__motion) to video.

Frame-exact: each frame calls __motion.seek(t) in headless Chromium, screenshots the
stage, and pipes PNGs to ffmpeg. Nothing reads the wall clock.

  render.py comp.html -o out.mp4                  # H.264 MP4
  render.py comp.html -o out.mov --prores         # ProRes 422 HQ for video editors
  render.py comp.html -o out.mov --alpha          # ProRes 4444 with transparent bg
  render.py comp.html -o out.gif                  # GIF (palette pass)
  render.py comp.html --stills 0,4.2,9 -o shots/  # PNG stills at the given seconds
  options: --fps N  --scale 0.5  --from S --to S  --audio track.mp3

Needs: python playwright (+ chromium) and ffmpeg on PATH.
"""
import argparse, shutil, subprocess, sys, tempfile, time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--fps", type=float)
    ap.add_argument("--scale", type=float, default=1.0, help="device scale factor (0.5 = half-res draft)")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--prores", action="store_true")
    ap.add_argument("--alpha", action="store_true", help="transparent background, ProRes 4444 .mov")
    ap.add_argument("--audio")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--stills", help="comma-separated seconds; writes PNGs into --out dir")
    a = ap.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg and not a.stills:
        sys.exit("ffmpeg not found on PATH")
    from playwright.sync_api import sync_playwright

    src = Path(a.html).resolve()
    url = src.as_uri() + "?render=1" + ("&alpha=1" if a.alpha else "")

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text"])
        probe = browser.new_page()
        probe.goto(url)
        probe.wait_for_function("window.__motion !== undefined")
        fmt = probe.evaluate("({w: __motion.width, h: __motion.height, fps: __motion.fps, d: __motion.duration})")
        probe.close()

        W, H = fmt["w"], fmt["h"]
        fps = a.fps or fmt["fps"]
        t1 = a.t1 if a.t1 is not None else fmt["d"]
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=a.scale)
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_function("window.__motion !== undefined")
        page.evaluate("__motion.ready")
        page.evaluate("document.fonts.ready.then(() => 1)")
        if a.alpha:
            page.evaluate("document.documentElement.style.background='transparent';"
                          "document.body.style.background='transparent';"
                          "document.getElementById('stage').style.background='transparent'")
        stage = page.locator("#stage")

        def shot(t):
            page.evaluate(f"__motion.seek({t})")
            return stage.screenshot(type="png", omit_background=a.alpha, animations="allow")

        if a.stills:
            outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
            for s in [float(x) for x in a.stills.split(",")]:
                f = outdir / f"still_{s:07.3f}s.png"
                f.write_bytes(shot(s)); print(f)
            browser.close(); return

        out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
        ext = out.suffix.lower()
        n = int(round((t1 - a.t0) * fps))
        ow, oh = int(W * a.scale) // 2 * 2, int(H * a.scale) // 2 * 2

        tmp = None
        target = out
        if ext == ".gif":
            tmp = Path(tempfile.mkdtemp()); target = tmp / "pre.mov"

        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
               "-c:v", "png", "-i", "-"]
        if a.audio:
            cmd += ["-i", a.audio]
        cmd += ["-vf", f"scale={ow}:{oh}:flags=lanczos"]
        if a.alpha:
            cmd += ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
        elif a.prores or ext == ".gif":
            cmd += ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-colorspace", "bt709"]
        if a.audio:
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd.append(str(target))

        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        t_start = time.time()
        for i in range(n):
            ff.stdin.write(shot(a.t0 + i / fps))
            if i % max(1, int(fps)) == 0:
                print(f"\rframe {i+1}/{n}", end="", file=sys.stderr, flush=True)
        ff.stdin.close()
        rc = ff.wait()
        browser.close()
        print(f"\rrendered {n} frames in {time.time()-t_start:.1f}s", file=sys.stderr)
        if rc:
            sys.exit(f"ffmpeg exited {rc}")

        if ext == ".gif":
            gfps = min(fps, 20)
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(target), "-vf",
                            f"fps={gfps},scale=min(960\\,iw):-2:flags=lanczos,split[a][b];"
                            "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a",
                            str(out)], check=True)
            shutil.rmtree(tmp)
        print(out)


if __name__ == "__main__":
    main()
