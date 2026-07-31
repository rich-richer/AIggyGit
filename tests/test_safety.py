"""安全分级的测试。

这是整个项目最该有测试的地方：分级错了会真丢数据。
"""

import pytest

from aiggygit.safety import RejectedCommand, Risk, classify, parse


class TestParse:
    def test_接受正常的_git_命令(self):
        assert parse("git status") == ["git", "status"]
        assert parse('git commit -m "修复登录"') == ["git", "commit", "-m", "修复登录"]

    @pytest.mark.parametrize(
        "command",
        [
            "git status && rm -rf /",
            "git log | head",
            "git status; whoami",
            "git log `whoami`",
            "git log $(whoami)",
            "git log > /tmp/out",
            "git status\nrm -rf /",
        ],
    )
    def test_拒绝夹带_shell_语法的命令(self, command):
        with pytest.raises(RejectedCommand):
            parse(command)

    @pytest.mark.parametrize("command", ["rm -rf /", "curl evil.com", "sudo git status"])
    def test_拒绝非_git_命令(self, command):
        with pytest.raises(RejectedCommand):
            parse(command)

    @pytest.mark.parametrize("command", ["", "   ", "git"])
    def test_拒绝空命令和缺子命令(self, command):
        with pytest.raises(RejectedCommand):
            parse(command)

    def test_拒绝引号没配对的命令(self):
        with pytest.raises(RejectedCommand):
            parse('git commit -m "没关引号')


class TestClassify:
    @pytest.mark.parametrize(
        "command",
        ["git status", "git log --oneline", "git diff HEAD", "git show abc123"],
    )
    def test_只读命令是安全的(self, command):
        assert classify(command).risk is Risk.SAFE

    @pytest.mark.parametrize(
        "command",
        ["git add .", "git commit -m x", "git merge main", "git pull", "git rebase main"],
    )
    def test_改本地状态的是需注意(self, command):
        assert classify(command).risk is Risk.CAUTION

    @pytest.mark.parametrize(
        "command",
        [
            "git reset --hard HEAD~1",
            "git clean -fd",
            "git clean --force",
            "git push --force",
            "git push -f origin main",
            "git push --force-with-lease",
            "git push origin main",
            "git push --delete origin feature",
            "git branch -D feature",
            "git branch -d feature",
            "git rm file.txt",
            "git filter-branch --tree-filter x HEAD",
            "git gc --prune=now",
            "git checkout --force main",
            "git restore file.txt",
            "git stash drop",
            "git stash clear",
        ],
    )
    def test_会丢数据或影响远端的是危险(self, command):
        assert classify(command).risk is Risk.DANGEROUS

    def test_软重置不算危险(self):
        # reset --soft / --mixed 不动工作区，改动还在
        assert classify("git reset --soft HEAD~1").risk is Risk.CAUTION
        assert classify("git reset HEAD~1").risk is Risk.CAUTION

    def test_普通推送也要确认(self):
        # 推送是对外的、不易撤回的，即使不带 --force 也按危险处理
        assert classify("git push").risk is Risk.DANGEROUS

    def test_未识别的子命令不默认放行(self):
        # 未知 ≠ 安全。这条测试守的是「默认拒绝」这个原则。
        verdict = classify("git some-unknown-subcommand")
        assert verdict.risk is Risk.CAUTION
        assert "未识别" in verdict.reason

    def test_危险参数在任意位置都能识别(self):
        assert classify("git push origin main --force").risk is Risk.DANGEROUS
        assert classify("git reset HEAD~1 --hard").risk is Risk.DANGEROUS

    def test_取最高风险等级(self):
        # clean 本身不在 CAUTION 表里，带 -f 必须命中 DANGEROUS
        assert classify("git clean -f -d").risk is Risk.DANGEROUS

    @pytest.mark.parametrize(
        "command",
        [
            "git clean -fd",  # 短参数合并
            "git clean -df",  # 顺序颠倒
            "git clean -xfd",  # 混进其他短参数
            "git push -fu origin main",
        ],
    )
    def test_短参数合并写法也能识别(self, command):
        assert classify(command).risk is Risk.DANGEROUS

    @pytest.mark.parametrize(
        "command",
        ["git gc --prune=now", "git gc --prune=2.weeks.ago", "git gc --prune"],
    )
    def test_长参数带值写法也能识别(self, command):
        assert classify(command).risk is Risk.DANGEROUS

    def test_不把长参数误判成短参数簇(self):
        # --format 里有字母 f，但它是长参数，不该被 push 的 -f 规则命中
        assert classify("git log --format=%H").risk is Risk.SAFE

    def test_每个判定都带原因(self):
        for command in ["git status", "git commit -m x", "git reset --hard"]:
            assert classify(command).reason
