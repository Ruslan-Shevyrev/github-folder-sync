import re
from pathlib import Path

from branches import BranchError, branch_refs, git, github_git, github_repository


def corrected_origin(url, current):
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9-]+/[A-Za-z0-9_.-]+)", url)
    if not match:
        raise BranchError("Не удалось определить адрес репозитория GitHub.")
    repository = match[1]
    if current.lower().startswith(("git@", "ssh://")):
        return f"git@github.com:{repository}.git"
    return f"https://github.com/{repository}.git"


def change_origin(path, current, target):
    root = git(str(path), "rev-parse", "--show-toplevel").stdout.strip()
    if Path(root).resolve() != path.resolve():
        raise BranchError("Локальный репозиторий изменился. Повторите сравнение.")
    actual = git(str(path), "config", "--get", "remote.origin.url", allowed=(0, 1)).stdout.strip()
    if actual != current:
        raise BranchError("Origin уже изменился. Повторите сравнение.")
    git(str(path), "remote", "set-url", "origin", target)


def sync_from_github(path, url, branch, token=""):
    if not github_repository(url):
        raise BranchError("Не удалось определить репозиторий GitHub.")

    if not path.is_dir():
        raise BranchError("Локальная папка больше недоступна.")

    origin = git(str(path), "config", "--get", "remote.origin.url", allowed=(0, 1)).stdout.strip()
    if github_repository(origin) != github_repository(url):
        raise BranchError("Origin изменился. Повторите сравнение.")

    local = str(path)
    ref = f"refs/heads/{branch.name}"
    current = branch_refs(git(local, "for-each-ref", "--format=%(objectname)%09%(refname)", ref).stdout)
    if current.get(branch.name, "") != branch.local_commit:
        raise BranchError("Локальная ветка изменилась. Повторите сравнение.")

    if branch.status == "github":
        remote = branch_refs(github_git(local, "ls-remote", "--heads", url, ref, token=token).stdout)
        commit = remote.get(branch.name)
        if not commit:
            raise BranchError("Ветка на GitHub больше недоступна. Повторите сравнение.")
        github_git(local, "fetch", "--no-tags", "--no-prune", "--no-recurse-submodules",
            "--no-write-fetch-head", "--refmap=", url, commit, timeout=300, token=token)
        git(local, "branch", "--", branch.name, commit)
        return

    if branch.status != "behind":
        raise BranchError("Это состояние ветки не поддерживает обновление.")
    head = git(local, "symbolic-ref", "--quiet", "HEAD", allowed=(0, 1)).stdout.strip()
    if head != ref:
        raise BranchError(f"Переключитесь на ветку «{branch.name}» в локальном репозитории и повторите обновление.")
    if git(local, "status", "--porcelain", "--untracked-files=all").stdout.strip():
        raise BranchError("В рабочей папке есть изменения. Сохраните их перед обновлением.")
    github_git(local, "-c", "pull.squash=false", "pull", "--ff-only", "--no-rebase", "--no-autostash",
        "--no-recurse-submodules", url, ref, timeout=300, token=token)


def clone_from_github(destination, url, branch, token=""):
    if not github_repository(url):
        raise BranchError("Не удалось определить репозиторий GitHub.")
    try:
        destination.mkdir()
    except FileExistsError as error:
        raise BranchError("Папка уже существует. Повторите сравнение.") from error

    options = ("--branch", branch.name) if branch else ()
    try:
        github_git(str(destination.parent), "clone", *options, "--", url, str(destination), timeout=600, token=token)
    except BranchError:
        try:
            destination.rmdir()
        except OSError:
            pass  # Preserve a nonempty directory if Git left files there.
        raise
