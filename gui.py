"""CustomTkinter desktop interface for SnapSorter.

All sorting logic lives in photo_sorter.py; nothing here is imported by the
backend, and the backend never imports this module.
"""
import queue
import threading
from pathlib import Path
from tkinter import TclError, filedialog

import customtkinter as ctk

from photo_sorter import sort_photos, validate_directories

ACCENT_OK = "#2d8a4e"
ACCENT_ERROR = "#c0392b"
ACCENT_WARN = "#b7791f"


class Modal(ctk.CTkToplevel):
    """A small centred, grab-modal dialog built from CustomTkinter widgets."""

    def __init__(self, parent, title, heading, detail="", buttons=(("OK", True),),
                 accent=None):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=28, pady=24, fill="both", expand=True)

        ctk.CTkLabel(body, text=heading, font=ctk.CTkFont(size=16, weight="bold"),
                     wraplength=420, justify="left").pack(anchor="w")
        if detail:
            ctk.CTkLabel(body, text=detail, wraplength=420, justify="left",
                         text_color=("gray35", "gray70")).pack(anchor="w", pady=(10, 0))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(pady=(24, 0), anchor="e")
        for label, value in buttons:
            ctk.CTkButton(
                row, text=label, width=110,
                fg_color=accent or ("gray65", "gray25"), hover_color=("gray55", "gray20"),
                text_color="white" if accent else None,
                command=lambda v=value: self._choose(v),
            ).pack(side="right", padx=(8, 0))

        self.update_idletasks()
        self._center()
        self.after(20, self._focus)
        self.protocol("WM_DELETE_WINDOW", self._dismiss)
        try:
            self.grab_set()
        except TclError:
            # Another grab is already active (a stale modal, or another app).
            # Without the grab the dialog is still usable, just not enforced.
            # This must never propagate: it would escape the button callback
            # that opened the dialog and lose the sort result.
            pass

    def _center(self):
        # See SortApp._center: update() first, or the requested geometry is
        # not applied yet and the measured size is the pre-mapped default.
        self.update()
        width, height = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 3
        self.geometry(f"+{x}+{y}")

    def _focus(self):
        try:
            self.focus_force()
        except Exception:
            pass

    def _choose(self, value):
        self.result = value
        self.destroy()

    def _dismiss(self):
        # Closing the window counts as a cancel, never as confirmation.
        self.result = None
        self.destroy()

    def ask(self):
        """Block until dismissed, then return the chosen value."""
        self.master.wait_window(self)
        return self.result


