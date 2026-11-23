import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from branches import Branch, BranchError, compare_branches


@dataclass(frozen=True)
class Match:
    name: str
    local_path: str = ""
    github_url: str = ""
    branches: tuple[Branch, ...] = ()
    branch_error: str = ""

    @property
    def status(self):
        if self.local_path and self.github_url:
            return "both"
        return "local" if self.local_path else "github"


def public_repositories(login):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", login, re.ASCII | re.IGNORECASE) or len(login) > 39:
        raise ValueError("Введите логин GitHub, например octocat.")

    url = f"https://api.github.com/users/{login}/repos?type=owner&sort=full_name&per_page=100"
    repositories = {}
    while url:
        request = Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "GitHubFolderComparison",
        })
        try:
            with urlopen(request, timeout=15) as response:
                for repo in json.load(response):
                    repositories[repo["name"]] = repo["html_url"]
                link = response.headers.get("Link", "")
        except HTTPError as error:
            if error.code == 404:
                raise ValueError(f"Аккаунт GitHub «{login}» не найден.") from error
            if error.code == 429 or (
                error.code == 403 and error.headers.get("X-RateLimit-Remaining") == "0"
            ):
                raise ValueError("Достигнут лимит запросов GitHub. Попробуйте позже.") from error
            raise ValueError(f"GitHub вернул ошибку HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise ValueError("Не удалось загрузить репозитории. Проверьте подключение к GitHub.") from error
        next_page = re.search(r'<(https://api\.github\.com/[^>]+)>;\s*rel="next"', link)
        url = next_page.group(1) if next_page else None
    return repositories


def compare(folder, login):
    if not folder:
        raise ValueError("Укажите локальную папку.")
    root = Path(folder).expanduser().absolute()
    try:
        with os.scandir(root) as entries:
            folders = [entry.name for entry in entries if entry.is_dir()]
    except OSError as error:
        raise ValueError(f"Не удалось прочитать папку «{root}».") from error

    repositories = public_repositories(login)
    by_name = {name.casefold(): url for name, url in repositories.items()}
    local_names = {name.casefold() for name in folders}
    rows = [Match(name, str(root / name), by_name.get(name.casefold(), "")) for name in folders]
    rows.extend(
        Match(name, github_url=url)
        for name, url in repositories.items()
        if name.casefold() not in local_names
    )
    return sorted(rows, key=lambda row: (row.name.casefold(), row.name))


def with_branches(row):
    try:
        return replace(row, branches=compare_branches(row.local_path, row.github_url))
    except BranchError as error:
        return replace(row, branch_error=str(error))
