
import os
import shutil
import hashlib
import csv
import json
import logging
import struct
import tkinter as tk

from pathlib import Path
from datetime import datetime, timedelta
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Smart File Organizer & Audit System"

logging.basicConfig(
    filename="file_activity.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)


# ---------------- FILE CATEGORIES ----------------

def get_category(file_path):
    ext = Path(file_path).suffix.lower()

    categories = {
        "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"],
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
        "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv"],
        "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg"],
        "Spreadsheets": [".xls", ".xlsx", ".csv"],
        "Presentations": [".ppt", ".pptx"],
        "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "Code": [".py", ".java", ".js", ".html", ".css", ".cpp", ".c"],
        "Executables": [".exe", ".msi", ".bat", ".sh"],
    }

    for category, extensions in categories.items():
        if ext in extensions:
            return category

    return "Others"


def unique_destination(path):
    path = Path(path)

    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(
            f"{path.stem}_{counter}{path.suffix}"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def calculate_hash(file_path):
    digest = hashlib.sha256()

    try:
        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


# ---------------- SCREENSHOT DETECTION ----------------

def image_dimensions(path):
    """Read dimensions of common image files without external packages."""
    try:
        with open(path, "rb") as file:
            header = file.read(32)

            # PNG
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                return struct.unpack(">II", header[16:24])

            # GIF
            if header.startswith((b"GIF87a", b"GIF89a")):
                return struct.unpack("<HH", header[6:10])

            # BMP
            if header.startswith(b"BM") and len(header) >= 26:
                width, height = struct.unpack("<ii", header[18:26])
                return abs(width), abs(height)

            # WebP extended format
            if (
                header[:4] == b"RIFF"
                and header[8:12] == b"WEBP"
                and header[12:16] == b"VP8X"
                and len(header) >= 30
            ):
                width = 1 + int.from_bytes(header[24:27], "little")
                height = 1 + int.from_bytes(header[27:30], "little")
                return width, height

    except (OSError, ValueError, struct.error):
        pass

    return None


def is_screenshot(record):
    path = Path(record["path"])
    name = path.stem.lower()
    parts = [part.lower().strip() for part in path.parts]

    keywords = (
        "screenshot",
        "screen_shot",
        "screen-shot",
        "screen shot",
        "screen_capture",
        "screen-capture",
        "screen capture",
        "snipping tool",
        "snip_",
    )

    if any(word in name for word in keywords):
        return True

    screenshot_folders = {
        "screenshots",
        "screen shots",
        "screen captures",
        "screenshot",
    }

    if any(part in screenshot_folders for part in parts[:-1]):
        return True

    # Heuristic only: tall display-shaped images may be screenshots.
    if path.suffix.lower() in (
        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"
    ):
        dimensions = image_dimensions(path)

        if dimensions:
            width, height = dimensions
            if (
                width >= 700
                and height >= 1200
                and height / max(width, 1) >= 1.45
            ):
                return True

    return False


# ---------------- WHATSAPP DETECTION ----------------

def is_whatsapp_file(record):
    """Detect WhatsApp files by folder path or filename."""
    path = Path(record["path"])
    parts = [part.lower().strip() for part in path.parts]
    name = path.stem.lower().replace("-", "_").replace(" ", "_")

    whatsapp_folders = {
        "whatsapp", "whatsapp media", "whatsapp images",
        "whatsapp image", "whatsapp video", "whatsapp videos",
        "whatsapp documents", "whatsapp document", "whatsapp audio",
        "whatsapp voice notes", "whatsapp stickers",
        "whatsapp animated gifs", "whatsapp profile photos",
        "com.whatsapp", "com.whatsapp.w4b",
    }

    if any(part in whatsapp_folders for part in parts[:-1]):
        return True

    # Match files like WhatsApp_photo.jpg, valid_whatsapp.png,
    # WhatsApp_invoice.pdf, WhatsApp_voice.mp3, etc.
    if "whatsapp" in name:
        return True

    return any(part.startswith("whatsapp_") for part in parts[:-1])


def whatsapp_subfolder(file_path):
    """Return the WhatsApp media subfolder based on the file extension."""
    ext = Path(file_path).suffix.lower()

    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
        return "WhatsApp Images"
    if ext in {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".3gp"}:
        return "WhatsApp Video"
    if ext in {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".opus"}:
        return "WhatsApp Audio"
    if ext in {
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
        ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".zip", ".rar"
    }:
        return "WhatsApp Documents"
    return "WhatsApp Documents"


def get_organized_destination(record, root_folder):
    """Choose a destination folder, prioritizing WhatsApp and screenshots."""
    path = Path(record["path"])

    if is_whatsapp_file(record):
        return root_folder / "WhatsApp Media" / whatsapp_subfolder(path)

    if is_screenshot(record):
        return root_folder / "Screenshots"

    return root_folder / get_category(path)


# ---------------- APPLICATION ----------------

class SmartFileOrganizer:

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1150x680")
        self.root.minsize(900, 520)

        self.folder_path = tk.StringVar()
        self.status = tk.StringVar(value="Select a working folder.")

        self.files = []
        self.visible_files = []

        self.create_ui()

    def create_ui(self):
        folder_frame = ttk.Frame(self.root, padding=10)
        folder_frame.pack(fill="x")

        ttk.Label(
            folder_frame, text="Working Folder:"
        ).pack(side="left")

        ttk.Entry(
            folder_frame,
            textvariable=self.folder_path
        ).pack(side="left", fill="x", expand=True, padx=5)

        ttk.Button(
            folder_frame,
            text="Browse",
            command=self.browse_folder
        ).pack(side="left")

        # Upload folder first; separate buttons actually move files.
        button_frame = ttk.Frame(
            self.root, padding=(10, 0, 10, 10)
        )
        button_frame.pack(fill="x")

        buttons = [
            ("Upload Folder", self.upload_files),
            ("Scan Folder", self.scan_folder),
            ("Organize Folder", self.organize_category),
            ("WhatsApp Files", self.show_whatsapp_files),
            ("Screenshots", self.show_screenshots),
            ("Old Files", self.show_old_files),
            ("Find Duplicates", self.find_duplicates),
        ]

        for text, command in buttons:
            ttk.Button(
                button_frame,
                text=text,
                command=command
            ).pack(side="left", padx=2, pady=3)

        table_frame = ttk.Frame(
            self.root, padding=(10, 0, 10, 5)
        )
        table_frame.pack(fill="both", expand=True)

        columns = ("name", "category", "size", "modified", "path")

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="extended"
        )

        headings = {
            "name": ("File Name", 180),
            "category": ("Category", 120),
            "size": ("Size (KB)", 90),
            "modified": ("Last Modified", 150),
            "path": ("Full Path", 480),
        }

        for column, (heading, width) in headings.items():
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, minwidth=70)

        y_scroll = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
        x_scroll = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill="x")

        ttk.Button(
            bottom_frame, text="Select All", command=self.select_all
        ).pack(side="left", padx=3)

        ttk.Button(
            bottom_frame, text="Export CSV", command=self.export_csv
        ).pack(side="left", padx=3)

        ttk.Button(
            bottom_frame, text="Export JSON", command=self.export_json
        ).pack(side="left", padx=3)

        ttk.Button(
            bottom_frame, text="View Activity Log", command=self.view_log
        ).pack(side="left", padx=3)

        ttk.Label(
            self.root,
            textvariable=self.status,
            relief="sunken",
            anchor="w",
            padding=5
        ).pack(fill="x", side="bottom")

    def browse_folder(self):
        folder = filedialog.askdirectory(
            title="Select Working Folder"
        )
        if folder:
            self.folder_path.set(folder)

    def get_root_folder(self):
        folder = self.folder_path.get().strip()

        if not folder or not os.path.isdir(folder):
            messagebox.showerror(
                "Invalid Folder",
                "Please select a valid working folder."
            )
            return None

        return Path(folder).resolve()

    # -------- Upload an entire test folder --------

    def upload_files(self):
        destination = self.get_root_folder()
        if destination is None:
            return

        source_folder = filedialog.askdirectory(
            title="Select Entire Test Folder to Upload"
        )
        if not source_folder:
            return

        source = Path(source_folder).resolve()

        if (
            source == destination
            or source in destination.parents
            or destination in source.parents
        ):
            messagebox.showerror(
                "Invalid Folder",
                "Choose separate source and destination folders."
            )
            return

        target_root = destination / source.name

        if target_root.exists() and not messagebox.askyesno(
            "Folder Exists",
            "The destination folder already exists. "
            "Copy files into it while preserving existing files?"
        ):
            return

        copied = 0
        failed = []

        for current_root, dirs, filenames in os.walk(source):
            # Do not follow directory symlinks.
            dirs[:] = [
                name for name in dirs
                if not (Path(current_root) / name).is_symlink()
            ]

            current_path = Path(current_root)
            relative_path = current_path.relative_to(source)
            target_folder = target_root / relative_path

            try:
                target_folder.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                failed.append(f"{current_path}: {error}")
                dirs[:] = []
                continue

            for filename in filenames:
                source_file = current_path / filename

                try:
                    if source_file.is_symlink():
                        continue

                    target_file = unique_destination(
                        target_folder / filename
                    )
                    shutil.copy2(source_file, target_file)
                    copied += 1

                except OSError as error:
                    failed.append(f"{filename}: {error}")

        logging.info(
            "Uploaded folder %s to %s; copied=%d",
            source, target_root, copied
        )

        result = f"Files copied: {copied}\nDestination: {target_root}"
        if failed:
            result += f"\nFailed: {len(failed)}"

        messagebox.showinfo("Folder Upload", result)
        self.status.set(
            f"Copied {copied} files. Click Scan Folder to display them."
        )

    # -------- Scan folder --------

    def scan_folder(self):
        root_folder = self.get_root_folder()
        if root_folder is None:
            return

        self.files = []

        excluded = {
            "logs", "reports", "venv", ".git", "__pycache__"
        }

        for current_root, dirs, filenames in os.walk(root_folder):
            dirs[:] = [
                d for d in dirs
                if d.lower() not in excluded
            ]

            for filename in filenames:
                path = Path(current_root) / filename

                try:
                    if not path.is_file():
                        continue

                    stat = path.stat()

                    self.files.append({
                        "name": path.name,
                        "path": str(path.resolve()),
                        "category": get_category(path),
                        "size": round(stat.st_size / 1024, 2),
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime
                        ).strftime("%Y-%m-%d %H:%M"),
                    })

                except OSError:
                    continue

        self.show_records(self.files)
        self.status.set(f"Scan complete: {len(self.files)} files found.")
        logging.info("Scanned %s", root_folder)

    def show_records(self, records):
        self.visible_files = list(records)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, record in enumerate(self.visible_files):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    record["name"],
                    record["category"],
                    record["size"],
                    record["modified"],
                    record["path"],
                )
            )

        self.status.set(f"Displaying {len(self.visible_files)} files.")

    def selected_records(self):
        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Select one or more files from the table first."
            )
            return []

        return [
            self.visible_files[int(item)]
            for item in selected
            if int(item) < len(self.visible_files)
        ]

    # -------- Safe file moving --------

    def move_records(self, records, folder_name):
        root_folder = self.get_root_folder()
        if root_folder is None:
            return

        destination_folder = root_folder / folder_name
        moved = skipped = failed = 0

        for record in records:
            source = Path(record["path"])

            try:
                if not source.is_file():
                    skipped += 1
                    continue

                source = source.resolve()

                if not source.is_relative_to(root_folder):
                    skipped += 1
                    continue

                # Skip files already in the target folder.
                if source.parent == destination_folder.resolve():
                    skipped += 1
                    continue

                destination_folder.mkdir(parents=True, exist_ok=True)
                destination = unique_destination(
                    destination_folder / source.name
                )

                shutil.move(str(source), str(destination))
                logging.info("Moved %s -> %s", source, destination)
                moved += 1

            except (OSError, ValueError, shutil.Error) as error:
                logging.error("Move failed for %s: %s", source, error)
                failed += 1

        messagebox.showinfo(
            "Move Result",
            f"Moved: {moved}\nSkipped: {skipped}\nFailed: {failed}"
        )

        self.scan_folder()

    # -------- Preview and organize all files automatically --------

    def organize_category(self):
        root_folder = self.get_root_folder()
        if root_folder is None:
            return

        # Refresh the scan so the preview includes the latest files.
        self.scan_folder()
        records = list(self.files)

        if not records:
            messagebox.showinfo("Organize Folder", "No files found to organize.")
            return

        # Build a preview plan without moving files or creating folders.
        plan = []
        for record in records:
            source = Path(record["path"])
            try:
                source = source.resolve()
                if not source.is_file() or not source.is_relative_to(root_folder):
                    continue
                destination_folder = get_organized_destination(record, root_folder)
                if source.parent == destination_folder.resolve():
                    destination_text = f"Already organized: {destination_folder.name}"
                else:
                    destination_text = str(destination_folder.relative_to(root_folder))
                plan.append({
                    "record": record,
                    "source": source,
                    "destination_folder": destination_folder,
                    "destination_text": destination_text,
                    "already": source.parent == destination_folder.resolve(),
                })
            except (OSError, ValueError):
                continue

        if not plan:
            messagebox.showinfo("Organize Folder", "No eligible files found to organize.")
            return

        preview = tk.Toplevel(self.root)
        preview.title("Organization Preview")
        preview.geometry("900x520")
        preview.transient(self.root)
        preview.grab_set()

        ttk.Label(
            preview,
            text=f"Preview: {len(plan)} files — nothing has been moved yet",
            font=("Segoe UI", 11, "bold"),
            padding=10,
        ).pack(fill="x")

        table_frame = ttk.Frame(preview, padding=(10, 0, 10, 10))
        table_frame.pack(fill="both", expand=True)
        columns = ("name", "category", "destination", "status")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        tree.heading("name", text="File Name")
        tree.heading("category", text="Detected Type")
        tree.heading("destination", text="Destination Folder")
        tree.heading("status", text="Action")
        tree.column("name", width=230)
        tree.column("category", width=120)
        tree.column("destination", width=350)
        tree.column("status", width=130)

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        for item in plan:
            record = item["record"]
            if is_whatsapp_file(record):
                detected = "WhatsApp"
            elif is_screenshot(record):
                detected = "Screenshot"
            else:
                detected = get_category(item["source"])
            action = "Already organized" if item["already"] else "Move"
            tree.insert("", "end", values=(
                item["source"].name,
                detected,
                item["destination_text"],
                action,
            ))

        footer = ttk.Frame(preview, padding=10)
        footer.pack(fill="x")
        ttk.Label(
            footer,
            text="WhatsApp files go into WhatsApp Media subfolders; screenshots go into Screenshots.",
        ).pack(side="left", fill="x", expand=True)

        def perform_organization():
            # Ask for final confirmation after the user reviews the preview.
            confirmed = messagebox.askyesno(
                "Confirm Organization",
                f"Organize all {len(plan)} files shown in the preview now?\n\n"
                "Files will be moved into their destination folders.\n"
                "Files already organized will remain where they are.",
                parent=preview,
            )
            if not confirmed:
                return

            preview.destroy()
            moved = already_organized = skipped = failed = 0
            skipped_details = []
            failed_details = []

            for item in plan:
                source = item["source"]
                destination_folder = item["destination_folder"]
                try:
                    if not source.exists():
                        skipped += 1
                        reason = "File no longer exists (it may have been moved or deleted)."
                        skipped_details.append(f"SKIPPED | {source} | {reason}")
                        logging.warning("Skipped %s: %s", source, reason)
                        continue

                    if not source.is_file():
                        skipped += 1
                        reason = "Path is not a file."
                        skipped_details.append(f"SKIPPED | {source} | {reason}")
                        logging.warning("Skipped %s: %s", source, reason)
                        continue

                    source = source.resolve()
                    if not source.is_relative_to(root_folder):
                        skipped += 1
                        reason = "File is outside the selected working folder (safety protection)."
                        skipped_details.append(f"SKIPPED | {source} | {reason}")
                        logging.warning("Skipped %s: %s", source, reason)
                        continue

                    destination_folder = destination_folder.resolve()
                    if source.parent == destination_folder:
                        already_organized += 1
                        logging.info("Already organized: %s", source)
                        continue

                    destination_folder.mkdir(parents=True, exist_ok=True)
                    destination = unique_destination(destination_folder / source.name)
                    shutil.move(str(source), str(destination))
                    logging.info("Organized %s -> %s", source, destination)
                    moved += 1

                except (OSError, ValueError, shutil.Error) as error:
                    failed += 1
                    failed_details.append(f"FAILED | {source} | {error}")
                    logging.error("Organization failed for %s: %s", source, error)

            result = (
                f"Total files in preview: {len(plan)}\n"
                f"Moved to correct folders: {moved}\n"
                f"Already organized: {already_organized}\n"
                f"Could not process: {skipped}\n"
                f"Failed due to errors: {failed}\n\n"
                f"Folders organized inside: {root_folder}"
            )
            messagebox.showinfo("Organization Result", result, parent=self.root)
            self.scan_folder()

            # Show exact reasons so skipped files are no longer unexplained.
            details = skipped_details + failed_details
            if details:
                detail_window = tk.Toplevel(self.root)
                detail_window.title("Skipped / Failed File Details")
                detail_window.geometry("900x450")
                detail_window.transient(self.root)

                ttk.Label(
                    detail_window,
                    text=f"Details: {len(skipped_details)} could not process, {len(failed_details)} failed",
                    font=("Segoe UI", 10, "bold"),
                    padding=10,
                ).pack(fill="x")

                text_frame = ttk.Frame(detail_window, padding=(10, 0, 10, 10))
                text_frame.pack(fill="both", expand=True)
                detail_text = tk.Text(text_frame, wrap="word")
                detail_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=detail_text.yview)
                detail_text.configure(yscrollcommand=detail_scroll.set)
                detail_text.pack(side="left", fill="both", expand=True)
                detail_scroll.pack(side="right", fill="y")
                detail_text.insert("1.0", "\n\n".join(details))
                detail_text.configure(state="disabled")

                ttk.Button(
                    detail_window,
                    text="Close",
                    command=detail_window.destroy,
                ).pack(anchor="e", padx=10, pady=(0, 10))

        ttk.Button(footer, text="Organize Now", command=perform_organization).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Cancel", command=preview.destroy).pack(side="right")

    # -------- WhatsApp features --------

    def show_whatsapp_files(self):
        records = [
            record for record in self.files
            if is_whatsapp_file(record)
        ]

        self.show_records(records)
        self.status.set(
            f"Found {len(records)} likely WhatsApp files."
        )

    # -------- Screenshot features --------

    def show_screenshots(self):
        records = [
            record for record in self.files
            if is_screenshot(record)
        ]

        self.show_records(records)
        self.status.set(
            f"Found {len(records)} likely screenshots."
        )

    # -------- Old files --------

    def show_old_files(self):
        cutoff = datetime.now() - timedelta(days=30)
        records = []

        for record in self.files:
            try:
                modified = datetime.fromtimestamp(
                    os.path.getmtime(record["path"])
                )
                if modified < cutoff:
                    records.append(record)
            except OSError:
                continue

        self.show_records(records)
        self.status.set(
            f"Found {len(records)} files older than 30 days."
        )

    # -------- Duplicate detection --------

    def find_duplicates(self):
        hashes = {}
        duplicates = []

        for record in self.files:
            digest = calculate_hash(record["path"])

            if digest is None:
                continue

            if digest in hashes:
                duplicates.append(record)
            else:
                hashes[digest] = record["path"]

        self.show_records(duplicates)
        self.status.set(
            f"Found {len(duplicates)} duplicate files. Nothing deleted."
        )

    # -------- Select and export --------

    def select_all(self):
        for item in self.tree.get_children():
            self.tree.selection_add(item)

    def export_csv(self):
        if not self.visible_files:
            messagebox.showwarning("No Data", "No files to export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )

        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "name", "path", "category", "size", "modified"
                    ]
                )
                writer.writeheader()
                writer.writerows(self.visible_files)

            messagebox.showinfo("Export", "CSV report saved.")

        except OSError as error:
            messagebox.showerror("Export Error", str(error))

    def export_json(self):
        if not self.visible_files:
            messagebox.showwarning("No Data", "No files to export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )

        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8") as file:
                json.dump(self.visible_files, file, indent=4)

            messagebox.showinfo("Export", "JSON report saved.")

        except OSError as error:
            messagebox.showerror("Export Error", str(error))

    # -------- Activity log --------

    def view_log(self):
        log_path = Path("file_activity.log")

        if not log_path.exists():
            messagebox.showinfo("Activity Log", "No activity logged yet.")
            return

        window = tk.Toplevel(self.root)
        window.title("Activity Log")
        window.geometry("800x450")

        text = tk.Text(window, wrap="word")
        scrollbar = ttk.Scrollbar(
            window, orient="vertical", command=text.yview
        )
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        try:
            text.insert("1.0", log_path.read_text(encoding="utf-8"))
            text.configure(state="disabled")
        except OSError as error:
            messagebox.showerror("Log Error", str(error))


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartFileOrganizer(root)
    root.mainloop()