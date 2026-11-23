import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile


def settings_path():
    launch_file = sys.executable if getattr(sys, "frozen", False) else __file__
    return Path(launch_file).resolve().parent / "settings" / "settings.json"


def load_settings(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"users": [], "profiles": {}, "default_profile": None}

    if (
        not isinstance(data, dict)
        or not isinstance(data.get("users"), list)
        or not all(isinstance(user, str) and user for user in data["users"])
        or not isinstance(data.get("profiles"), dict)
        or not all(
            isinstance(profile, dict)
            and isinstance(profile.get("folder"), str)
            and isinstance(profile.get("login"), str)
            and profile["login"] in data["users"]
            for profile in data["profiles"].values()
        )
    ):
        raise ValueError("Некорректный формат файла настроек.")
    default = data.get("default_profile")
    if not isinstance(default, str) or default not in data["profiles"]:
        data["default_profile"] = None
    return data


def save_settings(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
