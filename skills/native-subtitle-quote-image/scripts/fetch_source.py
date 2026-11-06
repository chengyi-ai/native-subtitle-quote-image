#!/usr/bin/env python3
"""包装 yt-dlp 的下载入口：识别 HTTP 403 / 429 并做有上限的退避重试。

设计边界（与 SKILL.md 一致）：
- 不绕过 DRM、付费墙、地区限制或平台风控；403/429 只做有限重试和清楚报错。
- 429 是请求过密，退避等待后重试；403 大多是 yt-dlp 版本或该格式的签名失效，只重试一次。
- 任何失败都显式报错并记入 download-attempts.log，不静默失败、不无限重试。
- 不自行添加 Cookie 参数；Cookie 仅在用户授权后由调用方传入 --extra。
"""

import argparse
import datetime as _datetime
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ATTEMPT_LOG = "download-attempts.log"
# 429 默认最多重试 3 次；再多就是在硬冲平台速率限制。
DEFAULT_RETRIES = 3
MAX_RETRIES = 6
# 退避基数（秒）：等待为 base * 2**n，并封顶在 MAX_BACKOFF。
DEFAULT_BACKOFF = 30.0
MAX_BACKOFF = 600.0
# 403 通常不是速率问题，重试再多也没意义。
FORBIDDEN_RETRIES = 1
FORBIDDEN_BACKOFF = 5.0

RATE_LIMITED = "rate_limited"
FORBIDDEN = "forbidden"
BOT_CHECK = "bot_check"
OTHER = "other"

_PATTERNS = (
    (RATE_LIMITED, re.compile(r"HTTP Error 429|Too Many Requests", re.IGNORECASE)),
    (FORBIDDEN, re.compile(r"HTTP Error 403|\bForbidden\b", re.IGNORECASE)),
    (
        BOT_CHECK,
        re.compile(
            r"Sign in to confirm|confirm you\u2019?re not a bot|not a bot"
            r"|age[- ]restricted|cookies",
            re.IGNORECASE,
        ),
    ),
)

_ADVICE = {
    RATE_LIMITED: (
        "HTTP 429：请求过于频繁，常见于一次请求多条自动翻译字幕轨。"
        "缩减 --sub-langs 只留需要的一两个标签，加 --sleep-subtitles 5，并改成串行单个视频；"
        "不要换 IP 或缩短间隔硬冲。"
    ),
    FORBIDDEN: (
        "HTTP 403：通常是 yt-dlp 版本落后于站点改动，或该格品的签名 URL 已失效。"
        "先 python3 -m pip install -U 'yt-dlp[default]' 升级并确认 JavaScript runtime 生效，"
        "再按 references/yt-dlp-and-transcripts.md 的格式回退表逐级换 -f，每级只试一次。"
    ),
    BOT_CHECK: (
        "平台要求登录态（机器人验证、年龄验证或非公开视频）。不要重试："
        "先向用户复述真实报错并取得授权，再用 --extra 传入 --cookies-from-browser chrome。"
    ),
    OTHER: "yt-dlp 未按 403/429 分类失败，请看下方原始报错。",
}


def classify(text):
    """把 yt-dlp 的 stderr 归类；顺序重要，429 优先于 403。"""
    for kind, pattern in _PATTERNS:
        if pattern.search(text or ""):
            return kind
    return OTHER


def retry_plan(kind, retries, backoff):
    """返回（该类错误还能重试几次，退避基数）。"""
    if kind == RATE_LIMITED:
        return retries, backoff
    if kind == FORBIDDEN:
        return min(FORBIDDEN_RETRIES, retries), FORBIDDEN_BACKOFF
    # 登录验证和其他错误重试没有意义。
    return 0, backoff


def wait_seconds(backoff, attempt):
    return min(MAX_BACKOFF, backoff * (2 ** attempt))


def log_attempt(log_path, attempt, kind, detail):
    stamp = _datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{stamp}\t第 {attempt} 次\t{kind}\t{detail}\n"
    try:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError as exc:
        print(f"警告: 无法写入 {log_path}（{exc}）", file=sys.stderr)


def last_lines(text, count=4):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return "\n".join(lines[-count:]) or "没有返回错误详情"


