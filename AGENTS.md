# AGENTS.md

Single-file Python Tkinter utility that sorts photos into date-named folders.

## Layout

- `photo_sorter.py` — the entire application. The repo is named **SnapSorter** but the module is `photo_sorter.py`; there is no `snapsorter` package and no `src/`.
- `tests/test_photo_sorter.py` — pytest suite. `pyproject.toml` holds the pytest config and the `dev` extra; `requirements.txt` pins the runtime dep.
- `.github/workflows/ci.yml` — runs the suite on `windows-latest` for Python 3.10 and 3.11 on push/PR to `main`.
- Runtime dependency is **Pillow** (EXIF reading); everything else is stdlib. Python floor is **3.9** — `Path.is_relative_to` is used in `validate_directories`.

## Commands

```powershell
pip install -e ".[dev]"   # or: pip install -r requirements.txt
python photo_sorter.py   # run the app; needs a real desktop (Tkinter GUI)
python -m pytest         # run the full suite
python -m pytest -q -k exif
```

`tkinter` is stdlib on the Windows/macOS python.org builds but a separate `python3-tk` package on Debian/Ubuntu.

## CI

- `.github/workflows/ci.yml` is **Windows-only** by design, and the run steps use `pwsh`. Keep quotes PowerShell-safe (single-quoted `'.[dev]'`).
- It tests Python 3.10 and 3.11. On Windows both fall back to `st_ctime`, so the `getattr(stat, "st_birthtime", ...)` branch in `file_datetime` is only reachable on **3.12+** — CI does not currently cover it. Add `"3.12"` to the matrix to cover it.

## Testing conventions

- Tests use `tmp_path` and call `sort_photos(source, dest)` directly. Do **not** test `main()`; it opens Tkinter dialogs and is not importable-testable.
- Most tests take the `fixed_date` fixture, which monkeypatches `ps.file_datetime`. Rely on it rather than the real filesystem or EXIF clock — otherwise folder names become machine-dependent and the suite goes flaky.
- To test EXIF specifically, use the `make_image()` helper: it writes a real JPEG with a real EXIF tag. Pillow **cannot write a `.cr2`**, so simulate raw files by writing a JPEG and renaming it.
- Each test's docstring names the bug it pins. Those were all reproduced live before being fixed; if you change behavior, update the test that guards it.

## Behavior notes

- Extension matching uses `entry.suffix.lower() in VALID_IMAGE_EXTENSIONS`, not `str.endswith`. `endswith` is case-sensitive (skipping `IMG.JPG`) and matches a *directory* named `MyPhotos.cr2`, which used to get moved as a whole tree. `iter_images` also gates on `is_file()`.
- `entry.relative_to(source)` is what makes collisions impossible — targets mirror the source layout instead of flattening. Reverting to a flat layout reintroduces the collision bug.
- `exif_datetime` must read `get_ifd(0x8769)[0x9003]`. Reading `getexif().get(0x9003)` off IFD0 returns `None` and silently never matches, because `DateTimeOriginal` lives in the Exif sub-IFD, not IFD0.
- `exif_datetime` deliberately swallows every exception: a corrupt or unsupported file must still fall back to the filesystem date rather than abort the run. The same is why `sort_photos` catches per file — one failure returns in `failures` instead of killing the batch.
- `sort_photos` never prunes emptied source directories, and never prompts. Both are deliberate; changing them is a UX decision, not a bug fix.
- Python 3.12+ exposes `st_birthtime` on Windows; before that, and on Linux, the fallback is `st_ctime`, which is *not* creation time off Windows.

## Conventions

- 4-space indent, no type hints, no classes; stdlib-first with Pillow as the single exception.
- Keep diffs minimal and match surrounding style. The original stray trailing whitespace is gone; do not reintroduce it.
- Default branch is `main`; remote is GitHub `AndreasKarampasis/SnapSorter`.