class SortApp(ctk.CTk):
    """Main window: pick two folders, then sort them in the background."""

    def __init__(self):
        super().__init__()
        self.title("SnapSorter")
        self.geometry("780x640")
        self.minsize(660, 560)
        self._thread = None
        self._events = queue.Queue()
        self._closing = False
        self._source = ""
        self._destination = ""
        # Closing mid-sort leaves the daemon worker running; stop polling so a
        # scheduled _poll cannot fire against a destroyed widget.
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._center()
        self._build()
        self._refresh_controls()

    def _center(self):
        # update_idletasks() alone leaves the requested geometry unapplied, so
        # winfo_width() can still report the pre-mapped default and the window
        # lands off-centre. A full update() settles it first.
        self.update()
        width, height = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"+{x}+{y}")

    # --- layout ---------------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        # Row 5 holds the log frame (see _build below), so that is the row that
        # must absorb extra height. Weighting row 4 instead leaves the log
        # pinned at its natural height and opens a dead band beneath the
        # progress bar on taller windows.
        self.grid_rowconfigure(5, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="SnapSorter", anchor="w",
                     font=ctk.CTkFont(size=26, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Move photos into folders named by capture date.",
                     anchor="w", text_color=("gray35", "gray70")).grid(
            row=1, column=0, sticky="w", pady=(2, 0))

        self._path_row(1, "Source Directory", "source")
        self._path_row(2, "Destination Directory", "destination")

        self.start_button = ctk.CTkButton(
            self, text="Start Sorting", height=42,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_start)
        self.start_button.grid(row=3, column=0, sticky="ew", padx=24, pady=(18, 0))

        status = ctk.CTkFrame(self, fg_color="transparent")
        status.grid(row=4, column=0, sticky="ew", padx=24, pady=(16, 4))
        status.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(status, height=8)
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew")
        self.status_label = ctk.CTkLabel(status, text="Ready.", anchor="w",
                                        text_color=("gray35", "gray70"))
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=5, column=0, sticky="nsew", padx=24, pady=(10, 24))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(log_frame, text="Activity log", anchor="w",
                     font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w",
                                                           padx=12, pady=(10, 4))
        self.log = ctk.CTkTextbox(log_frame, wrap="word", font=ctk.CTkFont(size=12))
        self.log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.log.tag_config("ok", foreground=ACCENT_OK)
        self.log.tag_config("err", foreground=ACCENT_ERROR)
        self.log.configure(state="disabled")

    def _path_row(self, row, label, key):
        frame = ctk.CTkFrame(self)
        frame.grid(row=row, column=0, sticky="ew", padx=24, pady=(14, 0))
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=label, anchor="w", width=170,
                     justify="left").grid(row=0, column=0, sticky="w", padx=(14, 10), pady=12)

        # A read-only CTkEntry silently discards insert() in CustomTkinter 6.x,
        # so the path is shown in a bordered label instead.
        field = ctk.CTkFrame(frame, corner_radius=6)
        field.grid(row=0, column=1, sticky="ew", pady=8)
        field.grid_columnconfigure(0, weight=1)
        value = ctk.CTkLabel(field, text="No folder selected", anchor="w",
                             text_color=("gray50", "gray55"), justify="left")
        value.grid(row=0, column=0, sticky="ew", padx=10, pady=7)
        field.bind("<Configure>",
                   lambda event, label=value, host=field: label.configure(
                       wraplength=max(180, event.width - 24)))

        button = ctk.CTkButton(frame, text="Browse", width=96,
                               command=lambda: self._browse(key))
        button.grid(row=0, column=2, padx=(10, 12), pady=8)
        setattr(self, f"_{key}_label", value)
        setattr(self, f"_{key}_button", button)

    # --- selection ------------------------------------------------------

    def _browse(self, key):
        chosen = filedialog.askdirectory(title=f"Select {key.title()} Directory",
                                        mustexist=True)
        if not chosen:
            return
        if key == "source":
            self._source = chosen
        else:
            self._destination = chosen
        getattr(self, f"_{key}_label").configure(text=chosen)
        self._log(f"{key.title()}: {chosen}")
        self._refresh_controls()

    def _ready(self):
        for path in (self._source, self._destination):
            if not path or not Path(path).is_dir():
                return False
        return True

    def _running(self):
        return self._thread is not None and self._thread.is_alive()

    def _refresh_controls(self):
        running = self._running()
        for key in ("source", "destination"):
            getattr(self, f"_{key}_button").configure(
                state="disabled" if running else "normal")
        if running:
            self.start_button.configure(state="disabled", text="Sorting...")
        elif self._ready():
            self.start_button.configure(state="normal")
        else:
            self.start_button.configure(state="disabled", text="Start Sorting")

    # --- logging --------------------------------------------------------

    def _log(self, message, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n", tag or ())
        self.log.configure(state="disabled")
        self.log.see("end")

    # --- execution ------------------------------------------------------

    def _on_start(self):
        if not self._ready():
            return
        source, destination = self._source, self._destination

        # Report a bad combination up front rather than after a confirmation.
        try:
            validate_directories(Path(source), Path(destination))
        except ValueError as exc:
            Modal(self, "Cannot sort", "Those folders cannot be used together.",
                  detail=str(exc), accent=ACCENT_ERROR).ask()
            return

        # No file count here on purpose: counting means walking the whole tree,
        # which blocks the GUI thread for the duration -- exactly the freeze
        # the background worker exists to avoid. The dialog says what will
        # happen instead of guessing a number.
        confirmed = Modal(
            self,
            "Confirm move",
            f"Move photos from\n{source}\nto\n{destination}?",
            detail=(
                "Every supported image in the source, including subfolders, will be "
                "moved, not copied, so this cannot be undone."
            ),
            buttons=(("Cancel", False), ("Move Files", True)),
            accent=ACCENT_WARN,
        ).ask()
        if confirmed is not True:
            self._log("Cancelled by user.", "err")
            return

        self._start_sorting(source, destination)

    def _start_sorting(self, source, destination):
        self.progress.set(0)
        self.status_label.configure(text="Scanning folders...")
        self._log("--- Sorting started ---")
        self._refresh_controls()

        def worker():
            # Off the GUI thread so a long scan cannot freeze the window.
            # The worker never touches Tk: Tk calls from a non-main thread
            # only marshal while the main thread blocks inside mainloop(),
            # so results travel through a queue that _poll() drains instead.
            def on_progress(processed, total, entry, target, error):
                self._events.put(("file", processed, total, entry, target, error))

            try:
                result = sort_photos(source, destination, on_progress=on_progress)
            except Exception as exc:  # unexpected: surface it, never crash
                self._events.put(("fatal", exc))
                return
            self._events.put(("done", *result))

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        self._poll()

    def _poll(self):
        """Drain worker events on the GUI thread until the run is finished."""
        if self._closing:
            return
        handlers = {"file": self._on_file, "fatal": self._on_fatal, "done": self._on_done}
        try:
            while True:
                try:
                    kind, *payload = self._events.get_nowait()
                except queue.Empty:
                    break
                handlers[kind](*payload)
        except TclError:
            return  # window went away mid-drain
        if self._running() or not self._events.empty():
            self.after(40, self._poll)

    def _on_close(self):
        self._closing = True
        self.destroy()

    # --- worker callbacks (always on the GUI thread via after) ----------

    def _on_file(self, processed, total, entry, target, error):
        self.progress.set(processed / total if total else 1)
        if error is not None:
            self._log(f"FAILED  {entry.name}: {error}", "err")
        else:
            self._log(f"Moved   {entry.name}  ->  {target}")
        self.status_label.configure(text=f"Sorted {processed} of {total}...")

    def _on_fatal(self, exc):
        self._thread = None
        self.status_label.configure(text="Stopped.")
        self._log(f"Aborted: {exc}", "err")
        self._refresh_controls()
        Modal(self, "Sorting stopped", "Sorting could not continue.",
              detail=str(exc), accent=ACCENT_ERROR).ask()

    def _on_done(self, moved, failures):
        self._thread = None
        self.progress.set(1)
        self.status_label.configure(text=f"Done - {moved} moved, {len(failures)} failed.")
        self._log(f"--- Finished: {moved} moved, {len(failures)} failed ---",
                  "err" if failures else "ok")
        self._refresh_controls()

        if failures:
            detail = (
                f"{moved} file(s) moved successfully.\n\n"
                f"{len(failures)} file(s) failed; see the activity log for details."
            )
            accent = ACCENT_ERROR
        else:
            detail = f"{moved} file(s) moved into {self._destination}."
            accent = ACCENT_OK
        Modal(self, "Sorting complete",
              "Sorting complete." if not failures else "Sorting finished with errors",
              detail=detail, accent=accent).ask()


def main():
    """Launch the desktop interface."""
    # "system" follows the OS light/dark preference.
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = SortApp()
    app.mainloop()


if __name__ == "__main__":
    main()
