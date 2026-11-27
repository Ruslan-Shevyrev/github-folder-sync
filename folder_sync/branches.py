import os
import re
import subprocess
from base64 import b64encode
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


class OriginMismatch(BranchError):
    message = "Origin ведёт на другой репозиторий."

    def __init__(self, origin):
        super().__init__(self.message)
        self.origin = origin


def git(path, *args, allowed=(0,), input_text=None, timeout=20, extra_env=None):
    command = ["git"]
    if path:
        command.extend(("-C", path))
    command.extend(args)
    try:
        result = subprocess.run(
            command, input=input_text.encode("ascii") if input_text is not None else None,
            capture_output=True, timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", **(extra_env or {})},
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


def github_git(path, *args, token="", **options):
    if not token:
        return git(path, *args, **options)
    if not any(re.fullmatch(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", arg)
               for arg in args):
        raise BranchError("Токен можно передать только GitHub по HTTPS.")

    basic = b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    count = int(os.environ.get("GIT_CONFIG_COUNT") or "0")
    config = {}
    for index, (key, value) in enumerate((
        ("http.https://github.com/.extraHeader", ""),
        ("http.https://github.com/.extraHeader", f"Authorization: Basic {basic}"),
        ("http.https://github.com/.followRedirects", "false"),
    ), count):
        config[f"GIT_CONFIG_KEY_{index}"] = key
        config[f"GIT_CONFIG_VALUE_{index}"] = value
    config["GIT_CONFIG_COUNT"] = str(count + 3)
    return git(path, *args, extra_env=config, **options)


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


def compare_branches(path, url, token=""):
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
                raise OriginMismatch(origin)
        local = branch_refs(git(path, "for-each-ref", "--format=%(objectname)%09%(refname)", "refs/heads").stdout)

    remote = {}
    if url:
        remote = branch_refs(github_git(None, "ls-remote", "--heads", url, token=token).stdout)

    changed = {remote[name] for name in local.keys() & remote.keys() if local[name] != remote[name]}
    missing = {
        commit for commit in changed
        if git(path, "cat-file", "-e", f"{commit}^{{commit}}", allowed=(0, 1, 128)).returncode
    }
    if missing:
        github_git(path, "fetch", "--no-tags", "--no-prune", "--no-recurse-submodules", "--no-auto-maintenance",
            "--no-write-fetch-head", "--refmap=", url, "--stdin",
            input_text="\n".join(sorted(missing)) + "\n", token=token)

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
