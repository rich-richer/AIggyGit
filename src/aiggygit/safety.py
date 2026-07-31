"""命令安全分级。

这一层是纯规则判断，**不经过 AI**。理由很简单：AI 会犯错，而 `git reset --hard`
犯一次错就够你难受一整天。危险与否必须是确定性的、可审计的、可以写测试的。
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum


class Risk(Enum):
    """风险等级，数值越大越危险。"""

    SAFE = 0  # 只读，不改变任何状态
    CAUTION = 1  # 改变本地状态，但基本都能找回来
    DANGEROUS = 2  # 可能丢数据，或影响到远端／别人


@dataclass(frozen=True)
class Verdict:
    risk: Risk
    reason: str


class RejectedCommand(Exception):
    """命令连执行的资格都没有 —— 不是 git，或者夹带了 shell 语法。"""


# 明确只读的子命令。不在这个集合里的一律不算 SAFE。
_READ_ONLY = frozenset(
    {
        "status", "log", "diff", "show", "blame", "reflog", "shortlog",
        "describe", "ls-files", "ls-remote", "ls-tree", "cat-file",
        "rev-parse", "rev-list", "name-rev", "whatchanged", "grep",
        "config", "help", "version", "check-ignore", "count-objects",
    }
)

# (子命令, 危险参数) → 原因。参数为 None 表示整个子命令都危险。
_DANGEROUS: dict[str, dict[str | None, str]] = {
    "reset": {"--hard": "会丢弃工作区里所有未提交的改动，且无法通过 git 找回"},
    "clean": {
        "-f": "会永久删除未跟踪的文件，这些文件从未进过 git，删了就真没了",
        "--force": "会永久删除未跟踪的文件，这些文件从未进过 git，删了就真没了",
    },
    "push": {
        "--force": "会覆盖远端历史，可能抹掉别人的提交",
        "-f": "会覆盖远端历史，可能抹掉别人的提交",
        "--force-with-lease": "会覆盖远端历史（比 --force 安全，但仍会改写）",
        "--delete": "会删除远端分支",
        "-d": "会删除远端分支",
        None: "会把改动推送到远端，其他人立刻可见，且不易撤回",
    },
    "branch": {
        "-D": "会强制删除分支，即使它还没有被合并",
        "--delete": "会删除分支",
        "-d": "会删除分支",
    },
    "rm": {None: "会从工作区删除文件"},
    "filter-branch": {None: "会重写整个仓库历史，属于核弹级操作"},
    "gc": {"--prune": "会清理无法访问的对象，清理后 reflog 里的东西也找不回来了"},
    "update-ref": {None: "会直接改写引用，绕过所有常规保护"},
    "checkout": {"--force": "会丢弃工作区改动", "-f": "会丢弃工作区改动"},
    "switch": {"--force": "会丢弃工作区改动", "-f": "会丢弃工作区改动"},
    "restore": {None: "会用其他版本覆盖当前文件，未提交的改动会丢失"},
    "stash": {"drop": "会删除一条 stash 记录", "clear": "会删除全部 stash 记录"},
}

# 这些会改变本地状态，但基本都能靠 reflog 或重新操作找回来。
_CAUTION_REASONS: dict[str, str] = {
    "commit": "会创建一条提交",
    "add": "会把改动放进暂存区",
    "merge": "会合并分支，可能产生冲突",
    "rebase": "会改写本地提交历史，可能产生冲突",
    "cherry-pick": "会把某条提交复制到当前分支",
    "revert": "会创建一条新提交来撤销旧提交",
    "pull": "会拉取远端改动并合并到本地",
    "fetch": "会拉取远端数据（不改动工作区）",
    "init": "会初始化一个新仓库",
    "clone": "会克隆一个仓库到本地",
    "tag": "会创建或改动标签",
    "apply": "会应用补丁到工作区",
    "mv": "会移动或重命名文件",
}

# shell 元字符。命令里出现任何一个就直接拒绝 —— 我们用 subprocess 传数组执行，
# 不经过 shell，所以这些字符不可能是「本意」，只可能是注入或者模型幻觉。
_SHELL_METACHARS = ("&", "|", ";", "`", "$(", ">", "<", "\n")


def parse(command: str) -> list[str]:
    """把命令字符串切成参数数组，顺便挡掉明显不该执行的东西。

    抛 RejectedCommand 表示这条命令根本不该走到执行环节。
    """
    if not command.strip():
        raise RejectedCommand("命令是空的")

    for char in _SHELL_METACHARS:
        if char in command:
            raise RejectedCommand(
                f"命令里含有 shell 元字符 {char!r}。本工具只执行单条 git 命令，"
                "不经过 shell，这类写法一律拒绝。"
            )

    try:
        parts = shlex.split(command)
    except ValueError as exc:  # 引号没配对之类
        raise RejectedCommand(f"命令无法解析：{exc}") from None

    if not parts:
        raise RejectedCommand("命令是空的")
    if parts[0] != "git":
        raise RejectedCommand(f"只允许执行 git 命令，但这条以 {parts[0]!r} 开头")
    if len(parts) < 2:
        raise RejectedCommand("缺少 git 子命令")

    return parts


def _matches(flag: str, args: list[str]) -> bool:
    """判断某个危险参数是否出现在参数列表里。

    必须处理三种写法，漏掉任何一种安全层都会被绕过：
      --prune       长参数，也可能写成 --prune=now
      -f            短参数，也可能合并成 -fd
      drop          既不是参数也不是标志，只能精确匹配（如 git stash drop）
    """
    if flag.startswith("--"):
        return any(arg == flag or arg.startswith(flag + "=") for arg in args)

    if flag.startswith("-"):
        letter = flag[1:]
        for arg in args:
            if arg == flag:
                return True
            # 短参数簇：-fd 等价于 -f -d。排除 -- 开头的长参数。
            if arg.startswith("-") and not arg.startswith("--") and letter in arg[1:]:
                return True
        return False

    return flag in args


def classify(command: str) -> Verdict:
    """判断一条 git 命令的风险等级。

    取所有匹配规则里最高的那一级 —— 宁可多问一句，不可少拦一次。
    """
    parts = parse(command)
    subcommand = parts[1]
    args = parts[2:]

    rules = _DANGEROUS.get(subcommand)
    if rules:
        # 先看有没有命中具体的危险参数
        for flag, reason in rules.items():
            if flag is not None and _matches(flag, args):
                return Verdict(Risk.DANGEROUS, reason)
        # 再看这个子命令是不是整体就危险
        if None in rules:
            return Verdict(Risk.DANGEROUS, rules[None])

    if subcommand in _CAUTION_REASONS:
        return Verdict(Risk.CAUTION, _CAUTION_REASONS[subcommand])

    if subcommand in _READ_ONLY:
        return Verdict(Risk.SAFE, "只读操作，不会改变任何东西")

    # 认不出来的子命令按 CAUTION 处理，让用户自己看一眼再决定。
    # 默认放行是绝对不行的 —— 未知不等于安全。
    return Verdict(Risk.CAUTION, f"未识别的子命令 {subcommand!r}，请自行确认它做什么")
