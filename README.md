# AIggyGit

> 用大白话指挥 Git —— 一个面向新手的 AI 辅助命令行工具。

## 简介

Git 的难点从来不是敲不出命令，而是**不知道该敲哪条**，以及**敲错了会怎样**。
新手最常见的两种卡壳：想做的事说得出来但翻译不成命令；以及从网上复制一条
`git reset --hard` 粘进终端，回车之后才发现改动全没了。

AIggyGit 针对的就是这两点：你用中文说想干什么，它翻译成一条 git 命令，
**先解释这条命令会做什么、有什么风险，等你确认了再执行**。

它不是图形客户端 —— 你看到的始终是真实的 git 命令，用久了自然就学会了。

## 功能特性

- **自然语言翻译** —— 「把这些改动提交了」→ 具体的 `git commit` 命令，附带中文解释
- **执行前风险分级** —— 每条命令标注安全 / 需注意 / 危险，危险操作必须完整输入 `yes` 才执行
- **大白话状态** —— `aig status` 把仓库状态讲成人话，而不是一堆术语
- **注入防护** —— 只执行单条 git 命令，含 `&&` `|` `;` `` ` `` 等 shell 语法的一律拒绝

## 环境要求

| 依赖 | 版本 |
| --- | --- |
| Python | ≥ 3.10 |
| git | 任意近期版本 |
| Anthropic API Key | 仅自然语言功能需要；`aig status` 离线可用 |

## 安装

```bash
git clone https://github.com/rich-richer/AIggyGit.git
cd AIggyGit
python3 -m venv .venv && .venv/bin/pip install -e .
```

配置 API Key（二选一）：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

或者复制 `.env.example` 成 `.env` 填进去 —— `.env` 已在 `.gitignore` 中，不会进仓库。

## 快速开始

```bash
aig status
```

输出：

```
你在分支 main 上。

已修改但未暂存 2 个文件：src/api.py、README.md
   git 看到了这些改动，但还没把它们纳入下一次提交。

你比远端 origin/main 多 1 条提交，还没推上去。

最近的提交：
   850afc6 docs: 补充项目简介
```

## 使用说明

用自然语言描述你想做的事：

```bash
aig "把这些改动提交了，说明是修复登录问题"
```

它会先展示方案，等你确认：

```
  git commit -am "fix: 修复登录问题"

  把当前所有已跟踪文件的改动打包成一条提交记录。提交后这些改动就被
  永久保存在本地历史里了，之后随时可以回到这个状态。

  风险：需注意 —— 会创建一条提交

执行吗？[y/N]
```

危险操作的门槛更高 —— 光敲 `y` 不算：

```bash
aig "把所有改动都扔掉，回到上次提交的状态"
```

```
  git reset --hard HEAD

  风险：危险 —— 会丢弃工作区里所有未提交的改动，且无法通过 git 找回
  提醒：这会永久丢失你尚未提交的全部修改。建议先用 git stash 存一份。

这个操作可能造成不可恢复的损失。
确认执行请完整输入 "yes"：
```

### 命令与参数

| 用法 | 说明 |
| --- | --- |
| `aig status` | 大白话展示仓库状态，不调用 AI，离线可用 |
| `aig "<想做的事>"` | 翻译成 git 命令，确认后执行 |
| `-n` / `--dry-run` | 只显示命令和解释，不执行 |
| `-y` / `--yes` | 跳过「需注意」级别的确认。**危险操作仍然会问** |
| `--version` | 显示版本 |

## 配置

| 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | 无，自然语言功能必需 |
| `AIGGYGIT_MODEL` | 覆盖使用的模型 | `claude-opus-5` |

> 密钥一律走环境变量或 `.env`，绝不要写进代码或提交进仓库。

## 目录结构

```
AIggyGit/
├── src/aiggygit/
│   ├── cli.py         # 命令行入口、确认流程
│   ├── safety.py      # 命令风险分级（纯规则，不经过 AI）
│   ├── translate.py   # 自然语言 → git 命令（唯一调用 AI 的模块）
│   ├── git.py         # git 执行与状态读取
│   └── explain.py     # 状态的大白话描述
└── tests/
    └── test_safety.py # 安全分级测试
```

### 一个设计决定：安全判断不经过 AI

`safety.py` 是纯规则代码。风险分级如果交给模型，就意味着模型幻觉一次
就可能放行一条 `git reset --hard`。规则代码可以写测试、可以审计、结果确定，
这是唯一能对数据安全负责的做法。AI 只负责「翻译」，「要不要执行」由规则和你决定。

同样地，命令通过参数数组执行，不经过 shell，并且拒绝一切含 shell 元字符的命令 ——
模型的输出被当作不可信输入对待。

## 开发

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

## 路线图

- [ ] `aig undo` —— 引导式撤销，自动选最安全的回退方式
- [ ] `aig explain <命令>` —— 反向翻译：解释一条从网上抄来的 git 命令
- [ ] 冲突解决的分步引导
- [ ] 常见操作的本地规则匹配，跳过 API 调用以降低延迟和成本

## License

[MIT](LICENSE) © 2026 Zheyuan Chen
