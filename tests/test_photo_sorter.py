"""Tests for photo_sorter. Each test pins a bug that was reproduced live."""
import ast
import datetime
import pathlib

import pytest
from PIL import Image

import photo_sorter as ps

FIXED_DATE = datetime.datetime(2021, 3, 4, 5, 6, 7)
FIXED_FOLDER = "2021-03-04"


@pytest.fixture
def fixed_date(monkeypatch):
    """Pin the capture date so folder names do not depend on the filesystem."""
    monkeypatch.setattr(ps, "file_datetime", lambda path: FIXED_DATE)
    return FIXED_DATE


def make_image(path, date_time=b"1999:12:31 23:59:58", tag=ps.EXIF_DATE_TIME_ORIGINAL):
    """Write a real JPEG carrying an EXIF capture date."""
    path.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    if tag == ps.EXIF_DATE_TIME_TIFF:
        exif[tag] = date_time
    else:
        sub_ifd = exif.get_ifd(ps.EXIF_IFD_TAG)
        sub_ifd[tag] = date_time
        exif[ps.EXIF_IFD_TAG] = sub_ifd
    Image.new("RGB", (2, 2), "red").save(path, exif=exif)
    return path


def tree(root):
    """Return every path under root as a sorted list of relative strings."""
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*"))


# --- extension matching -------------------------------------------------


def test_moves_plain_images(tmp_path, fixed_date):
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "a.jpg").write_bytes(b"x")

    moved, failures = ps.sort_photos(source, dest)

    assert (moved, failures) == (1, [])
    assert tree(dest) == [FIXED_FOLDER, f"{FIXED_FOLDER}/a.jpg"]


def test_uppercase_extensions_are_matched(tmp_path, fixed_date):
    """endswith() was case-sensitive, so IMG.JPG and IMG.CR2 were skipped."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    for name in ("a.JPG", "b.Cr2", "c.JPEG", "d.PNG"):
        (source / name).write_bytes(b"x")

    moved, failures = ps.sort_photos(source, dest)

    assert (moved, failures) == (4, [])
    assert f"{FIXED_FOLDER}/a.JPG" in tree(dest)
    assert f"{FIXED_FOLDER}/b.Cr2" in tree(dest)


def test_unsupported_extension_is_ignored(tmp_path, fixed_date):
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "notes.txt").write_bytes(b"x")
    (source / "clip.mp4").write_bytes(b"x")

    assert ps.sort_photos(source, dest) == (0, [])
    assert tree(dest) == []


def test_file_named_like_an_extension_is_not_an_image(tmp_path, fixed_date):
    """Path('.jpg').suffix is '', so a dotfile named '.jpg' is not an image."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / ".jpg").write_bytes(b"x")

    assert ps.sort_photos(source, dest) == (0, [])
    assert tree(source) == [".jpg"]


# --- directories must not be moved --------------------------------------


def test_directory_named_like_an_image_is_not_moved(tmp_path, fixed_date):
    """rglob yields directories; endswith() matched 'MyPhotos.cr2' and move()d it."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    photos = source / "MyPhotos.cr2"
    photos.mkdir()
    (photos / "inner.jpg").write_bytes(b"x")
    (source / "real.jpg").write_bytes(b"x")

    moved, failures = ps.sort_photos(source, dest)

    # The directory stays put; its image contents are still sorted, in place.
    assert (moved, failures) == (2, [])
    assert photos.is_dir()
    # Empty source directories are deliberately left behind, not pruned.
    assert list(photos.iterdir()) == []
    assert tree(dest) == [
        FIXED_FOLDER,
        f"{FIXED_FOLDER}/MyPhotos.cr2",
        f"{FIXED_FOLDER}/MyPhotos.cr2/inner.jpg",
        f"{FIXED_FOLDER}/real.jpg",
    ]


# --- collisions and structure -------------------------------------------


def test_same_named_files_in_different_folders_both_survive(tmp_path, fixed_date):
    """Two 'dup.jpg' used to collide; the unhandled shutil.Error aborted the run."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "one").mkdir()
    (source / "two").mkdir()
    (source / "one" / "dup.jpg").write_bytes(b"1")
    (source / "two" / "dup.jpg").write_bytes(b"2")

    moved, failures = ps.sort_photos(source, dest)

    assert (moved, failures) == (2, [])
    assert f"{FIXED_FOLDER}/one/dup.jpg" in tree(dest)
    assert f"{FIXED_FOLDER}/two/dup.jpg" in tree(dest)


def test_nested_structure_is_preserved(tmp_path, fixed_date):
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    deep = source / "2019" / "trip" / "day2"
    deep.mkdir(parents=True)
    (deep / "a.jpg").write_bytes(b"x")

    moved, failures = ps.sort_photos(source, dest)

    assert (moved, failures) == (1, [])
    assert f"{FIXED_FOLDER}/2019/trip/day2/a.jpg" in tree(dest)


