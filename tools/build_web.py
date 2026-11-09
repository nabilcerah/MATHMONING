"""Build MATHMON for the web (pygbag / WebAssembly) - the folder you upload to Vercel.

    python tools/build_web.py           # build only  -> build/mathmon/build/web
    python tools/build_web.py --serve   # build and test at http://localhost:8000

pygbag packages everything in the folder it is given, so this copies only what the game needs at
runtime (code, data, processed sprites, map tiles) into build/mathmon first. Raw sprite sheets,
saves, tests and the virtual environment stay out, keeping the download small.
Requires: pip install pygbag soundfile
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "build" / "mathmon"
CODE = ("main.py", "config.py", "game", "states", "world", "monsters", "combat", "ai", "battle_engine", "mathematics",
        "database", "data")
ASSETS = ("assets/sprites", "assets/backgrounds", "assets/fonts", "assets/sounds")
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".gitkeep", "number_forest_world.png", "_preview.jpg",
                              "New Sound", "*.mp3", "*.mpeg")    # source recordings: the game uses the .ogg copies
WEB_MUSIC_SECONDS = 75     # long recorded tracks are trimmed (with a fade) for phones' memory


KEEP = {".vercel", ".env.local"}      # the Vercel project link survives rebuilds


def clear(folder):
    """Empty ``folder`` but keep the folder itself and the Vercel link. On Windows a folder that a
    terminal is 'cd'-ed into cannot be deleted, so deleting its CONTENTS is what always works."""
    for item in folder.iterdir():
        if item.name in KEEP:
            continue
        if item.is_dir():
            clear(item)
            try:
                item.rmdir()
            except OSError:
                pass            # in use (e.g. a terminal is inside it): it is empty now, that's enough
        else:
            item.unlink()


def stage():
    if STAGE.exists():
        clear(STAGE)
    STAGE.mkdir(parents=True, exist_ok=True)
    for name in CODE + ASSETS:
        source = ROOT / name
        if not source.exists():
            continue
        target = STAGE / name
        if source.is_dir():
            shutil.copytree(source, target, ignore=SKIP)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    convert_sounds(STAGE / "assets" / "sounds")
    size = sum(f.stat().st_size for f in STAGE.rglob("*") if f.is_file())
    print(f"staged {size / 1_000_000:.1f} MB in {STAGE}")


def convert_sounds(folder):
    """pygbag only packages OGG audio, so turn every WAV into OGG Vorbis (also ~10x smaller).
    The game looks for <name>.ogg before <name>.wav, so nothing else changes."""
    if not folder.exists():
        return
    try:
        import numpy
        import soundfile
    except ImportError:
        sys.exit("The web build needs soundfile to convert the music to OGG:\n"
                 "  .venv\\Scripts\\python -m pip install soundfile")
    for wav in sorted(folder.glob("*.wav")):
        ogg = wav.with_suffix(".ogg")
        if not ogg.exists():
            data, rate = soundfile.read(str(wav), dtype="float32")
            # Small blocks: the Vorbis encoder overflows its stack on long writes on Windows.
            with soundfile.SoundFile(str(ogg), "w", rate, 1, format="OGG", subtype="VORBIS") as out:
                for start in range(0, len(data), 4096):
                    out.write(data[start:start + 4096])
        wav.unlink()
    for ogg in sorted(folder.glob("*.ogg")):
        info = soundfile.info(str(ogg))
        if info.duration <= WEB_MUSIC_SECONDS + 5:
            continue
        # In the browser a track is decoded whole into memory (smooth playback); 4 minutes of
        # stereo would be ~45 MB, so keep the first 75 s and fade it out into the loop.
        data, rate = soundfile.read(str(ogg), dtype="float32", frames=int(WEB_MUSIC_SECONDS * info.samplerate))
        fade = int(rate * 2)
        data[-fade:] *= (1 - numpy.arange(fade, dtype="float32") / fade)[:, None]
        with soundfile.SoundFile(str(ogg), "w", rate, info.channels, format="OGG", subtype="VORBIS") as out:
            for start in range(0, len(data), 4096):
                out.write(data[start:start + 4096])



def write_deploy_files(web):
    """Let `vercel --prod` run straight from the output folder: serve the files as a plain static site
    (no Python detection, no build step) and never upload local .env files."""
    (web / "vercel.json").write_text(json.dumps(
        {"framework": None, "installCommand": "", "buildCommand": "", "outputDirectory": "."}, indent=2) + "\n")
    (web / ".vercelignore").write_text(".env\n.env.*\n")
    # "Add to Home Screen" opens the game like an app: full screen, landscape, no browser bars.
    (web / "manifest.webmanifest").write_text(json.dumps({
        "name": "MATHMON", "short_name": "MATHMON", "start_url": ".", "scope": ".",
        "display": "fullscreen", "orientation": "landscape",
        "background_color": "#000000", "theme_color": "#131a2a",
        "icons": [{"src": "favicon.png", "sizes": "any", "type": "image/png"}],
    }, indent=2) + "\n")


def main():
    stage()
    serve = "--serve" in sys.argv
    # Our page template makes the canvas fill any window and tells the game when it's on a phone.
    template = ROOT / "tools" / "web" / "mathmon.tmpl"
    command = ([sys.executable, "-m", "pygbag", "--template", str(template), "--title", "MATHMON"]
               + ([] if serve else ["--build"]) + [str(STAGE)])
    print(" ".join(command))
    web = STAGE / "build" / "web"
    link = web / ".vercel"
    saved = None
    if link.exists():    # pygbag empties build/web; keep the Vercel project link across builds
        saved = STAGE.parent / ".vercel-link"
        shutil.rmtree(saved, ignore_errors=True)
        shutil.copytree(link, saved)
    subprocess.run(command, check=True)
    if saved is not None:
        shutil.copytree(saved, link, dirs_exist_ok=True)
    if not serve:
        write_deploy_files(web)
        print(f"\nDone. Upload this folder to Vercel:\n  {STAGE / 'build' / 'web'}")


if __name__ == "__main__":
    main()
