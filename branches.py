import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Branch:
    name: str
    status: str
    local_commit: str = ""
    remote_commit: str = ""


class BranchError(Exception):
    pass


def git(path, *args, allowed=(0,), input_text=None, timeout=20):
    command = ["git"]
    if path:
        command.extend(("-C", path))
    command.extend(args)
    try:
        result = subprocess.run(
            command, input=input_text.encode("ascii") if input_text is not None else None,
            capture_output=True, timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as error:
        raise BranchError("Для проверки веток установите Git.") from error
    except subprocess.TimeoutExpired as error:
        raise BranchError("Истекло время ожидания ответа Git.") from error
    except OSError as error:
        raise BranchError("Не удалось запустить Git.") from error
    if result.returncode not in allowed:
        raise BranchError("Git не смог прочитать ветки или их историю.")
    result.stdout = result.stdout.decode("utf-8", errors="replace")
    return result


def branch_refs(output):
    return {
        ref.removeprefix("refs/heads/"): commit
        for commit, ref in (line.split("\t", 1) for line in output.splitlines())
        if ref.startswith("refs/heads/")
    }


def github_repository(url):
    match = re.fullmatch(
        r"(?:https?://github\.com/|ssh://git@github\.com(?::22)?/|git@github\.com:)"
        r"([^/]+/[^/]+?)(?:\.git)?/?", url, re.IGNORECASE
    )
    return match[1].casefold() if match else None


def relationship(path, local, remote, shallow):
    if git(path, "merge-base", "--is-ancestor", local, remote, allowed=(0, 1)).returncode == 0:
        return "behind"
    if git(path, "merge-base", "--is-ancestor", remote, local, allowed=(0, 1)).returncode == 0:
        return "ahead"
    return "unknown" if shallow else "diverged"


def compare_branches(path, url):
    local = {}
    if path:
        if not (Path(path) / ".git").exists():
            if url:
                raise BranchError("В локальной папке нет Git-репозитория.")
            return ()
        if url:
            origin = git(path, "config", "--get", "remote.origin.url", allowed=(0, 1)).stdout.strip()
            if not origin:
                raise BranchError("У локального репозитория отсутствует origin.")
            if github_repository(origin) != github_repository(url):
                raise BranchError("Origin ведёт на другой репозиторий.")
        local = branch_refs(git(path, "for-each-ref", "--format=%(objectname)%09%(refname)", "refs/heads").stdout)

    remote = {}
    if url:
        remote = branch_refs(git(None, "ls-remote", "--heads", url).stdout)

    changed = {remote[name] for name in local.keys() & remote.keys() if local[name] != remote[name]}
    missing = {
        commit for commit in changed
        if git(path, "cat-file", "-e", f"{commit}^{{commit}}", allowed=(0, 1, 128)).returncode
    }
    if missing:
        git(path, "fetch", "--no-tags", "--no-prune", "--no-recurse-submodules", "--no-auto-maintenance",
            "--no-write-fetch-head", "--refmap=", url, "--stdin",
            input_text="\n".join(sorted(missing)) + "\n")

    shallow = bool(changed) and git(path, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    branches = []
    for name in sorted(local.keys() | remote.keys(), key=lambda name: (name.casefold(), name)):
        if name not in local:
            status = "github"
        elif name not in remote:
            status = "local"
        elif local[name] == remote[name]:
            status = "equal"
        else:
            status = relationship(path, local[name], remote[name], shallow)
        branches.append(Branch(name, status, local.get(name, ""), remote.get(name, "")))
    return tuple(branches)