def run_once(command):
    proc = subprocess.run(
        command, capture_output=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def fetch(command, retries, backoff, log_path, sleeper=time.sleep, runner=run_once):
    """执行 yt-dlp 并按错误类型退避重试；成功返回 0，否则非零。"""
    attempt = 0
    while True:
        attempt += 1
        code, stdout, stderr = runner(command)
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if code == 0:
            log_attempt(log_path, attempt, "成功", " ".join(command[1:]) or "-")
            print(f"下载成功（第 {attempt} 次尝试），尝试记录: {log_path}")
            return 0
        kind = classify(stderr)
        detail = last_lines(stderr, 1)
        log_attempt(log_path, attempt, kind, detail)
        allowed, base = retry_plan(kind, retries, backoff)
        remaining = allowed - (attempt - 1)
        if remaining <= 0:
            print(
                f"下载失败（{kind}，共 {attempt} 次尝试）。\n{_ADVICE[kind]}\n"
                f"yt-dlp 原始报错:\n{last_lines(stderr)}\n尝试记录: {log_path}",
                file=sys.stderr,
            )
            return 1
        delay = wait_seconds(base, attempt - 1)
        print(
            f"第 {attempt} 次失败（{kind}），{delay:.0f}s 后重试，还剩 {remaining} 次。\n"
            f"{_ADVICE[kind]}",
            file=sys.stderr,
        )
        sleeper(delay)


def build_command(args, ytdlp):
    command = [ytdlp, "--no-playlist"]
    if args.mode == "metadata":
        command += [
            "--skip-download",
            "--print",
            "%(id)s | %(title)s | %(channel)s | %(duration_string)s",
        ]
    elif args.mode == "subs":
        command += ["--skip-download", "--write-subs", "--write-auto-subs",
                    "--sub-format", "vtt", "--sub-langs", args.sub_langs,
                    "--sleep-subtitles", str(args.sleep_subtitles)]
    else:
        command += ["-f", args.format]
    if args.output:
        command += ["-o", args.output]
    command += list(args.extra)
    command.append(args.url)
    return command


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument(
        "--mode", choices=("metadata", "subs", "video"), default="video",
        help="metadata 只读元数据；subs 只下字幕；video 下视频（默认）",
    )
    parser.add_argument(
        "-f", "--format", default="bv*[height<=1080]+ba/b[height<=1080]",
        help="video 模式的 yt-dlp -f 参数",
    )
    parser.add_argument("-o", "--output", help="yt-dlp -o 输出模板")
    parser.add_argument(
        "--sub-langs", default="zh-Hans,en-orig",
        help="subs 模式的字幕语言标签；先用 --list-subs 看真实标签，不要用 zh.* 这类泛匹配",
    )
    parser.add_argument(
        "--sleep-subtitles", type=float, default=5.0,
        help="subs 模式每条字幕轨之间的等待秒数，默认 5，降低 429 概率",
    )
    parser.add_argument(
        "--retries", type=int, default=DEFAULT_RETRIES,
        help=f"429 最多重试次数，0–{MAX_RETRIES}，默认 {DEFAULT_RETRIES}；403 始终最多重试 1 次",
    )
    parser.add_argument(
        "--backoff", type=float, default=DEFAULT_BACKOFF,
        help=f"退避基数秒，等待为 base×2^n 并封顶 {MAX_BACKOFF:.0f}s，默认 {DEFAULT_BACKOFF:.0f}",
    )
    parser.add_argument(
        "--log", help=f"尝试日志路径，默认当前工作目录的 {ATTEMPT_LOG}",
    )
    parser.add_argument(
        "--extra", nargs=argparse.REMAINDER, default=[],
        help="透传给 yt-dlp 的其余参数，必须放在最后（例如 --extra --cookies-from-browser chrome）",
    )
    args = parser.parse_args(argv)

    if not 0 <= args.retries <= MAX_RETRIES:
        parser.error(f"--retries 必须在 0–{MAX_RETRIES} 之间")
    if not 0 < args.backoff <= MAX_BACKOFF:
        parser.error(f"--backoff 必须大于 0 且不超过 {MAX_BACKOFF:.0f}")
    if args.sleep_subtitles < 0:
        parser.error("--sleep-subtitles 不能为负数")

    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise SystemExit(
            "找不到 yt-dlp；先说明用途并取得授权后运行"
            ' python3 -m pip install -U "yt-dlp[default]"'
        )

    log_path = Path(args.log).expanduser() if args.log else Path(os.getcwd()) / ATTEMPT_LOG
    command = build_command(args, ytdlp)
    print("执行: " + " ".join(["yt-dlp", *command[1:]]))
    return fetch(command, args.retries, args.backoff, log_path)


if __name__ == "__main__":
    sys.exit(main())
