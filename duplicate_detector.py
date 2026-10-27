
import hashlib
from collections import defaultdict
from pathlib import Path


def calculate_hash(file_path):
    digest = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def find_duplicates(files):
    groups = defaultdict(list)

    for item in files:
        try:
            path = Path(item["path"])

            if path.is_file() and not path.is_symlink():
                digest = calculate_hash(path)
                groups[digest].append(str(path))

        except OSError:
            continue

    return [
        {
            "sha256": digest,
            "count": len(paths),
            "files": paths,
        }
        for digest, paths in groups.items()
        if len(paths) > 1
    ]