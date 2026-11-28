import errno
import json
import os
import re
import sys
from pathlib import Path
from shutil import copyfileobj
from tempfile import NamedTemporaryFile


def fallback_settings_path():
    if sys.platform.startswith("linux"):
        xdg_data = Path(os.environ.get("XDG_DATA_HOME", ""))
        data_home = xdg_data if xdg_data.is_absolute() else Path.home() / ".local" / "share"
        return data_home / "GitHubFolderSync" / "settings" / "settings.json"
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "GitHubFolderSync" / "settings" / "settings.json"
    return None


def copy_if_newer(source, destination):
    try:
        source_file = source.open("rb")
    except FileNotFoundError:
        return

    with source_file:
        source_stat = os.fstat(source_file.fileno())
        try:
            if destination.stat().st_mtime_ns >= source_stat.st_mtime_ns:
                return
        except FileNotFoundError:
            pass

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as output:
                temporary = Path(output.name)
                copyfileobj(source_file, output)
            os.utime(temporary, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def portable_settings_path():
    if getattr(sys, "frozen", False):
        directory = Path(sys.executable).resolve().parent
    else:
        directory = Path(__file__).resolve().parents[1]
    return directory / "settings" / "settings.json"


def settings_path():
    portable = portable_settings_path()
    fallback = fallback_settings_path()
    if fallback is None or fallback == portable:
        return portable

    active = portable
    try:
        for data_directory in (portable.parent, portable.parent.parent / "cache"):
            data_directory.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=data_directory):
                pass
        copy_if_newer(fallback, portable)
    except OSError as error:
        if isinstance(error, PermissionError) or error.errno == errno.EROFS:
            active = fallback

    try:
        if active == fallback or fallback.parent.parent.is_dir():
            copy_if_newer(portable, fallback)
    except OSError:
        # The active copy is still usable when the other location is inaccessible.
        pass
    return active


def validate_token_reference(value):
    if value and not re.fullmatch(r"(?:v\{[^{}=\r\n]+\}|[A-Za-z0-9_-]+)", value):
        raise ValueError("Введите токен GitHub или ссылку вида v{VARIABLE_NAME}.")


def resolve_token(value):
    validate_token_reference(value)
    if not value.startswith("v{"):
        return value
    name = value[2:-1]
    token = os.environ.get(name)
    if token is None and sys.platform == "win32":
        import winreg

        for hive, key in (
            (winreg.HKEY_CURRENT_USER, r"Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        ):
            try:
                with winreg.OpenKey(hive, key) as environment:
                    token, kind = winreg.QueryValueEx(environment, name)
            except OSError:
                continue
            if kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                break

    if not isinstance(token, str) or not token.strip():
        raise ValueError(f"Переменная окружения «{name}» не задана или пуста.")
    token = token.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise ValueError(f"Переменная окружения «{name}» содержит недопустимое значение токена.")
    return token


def load_settings(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"users": {}, "profiles": {}, "default_profile": None}

    if not isinstance(data, dict):
        raise ValueError("Некорректный формат файла настроек.")
    users = data.get("users")
    if isinstance(users, list) and all(isinstance(user, str) and user for user in users):
        tokens = data.pop("tokens", {})
        if not isinstance(tokens, dict) or not all(
            user in users and isinstance(value, str) for user, value in tokens.items()
        ):
            raise ValueError("Некорректный формат токенов.")
        data["users"] = {
            user: {"token": tokens[user]} if tokens.get(user) else {} for user in users
        }

    if (
        not isinstance(data.get("users"), dict)
        or not all(
            user and isinstance(account, dict) and isinstance(account.get("token", ""), str)
            for user, account in data["users"].items()
        )
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
