"""命令行入口。"""

from __future__ import annotations

import argparse
import sys

from . import __version__, explain, git, safety, translate
from .safety import RejectedCommand, Risk

_COLORS = {
    "dim": "\033[2m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "green": "\033[32m",
    "reset": "\033[0m",
}

_RISK_LABEL = {
    Risk.SAFE: ("green", "安全"),
    Risk.CAUTION: ("yellow", "需注意"),
    Risk.DANGEROUS: ("red", "危险"),
}


def _paint(text: str, color: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{_COLORS[color]}{text}{_COLORS['reset']}"


def _err(message: str) -> None:
    print(_paint(f"错误：{message}", "red"), file=sys.stderr)


def cmd_status() -> int:
    try:
        status = git.read_status()
    except git.NotARepo:
        _err("当前目录不在 git 仓库里。用 `git init` 新建，或 cd 到仓库目录。")
        return 1
    print(explain.describe(status))
    return 0


def _confirm(verdict: safety.Verdict, assume_yes: bool) -> bool:
    """按风险等级决定要不要问、怎么问。

    注意 --yes **不能**跳过 DANGEROUS —— 一个能被开关关掉的安全提示等于没有。
    """
    if verdict.risk is Risk.SAFE:
        return True

    if verdict.risk is Risk.CAUTION:
        if assume_yes:
            return True
        answer = input("执行吗？[y/N] ").strip().lower()
        return answer in ("y", "yes")

    # DANGEROUS：必须完整输入 yes，光敲 y 不算
    print(_paint("\n这个操作可能造成不可恢复的损失。", "red"))
    answer = input('确认执行请完整输入 "yes"：').strip()
    return answer == "yes"


def cmd_ask(request: str, *, dry_run: bool, assume_yes: bool) -> int:
    try:
        status = git.read_status()
    except git.NotARepo:
        _err("当前目录不在 git 仓库里。")
        return 1

    # flush=True：管道场景下 stdout 是块缓冲的，不刷新会让这行排到错误信息后面
    print(_paint("正在理解你的需求…", "dim"), flush=True)
    try:
        suggestion = translate.translate(request, explain.as_context(status))
    except translate.TranslationError as exc:
        _err(str(exc))
        return 1

    try:
        verdict = safety.classify(suggestion.command)
        argv = safety.parse(suggestion.command)
    except RejectedCommand as exc:
        _err(f"模型给出的命令不能执行：{exc}")
        print(_paint(f"  它建议的是：{suggestion.command}", "dim"), file=sys.stderr)
        return 1

    color, label = _RISK_LABEL[verdict.risk]
    print(f"\n  {_paint(suggestion.command, 'bold')}")
    print(f"\n  {suggestion.explanation}")
    print(f"\n  风险：{_paint(label, color)} —— {verdict.reason}")
    if suggestion.note:
        print(f"  提醒：{suggestion.note}")
    if suggestion.confidence != "high":
        print(_paint(f"  把握程度：{suggestion.confidence}，建议自己再核对一遍", "yellow"))
    print()

    if dry_run:
        print(_paint("(--dry-run，没有执行)", "dim"))
        return 0

    if not _confirm(verdict, assume_yes):
        print("已取消。")
        return 1

    result = git.run(argv)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if not result.ok:
        _err(f"git 退出码 {result.returncode}")
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aig",
        description="AI 辅助 Git 操作的命令行工具",
        epilog='示例：\n  aig status\n  aig "把这些改动提交了，说明是修复登录问题"\n  aig --dry-run "撤销上一次提交"',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"aiggygit {__version__}")
    parser.add_argument(
        "request",
        nargs="*",
        help='想做的事（自然语言），或者子命令 status',
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true", help="只显示命令，不执行"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="跳过「需注意」级别的确认（危险操作仍然会问）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.request:
        parser.print_help()
        return 0

    if args.request == ["status"]:
        return cmd_status()

    try:
        return cmd_ask(
            " ".join(args.request), dry_run=args.dry_run, assume_yes=args.yes
        )
    except (KeyboardInterrupt, EOFError):
        print("\n已取消。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
