"""Sort photos into date-named folders, preserving subfolder structure.

This module is the whole backend and deliberately imports no GUI toolkit, so
it stays unit-testable and usable on a machine with no display. The desktop
interface lives in gui.py.
"""
from datetime import datetime
from pathlib import Path
from shutil import move

from PIL import Image

VALID_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".cr2")

# DateTimeOriginal/DateTimeDigitized live in the Exif sub-IFD, not IFD0.
# DateTime (0x0132) is the plain TIFF tag that raw files such as .cr2 use.
EXIF_IFD_TAG = 0x8769
EXIF_DATE_TIME_ORIGINAL = 0x9003
EXIF_DATE_TIME_DIGITIZED = 0x9004
EXIF_DATE_TIME_TIFF = 0x0132
EXIF_DATE_FORMATS = ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S")


def parse_exif_datetime(raw):
    """Parse an EXIF date value (bytes or str) into a datetime, or None."""
    if not raw:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("ascii")
        except UnicodeDecodeError:
            return None
    if not isinstance(raw, str):
        # Malformed files carry tags of arbitrary types (an int, say).
        return None
    raw = raw.strip().rstrip("\x00")
    for date_format in EXIF_DATE_FORMATS:
        try:
            return datetime.strptime(raw, date_format)
        except ValueError:
            continue
    return None


def exif_datetime(path):
    """Return the capture datetime recorded in a file's EXIF, or None.

    Every failure mode -- unreadable file, unsupported container, absent or
    malformed tags -- falls back to the filesystem rather than propagating,
    because a photo that cannot be read must still be sorted.
    """
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return None
            sub_ifd = exif.get_ifd(EXIF_IFD_TAG)
            candidates = (
                (sub_ifd, EXIF_DATE_TIME_ORIGINAL),
                (sub_ifd, EXIF_DATE_TIME_DIGITIZED),
                (exif, EXIF_DATE_TIME_TIFF),
            )
            for source, tag in candidates:
                parsed = parse_exif_datetime(source.get(tag))
                if parsed:
                    return parsed
    except Exception:
        return None
    return None


def file_datetime(path):
    """Best-effort capture time: EXIF first, then birth time, then ctime."""
    captured = exif_datetime(path)
    if captured:
        return captured
    stat = path.stat()
    # st_birthtime exists on macOS and, since 3.12, on Windows. st_ctime is
    # creation time on Windows but inode-change time elsewhere.
    birth_time = getattr(stat, "st_birthtime", None)
    if birth_time:
        return datetime.fromtimestamp(birth_time)
    return datetime.fromtimestamp(stat.st_ctime)


def format_date(date):
    """Format a datetime as a YYYY-MM-DD folder name."""
    return date.strftime("%Y-%m-%d")


def iter_images(source):
    """Yield image files under source, skipping directories and other files."""
    for entry in sorted(source.rglob("*")):
        if entry.is_file() and entry.suffix.lower() in VALID_IMAGE_EXTENSIONS:
            yield entry


def target_for(entry, source, destination, date):
    """Mirror the entry's path beneath a date folder in the destination."""
    relative = entry.relative_to(source)
    return destination / format_date(date) / relative.parent / relative.name


def validate_directories(source, destination):
    """Raise ValueError if the destination would nest inside, or equal, the source."""
    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")
    if not destination.is_dir():
        raise ValueError(f"Destination directory does not exist: {destination}")
    source_real = source.resolve()
    destination_real = destination.resolve()
    if source_real == destination_real:
        raise ValueError("Source and destination must be different directories")
    if destination_real.is_relative_to(source_real):
        raise ValueError("Destination must not be inside the source directory")


def sort_photos(source, destination, on_progress=None):
    """Sort every image under source into date folders under destination.

    Returns (moved, failures), where failures is a list of (path, error). A
    failure on one file never aborts the rest of the run.

    on_progress, if given, is called once per file as
    on_progress(processed, total, entry, target, error) after that file has
    been attempted, where error is None on success. It is invoked on the
    calling thread, which is not necessarily the GUI thread.
    """
    source = Path(source)
    destination = Path(destination)
    validate_directories(source, destination)

    # Snapshot first: the walk must not see directories this run creates, and
    # the count is needed to drive a progress bar.
    images = list(iter_images(source))
    total = len(images)

    moved = 0
    failures = []
    for processed, entry in enumerate(images, start=1):
        target = None
        error = None
        try:
            target = target_for(entry, source, destination, file_datetime(entry))
            target.parent.mkdir(parents=True, exist_ok=True)
            move(entry, target)
            moved += 1
        except (OSError, ValueError) as exc:
            error = exc
            failures.append((entry, exc))
        if on_progress is not None:
            on_progress(processed, total, entry, target, error)
    return moved, failures
