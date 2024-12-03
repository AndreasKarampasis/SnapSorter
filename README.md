# SnapSorter
PhotoSorter is a lightweight, user-friendly application that organizes your image files into neatly categorized folders based on their creation dates. Perfect for photographers, designers, or anyone looking to declutter their photo collections.

## Features
- **Organizes photos**: Sorts image files (`.png`, `.jpg`, `.jpeg`, `.cr2`) into folders by creation date.
- **Graphical User Interface**: Uses a file dialog to select source and destination directories, making it user-friendly and accessible.
- **Simple & Fast**: Minimal setup and easy-to-understand workflow.

## Prerequisites
- Python 3.7 or higher
- Required libraries:
  - `tkinter` (comes pre-installed with Python)
  - `shutil`
  - `pathlib`

## How It Works
1. **Select Source Directory**: The app will prompt you to select a directory containing image files.
2. **Select Destination Directory**: Choose where you’d like the organized folders to be created.
3. **Automatic Sorting**: The app will scan all files in the source directory, filter for image files, and move them into folders named by their creation date (e.g., `2024-12-03`).
