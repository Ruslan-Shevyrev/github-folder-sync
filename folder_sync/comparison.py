import json
import os
import re
import shutil
import stat
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .branches import Branch, BranchError, OriginMismatch, compare_branches


@dataclass(frozen=True)
class Match:
    name: str
    local_path: str = ""
    github_url: str = ""
    branches: tuple[Branch, ...] = ()
    branch_error: str = ""
    mismatched_origin: str = ""
    visibility: str = ""

    @property
    def origin_mismatch(self):
        return bool(self.local_path and self.github_url and self.branch_error == OriginMismatch.message)

    @property
    def status(self):
        if self.local_path and self.github_url:
            return "both"
        return "local" if self.local_path else "github"


def validate_login(login):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", login, re.ASCII | re.IGNORECASE) or len(login) > 39:
        raise ValueError("Введите логин GitHub, например octocat.")


def github_json(url, *, allow_missing=False, token=""):
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHubFolderComparison",
    })
    if token:
        if not url.startswith("https://api.github.com/"):
            raise ValueError("Invalid GitHub API URL.")
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response), response.headers.get("Link", "")
    except HTTPError as error:
        if error.code == 404 and allow_missing:
            return None, ""
        if error.code == 429 or (
            error.code == 403 and error.headers.get("X-RateLimit-Remaining") == "0"
        ):
            raise ValueError("Достигнут лимит запросов GitHub. Попробуйте позже.") from error
        raise ValueError(f"GitHub вернул ошибку HTTP {error.code}.") from error
    except (URLError, TimeoutError, OSError) as error:
        raise ValueError("Не удалось загрузить репозитории. Проверьте подключение к GitHub.") from error


def github_repositories(login, token=""):
    validate_login(login)
    url = f"https://api.github.com/users/{login}/repos?type=owner&sort=full_name&per_page=100"
    if token:
        account, _ = github_json("https://api.github.com/user", token=token)
        if account["login"].casefold() != login.casefold():
            raise ValueError("Токен GitHub принадлежит другому пользователю.")
        url = "https://api.github.com/user/repos?affiliation=owner&sort=full_name&per_page=100"
    repositories = {}
    while url:
        page, link = github_json(url, allow_missing=not repositories, token=token)
        if page is None:
            raise ValueError(f"Аккаунт GitHub «{login}» не найден.")
        repositories.update(
            (repo["name"], Match(repo["name"], github_url=repo["html_url"], visibility=repo["visibility"]))
            for repo in page
            if not token or repo["owner"]["login"].casefold() == login.casefold()
        )
        next_page = re.search(r'<(https://api\.github\.com/[^>]+)>;\s*rel="next"', link)
        url = next_page.group(1) if next_page else None
    return repositories


def refresh_repository(folder, login, name, token=""):
    validate_login(login)
    root = Path(folder).expanduser().absolute()
    if not root.is_dir():
        raise ValueError(f"Локальная папка «{root}» недоступна.")
    candidate = root / name
    local_path = str(candidate) if candidate.is_dir() else ""
    repo, _ = github_json(f"https://api.github.com/repos/{login}/{quote(name, safe='')}", allow_missing=True, token=token)
    github_url = ""
    visibility = ""
    if (
        repo and (token or repo["visibility"] == "public")
        and repo["owner"]["login"].casefold() == login.casefold()
        and repo["name"].casefold() == name.casefold()
    ):
        github_url = repo["html_url"]
        visibility = repo["visibility"]
    if local_path or github_url:
        return with_branches(Match(name, local_path, github_url, visibility=visibility), token)


def delete_local_folder(parent, path):
    parent = Path(parent).expanduser().resolve(strict=True)
    original = Path(path)
    target = parent / original.name
    if original.parent.resolve(strict=True) != parent:
        raise ValueError("Папка находится вне каталога сравнения.")
    try:
        info = target.lstat()
    except FileNotFoundError:
        return
    if (
        not stat.S_ISDIR(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or target.resolve(strict=True).parent != parent
    ):
        raise ValueError("Выбранный путь не является обычной локальной папкой.")

    def retry_readonly(operation, filename, error):
        if not isinstance(error, PermissionError):
            raise error
        info = os.lstat(filename)
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise error
        os.chmod(filename, info.st_mode | stat.S_IWRITE)
        operation(filename)

    shutil.rmtree(target, onexc=retry_readonly)


def compare(folder, login, token=""):
    if not folder:
        raise ValueError("Укажите локальную папку.")
    root = Path(folder).expanduser().absolute()
    try:
        with os.scandir(root) as entries:
            folders = [entry.name for entry in entries if entry.is_dir()]
    except OSError as error:
        raise ValueError(f"Не удалось прочитать папку «{root}».") from error

    repositories = github_repositories(login, token)
    by_name = {name.casefold(): row for name, row in repositories.items()}
    local_names = {name.casefold() for name in folders}
    rows = [
        replace(by_name.get(name.casefold(), Match(name)), name=name, local_path=str(root / name))
        for name in folders
    ]
    rows.extend(row for name, row in by_name.items() if name not in local_names)
    return sorted(rows, key=lambda row: (row.name.casefold(), row.name))


def with_branches(row, token=""):
    try:
        return replace(row, branches=compare_branches(row.local_path, row.github_url, token),
                       branch_error="", mismatched_origin="")
    except OriginMismatch as error:
        return replace(row, branches=(), branch_error=str(error), mismatched_origin=error.origin)
    except BranchError as error:
        return replace(row, branches=(), branch_error=str(error), mismatched_origin="")
