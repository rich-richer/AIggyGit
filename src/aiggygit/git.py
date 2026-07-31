"""git 命令执行与仓库状态读取。

所有命令都用参数数组执行（不经过 shell），配合 safety.parse 的元字符检查，
从根子上避免命令注入。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field


class NotARepo(Exception):
    """当前目录不在 git 仓库里。"""


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class Status:
    """仓库当前状态的结构化快照。"""

    branch: str
    staged: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    conflicted: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    upstream: str | None = None
    recent_commits: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.staged or self.modified or self.untracked or self.conflicted)


def run(args: list[str], *, timeout: int = 30) -> Result:
    """执行一条 git 命令。args 必须是参数数组，第一项是 'git'。"""
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return Result(completed.returncode, completed.stdout, completed.stderr)


def _capture(args: list[str]) -> str:
    """跑一条只读命令并返回 stdout，失败时返回空串。"""
    result = run(args)
    return result.stdout.strip() if result.ok else ""


def in_repo() -> bool:
    return run(["git", "rev-parse", "--git-dir"]).ok


def read_status() -> Status:
    """读取仓库状态。不在仓库里时抛 NotARepo。"""
    if not in_repo():
        raise NotARepo("当前目录不在 git 仓库里")

    branch = _capture(["git", "branch", "--show-current"]) or "(游离 HEAD)"
    status = Status(branch=branch)

    # --porcelain=v1 的格式是稳定的，专门给脚本用
    for line in _capture(["git", "status", "--porcelain=v1"]).splitlines():
        if len(line) < 3:
            continue
        index_state, worktree_state, path = line[0], line[1], line[3:]
        if index_state == "?" and worktree_state == "?":
            status.untracked.append(path)
        elif "U" in (index_state, worktree_state) or index_state == worktree_state == "A":
            status.conflicted.append(path)
        else:
            if index_state != " ":
                status.staged.append(path)
            if worktree_state != " ":
                status.modified.append(path)

    upstream = _capture(["git", "rev-parse", "--abbrev-ref", "@{upstream}"])
    if upstream:
        status.upstream = upstream
        counts = _capture(["git", "rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
        parts = counts.split()
        if len(parts) == 2:
            status.behind, status.ahead = int(parts[0]), int(parts[1])

    status.recent_commits = _capture(
        ["git", "log", "--oneline", "-5", "--no-decorate"]
    ).splitlines()

    return status
