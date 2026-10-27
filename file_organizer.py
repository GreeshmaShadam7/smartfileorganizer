
import shutil
from pathlib import Path


def unique_destination(path):
    """Generate a new filename if the destination already exists."""
    path = Path(path)

    if not path.exists():
        return path

    counter = 1
    while True:
        new_path = path.with_name(
            f"{path.stem}_{counter}{path.suffix}"
        )
        if not new_path.exists():
            return new_path
        counter += 1


def organize_files(records, root_folder, mode="category"):
    """
    Move selected file records into the appropriate folders.
    Returns a result dictionary for each file.
    """
    root = Path(root_folder).resolve()
    results = []

    folder_names = {
        "whatsapp": "WhatsApp_Files",
        "screenshots": "Screenshots",
        "unused": "Unused_Files",
    }

    for record in records:
        source = Path(record["path"])

        try:
            if not source.is_file():
                results.append({
                    "file": str(source),
                    "status": "SKIPPED",
                    "message": "File does not exist."
                })
                continue

            source = source.resolve()

            # Only organize files inside the selected root folder.
            if not source.is_relative_to(root):
                results.append({
                    "file": str(source),
                    "status": "SKIPPED",
                    "message": "File is outside the selected folder."
                })
                continue

            if mode == "category":
                folder_name = record.get("category", "Others")
            elif mode in folder_names:
                folder_name = folder_names[mode]
            else:
                folder_name = "Others"

            destination_folder = root / folder_name

            # Avoid moving a file into its own folder repeatedly.
            if source.parent == destination_folder.resolve():
                results.append({
                    "file": str(source),
                    "status": "SKIPPED",
                    "message": "File is already organized."
                })
                continue

            destination_folder.mkdir(parents=True, exist_ok=True)
            destination = unique_destination(
                destination_folder / source.name
            )

            shutil.move(str(source), str(destination))

            results.append({
                "file": str(source),
                "status": "SUCCESS",
                "message": f"Moved to {destination}"
            })

        except (OSError, ValueError, shutil.Error) as error:
            results.append({
                "file": str(source),
                "status": "FAILED",
                "message": str(error)
            })

    return results