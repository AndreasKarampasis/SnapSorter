# SnapSorter

PhotoSorter is a lightweight, user-friendly application that organizes your image files into neatly categorized folders based on when they were taken. Perfect for photographers, designers, or anyone looking to declutter their photo collections.

## Features
- **Organizes photos**: Sorts image files (`.png`, `.jpg`, `.jpeg`, `.cr2` — matched case-insensitively) into folders named by capture date.
- **Reads EXIF dates**: Uses the EXIF `DateTimeOriginal` tag, falling back to `DateTimeDigitized`, the plain TIFF `DateTime` tag, then the filesystem timestamp. This is accurate across platforms, unlike `st_ctime`.
- **Preserves subfolders**: A file at `trip/day2/a.jpg` lands in `2024-12-03/trip/day2/a.jpg`, so same-named files in different folders never collide.
- **Graphical User Interface**: Uses a file dialog to select source and destination directories.
- **Simple & Fast**: Minimal setup and easy-to-understand workflow.

## Prerequisites
- Python 3.9 or higher
- [Pillow](https://pillow.readthedocs.io/) — pulls in EXIF support:
  ```bash
  pip install -r requirements.txt
  ```

## How It Works
1. **Select Source Directory**: The app will prompt you to select a directory containing image files. Subfolders are included.
2. **Select Destination Directory**: Choose where you’d like the organized folders to be created. It must already exist and must not be inside the source directory.
3. **Automatic Sorting**: The app scans the source tree, reads each photo's capture date, and moves it into a folder named for that date (e.g. `2024-12-03`), reproducing its subfolder structure. A file that cannot be moved is reported and the rest of the run continues.

> **Note:** Sorting **moves** files; it does not copy them. There is no undo and no confirmation prompt, so try it on a copy of a small folder first. Empty folders left behind in the source are not pruned.

## Tests
```bash
pip install -e ".[dev]"
pytest
```

Tests run automatically on GitHub Actions (`windows-latest`, Python 3.10 and 3.11) for every push and pull request to `main`.
