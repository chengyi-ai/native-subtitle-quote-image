import argparse
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("PYTHONUTF8", "1")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills"
    / "native-subtitle-quote-image"
    / "scripts"
    / "fetch_source.py"
)
SPEC = importlib.util.spec_from_file_location("fetch_source", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeRunner:
    """按顺序返回预设的 (returncode, stdout, stderr)，最后一项重复使用。"""

    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def __call__(self, command):
        self.calls += 1
        index = min(self.calls - 1, len(self.results) - 1)
        return self.results[index]


class ClassifyTests(unittest.TestCase):
    def test_429_and_403_are_distinguished(self):
        self.assertEqual(
            MODULE.classify("ERROR: unable to download: HTTP Error 429: Too Many Requests"),
            MODULE.RATE_LIMITED,
        )
        self.assertEqual(
            MODULE.classify("ERROR: unable to download video data: HTTP Error 403: Forbidden"),
            MODULE.FORBIDDEN,
        )

    def test_429_wins_when_both_appear(self):
        text = "HTTP Error 403: Forbidden\nHTTP Error 429: Too Many Requests"
        self.assertEqual(MODULE.classify(text), MODULE.RATE_LIMITED)

    def test_bot_check_and_unknown(self):
        self.assertEqual(
            MODULE.classify("Sign in to confirm you\u2019re not a bot"),
            MODULE.BOT_CHECK,
        )
        self.assertEqual(MODULE.classify("ERROR: ffmpeg not found"), MODULE.OTHER)
        self.assertEqual(MODULE.classify(""), MODULE.OTHER)


class RetryPlanTests(unittest.TestCase):
    def test_429_uses_full_budget_403_only_one(self):
        self.assertEqual(MODULE.retry_plan(MODULE.RATE_LIMITED, 3, 30.0), (3, 30.0))
        allowed, base = MODULE.retry_plan(MODULE.FORBIDDEN, 3, 30.0)
        self.assertEqual(allowed, MODULE.FORBIDDEN_RETRIES)
        self.assertEqual(base, MODULE.FORBIDDEN_BACKOFF)

    def test_bot_check_is_never_retried(self):
        self.assertEqual(MODULE.retry_plan(MODULE.BOT_CHECK, 3, 30.0)[0], 0)
        self.assertEqual(MODULE.retry_plan(MODULE.OTHER, 3, 30.0)[0], 0)

    def test_backoff_grows_and_is_capped(self):
        self.assertEqual(MODULE.wait_seconds(30.0, 0), 30.0)
        self.assertEqual(MODULE.wait_seconds(30.0, 1), 60.0)
        self.assertEqual(MODULE.wait_seconds(30.0, 10), MODULE.MAX_BACKOFF)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "download-attempts.log"
        self.waits = []

    def fetch(self, results, retries=3, backoff=30.0):
        runner = FakeRunner(results)
        code = MODULE.fetch(
            ["yt-dlp", "URL"], retries, backoff, self.log,
            sleeper=self.waits.append, runner=runner,
        )
        return code, runner

    def test_429_retries_then_succeeds_with_growing_backoff(self):
        code, runner = self.fetch([
            (1, "", "HTTP Error 429: Too Many Requests"),
            (1, "", "HTTP Error 429: Too Many Requests"),
            (0, "done", ""),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(runner.calls, 3)
        self.assertEqual(self.waits, [30.0, 60.0])
        text = self.log.read_text(encoding="utf-8")
        self.assertIn(MODULE.RATE_LIMITED, text)
        self.assertIn("成功", text)

    def test_429_stops_at_retry_limit_and_fails_loudly(self):
        code, runner = self.fetch([(1, "", "HTTP Error 429")], retries=2)
        self.assertEqual(code, 1)
        # 首次 + 2 次重试，不无限重试。
        self.assertEqual(runner.calls, 3)
        self.assertEqual(len(self.waits), 2)
        self.assertEqual(
            self.log.read_text(encoding="utf-8").count(MODULE.RATE_LIMITED), 3
        )

    def test_403_retries_once_only(self):
        code, runner = self.fetch([(1, "", "HTTP Error 403: Forbidden")], retries=5)
        self.assertEqual(code, 1)
        self.assertEqual(runner.calls, MODULE.FORBIDDEN_RETRIES + 1)
        self.assertEqual(self.waits, [MODULE.FORBIDDEN_BACKOFF])

    def test_403_recovers_after_single_retry(self):
        code, runner = self.fetch([
            (1, "", "HTTP Error 403: Forbidden"),
            (0, "", ""),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(runner.calls, 2)

    def test_bot_check_fails_without_retrying(self):
        code, runner = self.fetch([(1, "", "Sign in to confirm you are not a bot")])
        self.assertEqual(code, 1)
        self.assertEqual(runner.calls, 1)
        self.assertEqual(self.waits, [])
        self.assertIn(MODULE.BOT_CHECK, self.log.read_text(encoding="utf-8"))

    def test_retries_zero_disables_retry_for_429(self):
        code, runner = self.fetch([(1, "", "HTTP Error 429")], retries=0)
        self.assertEqual(code, 1)
        self.assertEqual(runner.calls, 1)

    def test_every_attempt_is_logged(self):
        self.fetch([(1, "", "HTTP Error 429")], retries=1)
        lines = [
            line for line in self.log.read_text(encoding="utf-8").splitlines() if line
        ]
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertEqual(len(line.split("\t")), 4)


class BuildCommandTests(unittest.TestCase):
    def build(self, **overrides):
        namespace = argparse.Namespace(
            url="URL", mode="video", format="bv*+ba", output=None,
            sub_langs="zh-Hans", sleep_subtitles=5.0, extra=[],
        )
        for key, value in overrides.items():
            setattr(namespace, key, value)
        return MODULE.build_command(namespace, "yt-dlp")

    def test_video_mode_passes_format_and_no_playlist(self):
        command = self.build()
        self.assertEqual(command[0], "yt-dlp")
        self.assertIn("--no-playlist", command)
        self.assertIn("-f", command)
        self.assertEqual(command[-1], "URL")

    def test_subs_mode_skips_download_and_sleeps(self):
        command = self.build(mode="subs")
        self.assertIn("--skip-download", command)
        self.assertIn("--sleep-subtitles", command)
        # 字幕命令不带视频格式，两条命令互不影响。
        self.assertNotIn("-f", command)

    def test_metadata_mode_only_prints(self):
        command = self.build(mode="metadata")
        self.assertIn("--print", command)
        self.assertIn("--skip-download", command)

    def test_extra_arguments_are_passed_through_before_url(self):
        command = self.build(extra=["--cookies-from-browser", "chrome"])
        self.assertEqual(command[-3:], ["--cookies-from-browser", "chrome", "URL"])


if __name__ == "__main__":
    unittest.main()
