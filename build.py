"""Build a single-file SnapSorter executable into dist/.

Usage:
    python build.py            # clean, then build
    python build.py --no-clean # keep existing dist/ contents
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC_NAME = "SnapSorter.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
EXE_NAME = "SnapSorter.exe" if sys.platform == "win32" else "SnapSorter"


def clean():
    """Remove previous build output so a stale binary is never mistaken for fresh."""
    for path in (BUILD, DIST):
        if not path.exists():
            continue
        try:
            shutil.rmtree(path)
            print(f"  removed {path.name}/")
        except PermissionError:
            # A running SnapSorter.exe holds its own file open. Note that a
            # --onefile build runs a parent bootloader plus a child process, so
            # closing the window may not be enough; check Task Manager.
            raise SystemExit(
                f"error: cannot remove {path.name}/ -- a file is in use.\n"
                "       Close any running SnapSorter.exe, then retry."
            )
    cache = ROOT / "__pycache__"
    if cache.exists():
        shutil.rmtree(cache)


def build():
    """Run PyInstaller against the committed spec."""
    if not (ROOT / SPEC_NAME).exists():
        raise SystemExit(f"error: {SPEC_NAME} not found in {ROOT}")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        SPEC_NAME,
        "--noconfirm",   # overwrite dist/ without prompting
        "--clean",       # drop PyInstaller's analysis cache
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
    ]
    print("  " + " ".join(command[1:]))
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    print(f"Building {EXE_NAME} with Python {sys.version.split()[0]}")
    if "--no-clean" not in sys.argv:
        clean()
    else:
        print("  --no-clean: keeping existing build output")
    build()

    exe = DIST / EXE_NAME
    if not exe.exists():
        raise SystemExit(f"error: expected {exe} but it was not produced")
    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"\nBuilt {exe.relative_to(ROOT)}  ({size_mb:.1f} MB, single file)")
    print("The app has no CLI: it opens folder pickers, so it will look idle.")


if __name__ == "__main__":
    main()
