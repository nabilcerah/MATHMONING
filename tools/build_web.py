"""Build MATHMON for the web (pygbag / WebAssembly) - the folder you upload to Vercel.

    python tools/build_web.py           # build only  -> build/mathmon/build/web
    python tools/build_web.py --serve   # build and test at http://localhost:8000

pygbag packages everything in the folder it is given, so this copies only what the game needs at
runtime (code, data, processed sprites, map tiles) into build/mathmon first. Raw sprite sheets,
saves, tests and the virtual environment stay out, keeping the download small.
Requires: pip install pygbag
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
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".gitkeep", "number_forest_world.png", "_preview.jpg")


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
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
    size = sum(f.stat().st_size for f in STAGE.rglob("*") if f.is_file())
    print(f"staged {size / 1_000_000:.1f} MB in {STAGE}")


def write_deploy_files(web):
    """Let `vercel --prod` run straight from the output folder: serve the files as a plain static site
    (no Python detection, no build step) and never upload local .env files."""
    (web / "vercel.json").write_text(json.dumps(
        {"framework": None, "installCommand": "", "buildCommand": "", "outputDirectory": "."}, indent=2) + "\n")
    (web / ".vercelignore").write_text(".env\n.env.*\n")


def main():
    stage()
    serve = "--serve" in sys.argv
    # Our page template makes the canvas fill any window and tells the game when it's on a phone.
    template = ROOT / "tools" / "web" / "mathmon.tmpl"
    command = ([sys.executable, "-m", "pygbag", "--template", str(template), "--title", "MATHMON"]
               + ([] if serve else ["--build"]) + [str(STAGE)])
    print(" ".join(command))
    subprocess.run(command, check=True)
    if not serve:
        write_deploy_files(STAGE / "build" / "web")
        print(f"\nDone. Upload this folder to Vercel:\n  {STAGE / 'build' / 'web'}")


if __name__ == "__main__":
    main()
