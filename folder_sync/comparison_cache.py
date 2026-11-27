import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from .branches import Branch
from .comparison import Match
from .settings import copy_if_newer, fallback_settings_path, portable_settings_path, save_settings


def profile_cache_path(settings_file, name, folder, login, authenticated):
    identity = json.dumps([name, str(Path(folder).expanduser().absolute()), login.casefold(), authenticated])
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return settings_file.parent.parent / "cache" / f"{key}.json"


def cache_for_profile(settings_file, name, profile, users):
    login = profile["login"]
    authenticated = bool(users.get(login, {}).get("token"))
    return profile_cache_path(settings_file, name, profile["folder"], login, authenticated)


def sync_cache_locations(settings_file, preferences):
    portable = portable_settings_path()
    fallback = fallback_settings_path()
    if fallback is None or fallback == portable:
        return
    try:
        if settings_file == portable and not fallback.parent.parent.is_dir():
            return
    except OSError:
        return

    directions = [(portable, fallback)]
    if settings_file == portable:
        directions.insert(0, (fallback, portable))

    for source_settings, destination_settings in directions:
        for name, profile in preferences["profiles"].items():
            source = cache_for_profile(source_settings, name, profile, preferences["users"])
            destination = cache_for_profile(destination_settings, name, profile, preferences["users"])
            try:
                copy_if_newer(source, destination)
            except OSError:
                continue


def reconcile_cache(settings_file, preferences, renamed=None):
    directory = settings_file.parent.parent / "cache"
    try:
        if directory.is_symlink() or directory.is_junction():
            return
        files = list(directory.iterdir())
    except OSError:
        return

    used = {
        cache_for_profile(settings_file, name, profile, preferences["users"])
        for name, profile in preferences["profiles"].items()
    }
    if renamed is not None:
        old, new = renamed
        if old in files and old not in used and new in used and not old.is_symlink() and old.is_file():
            try:
                if not new.exists() or new.stat().st_mtime_ns < old.stat().st_mtime_ns:
                    old.replace(new)
            except OSError:
                used.add(old)

    for file in files:
        if file in used or not re.fullmatch(r"[0-9a-f]{64}\.json", file.name):
            continue
        try:
            if file.is_file() and not file.is_symlink():
                file.unlink(missing_ok=True)
        except OSError:
            continue


def save_preferences(path, data, renamed=None):
    save_settings(path, data)
    reconcile_cache(path, data, renamed)


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