def test_two_dates_produce_two_folders(tmp_path, monkeypatch):
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "a.jpg").write_bytes(b"x")
    (source / "b.jpg").write_bytes(b"y")

    dates = iter([datetime.datetime(2020, 1, 2), datetime.datetime(2021, 3, 4)])
    monkeypatch.setattr(ps, "file_datetime", lambda path: next(dates))
    ps.sort_photos(source, dest)

    assert "2020-01-02/a.jpg" in tree(dest)
    assert "2021-03-04/b.jpg" in tree(dest)


# --- destination guards -------------------------------------------------


def test_destination_inside_source_is_rejected(tmp_path, fixed_date):
    """rglob re-walked the date folders it created and died on 'already exists'."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    (source / "organized").mkdir(parents=True)
    (source / "a.jpg").write_bytes(b"x")

    with pytest.raises(ValueError, match="inside the source"):
        ps.sort_photos(source, source / "organized")
    assert (source / "a.jpg").exists()


def test_same_source_and_destination_is_rejected(tmp_path, fixed_date):
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"x")

    with pytest.raises(ValueError, match="different directories"):
        ps.sort_photos(source, source)
    assert (source / "a.jpg").exists()


def test_missing_destination_is_rejected(tmp_path, fixed_date):
    source = tmp_path / "src"
    source.mkdir()

    with pytest.raises(ValueError, match="does not exist"):
        ps.sort_photos(source, tmp_path / "nope")


# --- failure containment ------------------------------------------------


def test_one_failure_does_not_abort_the_run(tmp_path, fixed_date, monkeypatch):
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    for name in ("a.jpg", "boom.jpg", "c.jpg"):
        (source / name).write_bytes(b"x")

    real_move = ps.move

    def flaky_move(src, dst):
        if src.name == "boom.jpg":
            raise OSError("disk full")
        return real_move(src, dst)

    monkeypatch.setattr(ps, "move", flaky_move)
    moved, failures = ps.sort_photos(source, dest)

    assert moved == 2
    assert len(failures) == 1
    assert failures[0][0].name == "boom.jpg"
    assert isinstance(failures[0][1], OSError)
    # The file that failed is still in place; the rest were sorted.
    assert (source / "boom.jpg").exists()
    assert f"{FIXED_FOLDER}/c.jpg" in tree(dest)


def test_empty_source(tmp_path, fixed_date):
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()

    assert ps.sort_photos(source, dest) == (0, [])
    assert tree(dest) == []


# --- EXIF ---------------------------------------------------------------


def test_exif_datetime_reads_sub_ifd(tmp_path):
    path = make_image(tmp_path / "a.jpg", b"2021:03:04 05:06:07")
    assert ps.exif_datetime(path) == FIXED_DATE


def test_exif_datetime_reads_tiff_tag(tmp_path):
    path = make_image(tmp_path / "a.jpg", b"2018:07:08 09:10:11", tag=ps.EXIF_DATE_TIME_TIFF)
    assert ps.exif_datetime(path) == datetime.datetime(2018, 7, 8, 9, 10, 11)


def test_exif_datetime_falls_back_to_digitized(tmp_path):
    path = make_image(tmp_path / "a.jpg", b"2015:01:01 00:00:00", tag=ps.EXIF_DATE_TIME_DIGITIZED)
    assert ps.exif_datetime(path) == datetime.datetime(2015, 1, 1, 0, 0, 0)


def test_exif_preferred_over_filesystem_time(tmp_path):
    path = make_image(tmp_path / "a.jpg", b"2001:02:03 04:05:06")
    assert ps.file_datetime(path) == datetime.datetime(2001, 2, 3, 4, 5, 6)


def test_exif_original_wins_over_digitized(tmp_path):
    exif = Image.Exif()
    sub_ifd = exif.get_ifd(ps.EXIF_IFD_TAG)
    sub_ifd[ps.EXIF_DATE_TIME_ORIGINAL] = b"2001:02:03 04:05:06"
    sub_ifd[ps.EXIF_DATE_TIME_DIGITIZED] = b"2015:01:01 00:00:00"
    exif[ps.EXIF_IFD_TAG] = sub_ifd
    path = tmp_path / "a.jpg"
    Image.new("RGB", (2, 2), "red").save(path, exif=exif)

    assert ps.exif_datetime(path) == datetime.datetime(2001, 2, 3, 4, 5, 6)


def test_exif_absent_falls_back_to_filesystem(tmp_path):
    path = tmp_path / "a.jpg"
    Image.new("RGB", (2, 2), "red").save(path)
    assert ps.exif_datetime(path) is None
    assert isinstance(ps.file_datetime(path), datetime.datetime)


@pytest.mark.parametrize("raw", [None, b"", "", b"garbage", b"\xff\xfe not ascii", 12345])
def test_parse_exif_datetime_rejects_junk(raw):
    assert ps.parse_exif_datetime(raw) is None


def test_parse_exif_datetime_accepts_str_and_trims():
    assert ps.parse_exif_datetime("2021:03:04 05:06:07") == FIXED_DATE
    assert ps.parse_exif_datetime(b"2021:03:04 05:06:07\x00") == FIXED_DATE
    assert ps.parse_exif_datetime("2021-03-04 05:06:07") == FIXED_DATE


def test_corrupt_file_falls_back_instead_of_raising(tmp_path):
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"this is not an image")
    assert ps.exif_datetime(path) is None
    assert isinstance(ps.file_datetime(path), datetime.datetime)


def test_exif_sort_end_to_end(tmp_path):
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    make_image(source / "trip.jpg", b"2021:03:04 05:06:07")

    moved, failures = ps.sort_photos(source, dest)

    assert (moved, failures) == (1, [])
    assert tree(dest) == [FIXED_FOLDER, f"{FIXED_FOLDER}/trip.jpg"]


# --- progress reporting -------------------------------------------------


def test_on_progress_reports_every_file(tmp_path, fixed_date):
    """The GUI drives its progress bar and log from this callback."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (source / name).write_bytes(b"x")

    seen = []
    moved, failures = ps.sort_photos(
        source, dest,
        on_progress=lambda *args: seen.append(args),
    )

    assert (moved, failures) == (3, [])
    assert [call[0] for call in seen] == [1, 2, 3]
    assert all(call[1] == 3 for call in seen)      # total is stable
    assert all(call[4] is None for call in seen)   # error None on success
    assert all(call[3] is not None for call in seen)  # target populated


