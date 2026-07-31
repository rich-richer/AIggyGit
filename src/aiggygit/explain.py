"""把仓库状态翻译成大白话。

这里不调 AI —— 状态解释是确定性的，用规则写又快又准，还能离线用。
"""

from __future__ import annotations

from .git import Status


def _file_list(paths: list[str], limit: int = 5) -> str:
    shown = "、".join(paths[:limit])
    if len(paths) > limit:
        shown += f" 等 {len(paths)} 个"
    return shown


def describe(status: Status) -> str:
    """生成一段面向新手的状态说明。"""
    lines: list[str] = [f"你在分支 {status.branch} 上。"]

    if status.conflicted:
        lines.append(
            f"\n⚠️  有 {len(status.conflicted)} 个文件处于冲突状态："
            f"{_file_list(status.conflicted)}\n"
            "   需要你手动编辑这些文件、决定保留哪部分内容，"
            "改完后用 git add 把它们标记为已解决。"
        )

    if status.clean:
        lines.append("工作区是干净的 —— 没有任何未提交的改动。")
    else:
        if status.staged:
            lines.append(
                f"\n已暂存 {len(status.staged)} 个文件：{_file_list(status.staged)}\n"
                "   这些改动已经准备好了，下一次 commit 会把它们记录进去。"
            )
        if status.modified:
            lines.append(
                f"\n已修改但未暂存 {len(status.modified)} 个文件：{_file_list(status.modified)}\n"
                "   git 看到了这些改动，但还没把它们纳入下一次提交。"
            )
        if status.untracked:
            lines.append(
                f"\n未跟踪 {len(status.untracked)} 个文件：{_file_list(status.untracked)}\n"
                "   git 完全不认识这些文件。它们不会被提交，也不受版本控制保护。"
            )

    if status.upstream:
        if status.ahead and status.behind:
            lines.append(
                f"\n和远端 {status.upstream} 已经分叉了："
                f"你多出 {status.ahead} 条提交，远端多出 {status.behind} 条。\n"
                "   需要先合并或变基，才能推上去。"
            )
        elif status.ahead:
            lines.append(
                f"\n你比远端 {status.upstream} 多 {status.ahead} 条提交，"
                "还没推上去。"
            )
        elif status.behind:
            lines.append(
                f"\n远端 {status.upstream} 比你多 {status.behind} 条提交，"
                "你落后了，需要先拉取。"
            )
        else:
            lines.append(f"\n和远端 {status.upstream} 完全同步。")
    else:
        lines.append("\n这个分支还没有关联远端分支，推送时需要指定推到哪里。")

    if status.recent_commits:
        lines.append("\n最近的提交：")
        lines.extend(f"   {commit}" for commit in status.recent_commits)

    return "\n".join(lines)


def as_context(status: Status) -> str:
    """给模型看的紧凑状态摘要。写给机器，不用照顾可读性。"""
    parts = [f"当前分支: {status.branch}"]
    if status.upstream:
        parts.append(f"上游: {status.upstream} (领先 {status.ahead}, 落后 {status.behind})")
    else:
        parts.append("上游: 无")
    parts.append(f"已暂存: {status.staged or '无'}")
    parts.append(f"已修改未暂存: {status.modified or '无'}")
    parts.append(f"未跟踪: {status.untracked or '无'}")
    if status.conflicted:
        parts.append(f"冲突中: {status.conflicted}")
    if status.recent_commits:
        parts.append("最近提交:\n" + "\n".join(status.recent_commits))
    return "\n".join(parts)
