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


def cmd_explain(command: str) -> int:
    """解释一条命令。**永远不执行任何东西。**"""
    command = command.strip()
    if not command:
        _err('要解释什么？用法：aig explain "git reset --hard HEAD~1"')
        return 1

    segments = safety.analyze(command)
    chained = len(segments) > 1
    print(f"\n  {_paint(command, 'bold')}\n")

    # 分级是本地规则判断，没网也能用 —— 新手最急需的正是这部分
    if chained:
        print(f"  这条命令由 {len(segments)} 段串联而成，会依次执行：\n")
    for i, seg in enumerate(segments, 1):
        if chained:
            # 单条命令时上面已经打印过了，不重复
            print(f"  [{i}] {seg.command}")
        if seg.verdict:
            color, label = _RISK_LABEL[seg.verdict.risk]
            print(f"      {_paint(label, color)} —— {seg.verdict.reason}")
        else:
            print(f"      {_paint('无法分级', 'yellow')} —— {seg.problem}")

    unassessed = [seg for seg in segments if seg.verdict is None]
    if unassessed:
        # 有评估不了的部分时绝不能给「安全」这种结论 —— 用户会当成整条命令的判断。
        # 宁可说不知道，也不能给虚假的安心。
        print(
            _paint(
                f"\n  ⚠ 整体风险无法判定：有 {len(unassessed)} 段不是 git 命令，"
                "本工具评估不了，请自行确认它们做什么。",
                "yellow",
            )
        )
    elif chained:
        color, label = _RISK_LABEL[safety.worst_risk(segments)]
        print(f"\n  整体风险：{_paint(label, color)}（取最高的一段）")

    # AI 解释是加分项，拿不到也不影响上面的分级
    try:
        exp = translate.explain_command(command)
    except translate.TranslationError as exc:
        print(_paint(f"\n  详细解释需要 API：{exc}", "dim"))
        return 0

    print(f"\n  {_paint('这条命令做什么', 'bold')}")
    print(f"  {exp.summary}\n")
    print(f"  {exp.detail}")
    if exp.risk_note:
        print(f"\n  {_paint('会不会丢东西', 'bold')}")
        print(f"  {exp.risk_note}")
    if exp.safer_alternative:
        print(f"\n  {_paint('更安全的做法', 'bold')}")
        print(f"  {exp.safer_alternative}")
    print(_paint("\n  （explain 只解释，不执行任何命令）", "dim"))
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
        epilog=(
            "示例：\n"
            "  aig status\n"
            '  aig "把这些改动提交了，说明是修复登录问题"\n'
            '  aig explain "git reset --hard HEAD~1"\n'
            '  aig --dry-run "撤销上一次提交"'
        ),
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

    if args.request[0] == "explain":
        return cmd_explain(" ".join(args.request[1:]))

    try:
        return cmd_ask(
            " ".join(args.request), dry_run=args.dry_run, assume_yes=args.yes
        )
    except (KeyboardInterrupt, EOFError):
        print("\n已取消。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
