import sys
from shutil import move
from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

def convert_date(timestamp):
    """Convert a timestamp into a formatted date string."""
    date = datetime.fromtimestamp(timestamp)
    return date.strftime('%Y %m %d')

VALID_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".cr2")

if __name__ == "__main__":
    root = Tk()
    root.withdraw()  # Hide the root window


    source_dir = filedialog.askdirectory(title="Select Source Directory")
    if not source_dir:
        messagebox.showerror("Error", "Source directory not selected!")
        sys.exit()

    source_dir = Path(source_dir)

    dest_dir = filedialog.askdirectory(title="Select Destination Directory")
    if not dest_dir:
        messagebox.showerror("Error", "Destination directory not selected!")
    dest_dir = Path(dest_dir)

    for entry in source_dir.rglob("*"):
        if entry.name.endswith(VALID_IMAGE_EXTENSIONS):
            file_path = entry
            creation_date  = convert_date(entry.stat().st_ctime)
            folder_name = creation_date .replace(' ', '-')
            target_folder  = Path(dest_dir.joinpath(folder_name))
            if not Path.exists(target_folder ):
                Path.mkdir(target_folder )
            move(file_path, target_folder )
