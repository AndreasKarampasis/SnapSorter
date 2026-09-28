# AGENTS.md

Two-module Python desktop app: `gui.py` is the CustomTkinter interface, `photo_sorter.py` is the backend and must stay GUI-free.

## Layout

- `photo_sorter.py` — **backend only.** Sorting, date resolution, validation. Imports `datetime`, `pathlib`, `shutil`, `PIL` and nothing else — no `tkinter`, no `customtkinter`, no `gui`. This is what makes it importable and testable with no display.
- `gui.py` — **UI only.** `SortApp`, `Modal`, `main()`. Owns no sorting logic; it calls `sort_photos()` and renders results.
- `tests/test_photo_sorter.py` — pytest suite. `pyproject.toml` holds the pytest config and the `dev` extra; `requirements.txt` pins the runtime deps.
- `SnapSorter.spec` + `build.py` — PyInstaller packaging. `python build.py` produces `dist\SnapSorter.exe`.
- `.github/workflows/ci.yml` — tests on `windows-latest`, Python 3.10/3.11. `.github/workflows/build.yml` — builds the exe.

Runtime dependencies are **Pillow** and **CustomTkinter**; everything else is stdlib. Python floor is **3.9** (`Path.is_relative_to` in `validate_directories`).

## Commands

```powershell
pip install -e ".[dev]"   # or: pip install -r requirements.txt
python gui.py             # run the app (NOT photo_sorter.py - that is a backend)
python -m pytest          # run the full suite
python -m pytest -q -k exif
python build.py           # build dist\SnapSorter.exe
```

`tkinter` is stdlib on the Windows/macOS python.org builds but a separate `python3-tk` package on Debian/Ubuntu.

## Threading: the worker must not touch Tk

`sort_photos` runs on a `threading.Thread`. The worker **only** pushes tuples onto `self._events` (a `queue.Queue`); the GUI thread drains it in `_poll()` via `self.after(40, ...)`.

Do **not** call `self.after(...)`, `self.update()` or any widget method from the worker. Tk calls from a non-main thread only marshal while the main thread is blocking inside `mainloop()`; from a `update()` loop they raise `RuntimeError: main thread is not in main loop`. This was hit and fixed during the GUI build, and `test_gui_worker_never_touches_tkinter` guards it via AST.

## CustomTkinter gotchas (verified on 6.0.0)

- **`CTkEntry(state="readonly")` is broken.** `insert()` is a silent no-op and `get()` always returns `''`. The path display is a `CTkLabel` inside a bordered `CTkFrame` instead. Do not "fix" this back to a readonly entry.
- The widget is `CTkEntry._entry`, not `.entry` (that attribute does not exist in 6.x).
- `ctk.AppearanceMode` is not exported; pass the plain string `"system"` to `set_appearance_mode`.
- `CTkTextbox` does expose `tag_config`/`tag_add` publicly, which is how the log colours errors.
- Long paths: the label is re-`wraplength`-ed on the frame's `<Configure>` event.

## Sorting behaviour (do not regress)

- Extension matching uses `entry.suffix.lower() in VALID_IMAGE_EXTENSIONS`, not `str.endswith`. `endswith` is case-sensitive (skipping `IMG.JPG`) and matches a *directory* named `MyPhotos.cr2`, which used to get moved as a whole tree. `iter_images` also gates on `is_file()`.
- `entry.relative_to(source)` is what makes collisions impossible — targets mirror the source layout. Reverting to a flat layout reintroduces the collision bug.
- `sort_photos` snapshots `list(iter_images(source))` **before** moving anything. A progress bar needs the total up front, and the walk must not descend into the directories the run creates.
- `on_progress(processed, total, entry, target, error)` fires once per file after it is attempted, `error` being `None` on success. It runs on the calling thread.
- `exif_datetime` must read `get_ifd(0x8769)[0x9003]`. Reading `getexif().get(0x9003)` off IFD0 returns `None` and silently never matches, because `DateTimeOriginal` lives in the Exif sub-IFD, not IFD0.
- `exif_datetime` deliberately swallows every exception, and `sort_photos` catches per file: a corrupt photo must fall back to the filesystem date and must never abort the batch.
- Emptied source directories are never pruned. Changing that is a UX decision, not a bug fix.
- Python 3.12+ exposes `st_birthtime` on Windows; before that, and on Linux, the fallback is `st_ctime`, which is *not* creation time off Windows.

## Testing conventions

- Tests import only `photo_sorter`. **Never import `gui` in a test** — it needs an interactive desktop and would be flaky in CI. The GUI is covered by AST-based architecture guards instead (it must delegate to the backend, and must not import `PIL`).
- Tests use `tmp_path` and call `sort_photos(source, dest)` directly. Do not test `main()`.
- Most tests take the `fixed_date` fixture, which monkeypatches `ps.file_datetime`. Rely on it rather than the real filesystem or EXIF clock — otherwise folder names become machine-dependent and the suite goes flaky.
- For EXIF tests use the `make_image()` helper. Pillow **cannot write a `.cr2`**, so simulate raw files by writing a JPEG and renaming it.
- Each test's docstring names the bug it pins; those were reproduced live before being fixed.

## Packaging

- `SnapSorter.spec` is committed on purpose and is deliberately **not** gitignored — it is a build input.
- Its entry point is `gui.py`. Pointing it at `photo_sorter.py` yields an executable with no window.
- `collect_data_files("customtkinter")` is mandatory: without the theme JSON the exe dies at import with `FileNotFoundError`.
- `collect_all("PIL")` is mandatory: Pillow loads codec plugins lazily.
- Pass `collect_all` output into `Analysis(...)`; never `+=` onto `analysis.datas`, which holds 3-tuples while `collect_all` yields 2-tuples.

## CI

- Both workflows are **Windows-only** by design and use `pwsh`. Keep quotes PowerShell-safe (single-quoted `'.[dev]'`).
- Tests run on Python 3.10 and 3.11. On Windows both fall back to `st_ctime`, so the `st_birthtime` branch in `file_datetime` is only reachable on **3.12+** — CI does not cover it. Add `"3.12"` to the matrix to cover it.
- `build.py` reports a clear error if a previous `SnapSorter.exe` is still running. A `--onefile` build is a parent bootloader plus a child process, so closing the window may not release the file.

## Conventions

- 4-space indent, no type hints, no classes in the backend; stdlib-first apart from Pillow and CustomTkinter.
- Keep diffs minimal and match surrounding style.
- Default branch is `main`; remote is GitHub `AndreasKarampasis/SnapSorter`.
