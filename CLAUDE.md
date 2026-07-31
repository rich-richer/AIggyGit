# AIggyGit — 项目约定

## 项目简介

AIggyGit 是一个 **AI 辅助 Git 操作的 CLI 工具**，面向不熟悉 git 的新手。
用户用中文说想做什么，工具翻译成一条 git 命令，解释清楚风险，确认后执行。

技术栈：Python ≥ 3.10，依赖只有 `anthropic`。命令名 `aig`。

## 架构约定

```
src/aiggygit/
├── cli.py         命令行入口、确认流程
├── safety.py      风险分级（纯规则，禁止引入 AI）
├── translate.py   自然语言 → git 命令（唯一调用 AI 的模块）
├── git.py         git 执行与状态读取
└── explain.py     状态的大白话描述
```

**两条不能破的规则：**

1. **安全判断绝不交给 AI。** `safety.py` 必须保持纯规则、可测试。改动这个文件
   必须同步加测试。模型幻觉一次就可能放行 `git reset --hard`。
2. **模型输出是不可信输入。** 命令一律用参数数组执行（不用 `shell=True`），
   含 shell 元字符的命令直接拒绝。

新增危险命令规则时，记得覆盖三种写法：`--flag`、`--flag=value`、短参数簇 `-fd`。

## 语言

- 与用户交流、README、注释、提交信息**一律用中文**
- 代码标识符、目录名用英文

## 提交信息

Conventional Commits 前缀 + 中文描述：

```
docs: 扩充 README 结构骨架
chore: 忽略 .env 及其变体，放行 .env.example
```

常用前缀：`feat` `fix` `docs` `chore` `refactor` `test`

## 分支与推送

- 主分支 `main`，直接推 `origin/main`
- **未经明确要求不要自动提交或推送**

## 许可

MIT，版权人 `Zheyuan Chen`。新增源文件不需要加版权头。

## 安全红线

- `.env` 及其变体已在 `.gitignore` 中；**任何密钥、token 都不准进仓库**
- 需要配置项时用环境变量，并在 `.env.example` 里放不含真值的模板
- 本仓库是 **public**，提交前留意不要带入私密信息
