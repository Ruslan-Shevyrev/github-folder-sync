import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from branches import Branch
from comparison import Match
from settings import save_settings


def profile_cache_path(settings_file, name, folder, login, authenticated):
    identity = json.dumps([name, str(Path(folder).expanduser().absolute()), login.casefold(), authenticated])
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return settings_file.parent.parent / "cache" / f"{key}.json"


def load_cache(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["version"] != 1 or not isinstance(data["rows"], list):
            return None
        rows = []
        for row in data["rows"]:
            branches = row["branches"]
            values = {key: row[key] for key in ("name", "local_path", "github_url", "branch_error", "visibility")}
            if not all(isinstance(value, str) for value in values.values()):
                return None
            if not isinstance(branches, list) or not all(
                isinstance(branch, dict) and all(isinstance(value, str) for value in branch.values())
                for branch in branches
            ):
                return None
            rows.append(Match(**values, branches=tuple(Branch(**branch) for branch in branches)))
        return rows
    except (OSError, ValueError, TypeError, KeyError):
        return None


def save_cache(path, rows):
    records = []
    for row in rows:
        record = asdict(row)
        # Origin URLs can contain credentials and are only needed for live actions.
        record.pop("mismatched_origin")
        records.append(record)
    save_settings(path, {"version": 1, "rows": records})
