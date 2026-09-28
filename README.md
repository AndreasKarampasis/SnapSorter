# SnapSorter

PhotoSorter is a lightweight, user-friendly application that organizes your image files into neatly categorized folders based on when they were taken. Perfect for photographers, designers, or anyone looking to declutter their photo collections.

## Features
- **Organizes photos**: Sorts image files (`.png`, `.jpg`, `.jpeg`, `.cr2` — matched case-insensitively) into folders named by capture date.
- **Reads EXIF dates**: Uses the EXIF `DateTimeOriginal` tag, falling back to `DateTimeDigitized`, the plain TIFF `DateTime` tag, then the filesystem timestamp. This is accurate across platforms, unlike `st_ctime`.
- **Preserves subfolders**: A file at `trip/day2/a.jpg` lands in `2024-12-03/trip/day2/a.jpg`, so same-named files in different folders never collide.
- **Modern desktop interface**: Built with [CustomTkinter](https://github.com/tomschroeder/CustomTkinter) — follows your Windows light/dark theme, shows a live progress bar and a scrollable activity log, and never freezes while scanning or moving files.
- **Safe by default**: Confirms the exact source and destination before moving anything, then reports how many files moved versus failed.

## Prerequisites
- Python 3.9 or higher
- Runtime dependencies:
  ```bash
  pip install -r requirements.txt   # Pillow + CustomTkinter
  ```

## Running

```bash
python gui.py
```

`photo_sorter.py` holds all the sorting logic and imports no GUI toolkit, so it can be imported and tested on a machine with no display.

## How It Works
1. **Select Source Directory**: Use **Browse** to pick a folder containing image files. Subfolders are included.
2. **Select Destination Directory**: Choose where you’d like the organized folders to be created. It must already exist and must not be inside the source directory.
3. **Confirm**: A dialog restates the exact source and destination. Sorting **moves** files, so this is your checkpoint.
4. **Automatic Sorting**: The app scans the source tree in the background, reads each photo's capture date, and moves it into a folder named for that date (e.g. `2024-12-03`), reproducing its subfolder structure. Progress, every move, and every error stream into the activity log, and a summary reports files moved versus failures.

> **Note:** Sorting **moves** files; it does not copy them, and it cannot be undone. Empty folders left behind in the source are not pruned.

## Tests
```bash
pip install -e ".[dev]"
pytest
```

Tests run automatically on GitHub Actions (`windows-latest`, Python 3.10 and 3.11) for every push and pull request to `main`.

## Building Executable

A single-file, windowed Windows executable is built with [PyInstaller](https://pyinstaller.org/).

```bash
pip install -e ".[dev]"   # installs pyinstaller as a dev dependency
python build.py
```

This cleans any previous `build/` and `dist/` output and produces **`dist\SnapSorter.exe`** (~20 MB, no console window). Pass `--no-clean` to keep existing output.

The build is driven by the committed `SnapSorter.spec`, so it is reproducible rather than depending on `pyi-makespec` defaults. Three details in that spec are load-bearing:

- The entry point is `gui.py`, not `photo_sorter.py` — the latter is a GUI-free backend and would produce an executable with no window.
- `collect_all("PIL")` — Pillow resolves its codec plugins lazily inside `Image.open()`. Without bundling them the executable throws `UnidentifiedImageError` on valid photos.
- `collect_data_files("customtkinter")` — CustomTkinter loads its colour theme from `assets/themes/*.json` at import time. Those files are invisible to static analysis, and without them the executable dies with `FileNotFoundError` before the first window appears.

> **Not code-signed.** Windows SmartScreen will warn on first run, since the binary is unsigned. Also note `--onefile` unpacks to a temp folder at launch, so startup takes a second or two.

### Automated builds

`.github/workflows/build.yml` runs the test suite and then builds the executable on every push and pull request to `main`, uploading `SnapSorter.exe` as a build artifact. Pushing a `v*` tag additionally publishes the binary to a GitHub Release:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

Both workflows are Windows-only because the app targets Windows and its date handling differs by platform.
