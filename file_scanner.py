
from pathlib import Path
from datetime import datetime
import os

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"},
    "Spreadsheets": {".xls", ".xlsx", ".csv"},
    "Presentations": {".ppt", ".pptx"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
    "Audio": {".mp3", ".wav", ".aac", ".m4a", ".ogg"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".html", ".css", ".java", ".cpp"},
}

SCREENSHOT_WORDS = (
    "screenshot", "screen shot", "screen_shot",
    "snipping tool", "capture",
)

WHATSAPP_WORDS = ("whatsapp", "com.whatsapp")


def get_category(file_path):
    extension = Path(file_path).suffix.lower()

    for category, extensions in CATEGORIES.items():
        if extension in extensions:
            return category

    return "Others"


def is_screenshot(file_path):
    name = Path(file_path).stem.lower()
    return any(word in name for word in SCREENSHOT_WORDS)


def is_whatsapp_file(file_path):
    path_text = str(file_path).lower()
    return any(word in path_text for word in WHATSAPP_WORDS)


def scan_files(folder_path):
    root = Path(folder_path).expanduser().resolve()

    if not root.is_dir():
        raise ValueError("Select a valid existing folder.")

    results = []
    excluded = {"logs", "reports", "venv", ".git", "__pycache__"}

    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in excluded]

        for filename in filenames:
            path = Path(current_root) / filename

            try:
                if path.is_symlink() or not path.is_file():
                    continue

                stat = path.stat()
                modified = datetime.fromtimestamp(stat.st_mtime)
                age_days = max(
                    0, (datetime.now() - modified).days
                )

                results.append({
                    "name": path.name,
                    "path": str(path.resolve()),
                    "extension": path.suffix.lower(),
                    "category": get_category(path),
                    "size_bytes": stat.st_size,
                    "size_kb": round(stat.st_size / 1024, 2),
                    "modified": modified.strftime("%Y-%m-%d %H:%M"),
                    "age_days": age_days,
                    "is_screenshot": is_screenshot(path),
                    "is_whatsapp": is_whatsapp_file(path),
                })

            except OSError:
                continue

    return results


def find_old_files(files, days=30):
    return [
        item for item in files
        if item["age_days"] >= days
    ]