def test_on_progress_reports_errors(tmp_path, fixed_date, monkeypatch):
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "boom.jpg").write_bytes(b"x")

    def explode(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(ps, "move", explode)
    seen = []
    ps.sort_photos(source, dest, on_progress=lambda *args: seen.append(args))

    assert len(seen) == 1
    assert isinstance(seen[0][4], OSError)


def test_sort_photos_without_callback_still_works(tmp_path, fixed_date):
    """The callback is optional; existing two-argument callers keep working."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "a.jpg").write_bytes(b"x")

    assert ps.sort_photos(source, dest) == (1, [])


def test_image_list_is_snapshotted_before_moving(tmp_path, fixed_date):
    """A progress bar needs a total up front, and the walk must not see its
    own output directories."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "a.jpg").write_bytes(b"x")
    (source / "sub").mkdir()
    (source / "sub" / "b.jpg").write_bytes(b"x")

    totals = []
    ps.sort_photos(source, dest, on_progress=lambda p, t, *a: totals.append(t))

    assert totals == [2, 2]
    assert tree(dest) == [
        FIXED_FOLDER,
        f"{FIXED_FOLDER}/a.jpg",
        f"{FIXED_FOLDER}/sub",
        f"{FIXED_FOLDER}/sub/b.jpg",
    ]


# --- architecture guards ------------------------------------------------


REPO_ROOT = pathlib.Path(ps.__file__).resolve().parent
GUI_SOURCE = REPO_ROOT / "gui.py"


def _top_level_imports(path):
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def test_backend_imports_no_gui_toolkit():
    """The backend must stay importable with no display and unit-testable."""
    assert _top_level_imports(ps.__file__) == {"datetime", "pathlib", "shutil", "PIL"}


def test_backend_does_not_import_the_gui_module():
    assert "gui" not in _top_level_imports(ps.__file__)


def test_gui_delegates_to_the_backend():
    """gui.py must call sort_photos rather than reimplementing the sort."""
    gui_imports = _top_level_imports(GUI_SOURCE)
    assert {"customtkinter", "tkinter", "photo_sorter"} <= gui_imports
    assert "PIL" not in gui_imports  # image work belongs to the backend

    source = GUI_SOURCE.read_text(encoding="utf-8")
    assert "sort_photos(" in source
    assert "def exif_datetime" not in source   # not duplicated
    assert "def target_for" not in source


def test_gui_runs_sorting_off_the_gui_thread():
    """Sorting must not run on the GUI thread or the window freezes."""
    source = GUI_SOURCE.read_text(encoding="utf-8")
    assert "threading.Thread" in source


def test_gui_worker_never_touches_tkinter():
    """The worker thread must not make Tk calls.

    Tk calls from a non-main thread only marshal while the main thread is
    blocking inside mainloop(); called from update() they raise
    "main thread is not in main loop". The worker therefore only pushes onto
    a queue that the GUI thread drains.
    """
    tree = ast.parse(GUI_SOURCE.read_text(encoding="utf-8"))
    workers = [node for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef) and node.name == "worker"]
    assert workers, "expected a nested worker function in gui.py"

    for worker in workers:
        for node in ast.walk(worker):
            if isinstance(node, ast.Attribute):
                assert node.attr not in ("after", "update", "configure", "insert"), (
                    f"worker calls self.{node.attr}() from a non-main thread"
                )
    assert "queue" in _top_level_imports(GUI_SOURCE)
