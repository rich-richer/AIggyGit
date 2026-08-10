"""自然语言 → git 命令。这是唯一会调用 AI 的模块。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "claude-opus-5"

# 结构化输出的 schema。用它而不是让模型自由发挥再去解析文本 ——
# 后者迟早会碰上模型多写一句「好的，这是你要的命令：」然后解析崩掉。
_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "单条 git 命令，必须以 git 开头。不要用 && 或 | 串联多条命令。",
        },
        "explanation": {
            "type": "string",
            "description": "用中文向 git 新手解释这条命令会做什么，两三句话，不要术语堆砌。",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "对这条命令确实符合用户意图的把握程度。",
        },
        "note": {
            "type": "string",
            "description": "需要额外提醒的事项；没有就填空字符串。",
        },
    },
    "required": ["command", "explanation", "confidence", "note"],
    "additionalProperties": False,
}

_SYSTEM = """你是一个 git 助手，服务对象是**不熟悉 git 的新手**。

用户会用自然语言描述他想做什么，你把它翻译成一条 git 命令。

规则：
- 只输出**一条** git 命令。不要用 `&&`、`|`、`;` 串联多条。
  如果一个意图确实需要多步，先输出第一步，并在 note 里说明后续还要做什么。
- 命令必须以 `git` 开头。
- 优先选择**可逆**的做法。比如撤销提交优先用 `git revert` 而不是 `git reset --hard`；
  丢弃改动优先建议先 `git stash` 保存一份。
- explanation 写给新手看：说清楚这条命令会改变什么、改完之后是什么状态。
  不要罗列参数含义，要说人话。
- 如果用户的描述有歧义，选最保守的解释，并在 note 里说明你是怎么理解的。
- 如果用户想做的事有数据丢失风险，在 note 里明确指出会丢什么。

你会拿到当前仓库的状态，请结合它生成准确的命令（比如分支名、文件名要对得上）。"""


_EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "一句话说清这条命令的作用。",
        },
        "detail": {
            "type": "string",
            "description": "逐部分解释，包括每个参数的含义。写给新手看，不要术语堆砌。",
        },
        "risk_note": {
            "type": "string",
            "description": "执行后会不会丢东西、丢什么、能不能找回来。没有风险就写没有风险。",
        },
        "safer_alternative": {
            "type": "string",
            "description": "如果有更安全的替代做法就给出来；没有则填空字符串。",
        },
    },
    "required": ["summary", "detail", "risk_note", "safer_alternative"],
    "additionalProperties": False,
}

_EXPLAIN_SYSTEM = """你在向一个**不熟悉 git 的新手**解释一条命令。

用户通常是从网上抄到这条命令，还没执行，想先搞清楚它是干什么的。

规则：
- 用中文，说人话。不要罗列参数手册，要说「执行完之后会变成什么样」。
- detail 里逐个解释参数，但要结合这条命令的实际语境，别背文档。
- risk_note 必须诚实：会丢数据就明说会丢什么、能不能找回来。不会丢也要明说。
- 如果这条命令有更安全的替代写法（比如用 revert 代替 reset --hard，
  或者先 stash 保存一份），在 safer_alternative 里给出来。确实没有就留空。
- 命令可能是用 && 串起来的多条。那就整体解释它们连起来达成什么效果。
- 如果命令有明显问题（参数写错、危险且没有必要），直接指出来。"""


class TranslationError(Exception):
    """翻译失败。消息是给用户看的，要能直接打印。"""


@dataclass
class Suggestion:
    command: str
    explanation: str
    confidence: str
    note: str


@dataclass
class Explanation:
    summary: str
    detail: str
    risk_note: str
    safer_alternative: str


def load_dotenv(path: Path | None = None) -> None:
    """把 .env 里的变量读进环境。已存在的环境变量优先，不覆盖。

    自己写而不是依赖 python-dotenv —— 这点功能不值得多一个依赖。
    """
    env_file = path or Path.cwd() / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("\"'")


def _request(system: str, schema: dict, user_content: str) -> dict:
    """调一次 API，返回解析好的 JSON。翻译和解释共用这条路径。"""
    try:
        import anthropic
    except ImportError:
        raise TranslationError(
            "缺少 anthropic 包。安装：pip install anthropic"
        ) from None

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise TranslationError(
            "没有找到 ANTHROPIC_API_KEY。\n"
            "  从 https://console.anthropic.com 获取，然后二选一：\n"
            "    export ANTHROPIC_API_KEY=...\n"
            "    或复制 .env.example 成 .env 并填进去"
        )

    client = anthropic.Anthropic()
    model = os.environ.get("AIGGYGIT_MODEL", DEFAULT_MODEL)

    try:
        response = client.messages.create(
            model=model,
            # 给足空间：thinking 和回复共用这个上限，卡太紧会截断
            max_tokens=8192,
            system=system,
            output_config={
                # 这类任务不需要深思，low 又快又省
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema},
            },
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.AuthenticationError:
        raise TranslationError("API Key 无效，检查 ANTHROPIC_API_KEY") from None
    except anthropic.RateLimitError:
        raise TranslationError("触发速率限制，稍等一下再试") from None
    except anthropic.APIConnectionError:
        raise TranslationError("连不上 Anthropic API，检查网络") from None
    except anthropic.APIStatusError as exc:
        raise TranslationError(f"API 报错（{exc.status_code}）：{exc.message}") from None

    if response.stop_reason == "refusal":
        raise TranslationError("模型拒绝了这个请求")
    if response.stop_reason == "max_tokens":
        raise TranslationError("回复被截断了，请把需求描述得更短一些")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise TranslationError("模型没有返回内容")

    return json.loads(text)  # output_config.format 保证了这里是合法 JSON


def translate(request: str, repo_context: str) -> Suggestion:
    """把一句自然语言翻译成一条 git 命令。"""
    data = _request(
        _SYSTEM,
        _SCHEMA,
        f"仓库当前状态：\n{repo_context}\n\n我想做的事：{request}",
    )
    return Suggestion(
        command=data["command"].strip(),
        explanation=data["explanation"].strip(),
        confidence=data["confidence"],
        note=data["note"].strip(),
    )


def explain_command(command: str, repo_context: str | None = None) -> Explanation:
    """解释一条 git 命令。不执行，只解释。"""
    content = f"请解释这条命令：\n{command}"
    if repo_context:
        content += f"\n\n（供参考的仓库当前状态）\n{repo_context}"
    data = _request(_EXPLAIN_SYSTEM, _EXPLAIN_SCHEMA, content)
    return Explanation(
        summary=data["summary"].strip(),
        detail=data["detail"].strip(),
        risk_note=data["risk_note"].strip(),
        safer_alternative=data["safer_alternative"].strip(),
    )
