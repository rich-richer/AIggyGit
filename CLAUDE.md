# AIggyGit — 项目约定

## 项目简介

<!-- 待补充：这个项目是做什么的、技术栈、给谁用。
     补上之后 README.md 的「简介」一节也要同步。 -->

尚未填写。

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
