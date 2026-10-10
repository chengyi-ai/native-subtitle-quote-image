import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills"
    / "native-subtitle-quote-image"
    / "scripts"
    / "native_subtitle_stitch.py"
)
ENV_SCRIPT = (
    ROOT
    / "skills"
    / "native-subtitle-quote-image"
    / "scripts"
    / "check_environment.py"
)
SPEC = importlib.util.spec_from_file_location("native_subtitle_stitch", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HelperTests(unittest.TestCase):
    def test_parse_aspect_and_safe_title(self):
        self.assertEqual(MODULE.parse_aspect("3:4"), (3.0, 4.0))
        self.assertEqual(MODULE.safe_title('a/b:c*?"<>|'), "a_b_c")

    def test_default_sample_times_cover_range_with_24_frames(self):
        times = MODULE.build_sample_times(0, 230, None, 48)
        self.assertEqual(len(times), 24)
        self.assertEqual(times[0], 0)
        self.assertAlmostEqual(times[-1], 230)

    def test_sample_times_enforce_frame_cap(self):
        with self.assertRaisesRegex(SystemExit, "超过上限"):
            MODULE.build_sample_times(0, 100, 1, 48)

    def test_focus_times_add_before_middle_and_after(self):
        times = MODULE.build_focus_times([1, 3], 0.5, 5, 48)
        self.assertEqual(times, [0.5, 1.0, 1.5, 2.5, 3.0, 3.5])

    def test_focus_times_clip_and_deduplicate_edges(self):
        times = MODULE.build_focus_times([0, 2.7], 0.5, 3, 48)
        self.assertEqual(times, [0.0, 0.5, 2.2, 2.7])

    def test_auto_layout_keeps_subtitle_strips_compact(self):
        self.assertEqual(MODULE.choose_hero_fraction(4), 0.7)
        self.assertEqual(MODULE.choose_hero_fraction(3), 0.775)
        self.assertEqual(MODULE.choose_hero_fraction(2), 0.82)
        self.assertEqual(MODULE.choose_hero_fraction(7), 0.48)
        self.assertEqual(MODULE.choose_hero_fraction(4, 0.6), 0.6)

    def test_script_lines_require_increasing_timestamps_and_text(self):
        lines = MODULE.normalize_script_lines(
            {
                "lines": [
                    {"t": 1, "text": "First"},
                    {"t": 2, "text": "Second"},
                ]
            },
            3,
        )
        self.assertEqual(lines[1]["text"], "Second")
        with self.assertRaisesRegex(SystemExit, "严格递增"):
            MODULE.normalize_script_lines(
                {
                    "lines": [
                        {"t": 2, "text": "First"},
                        {"t": 1, "text": "Second"},
                    ]
                },
                3,
            )
        with self.assertRaisesRegex(SystemExit, "最多支持 7"):
            MODULE.normalize_script_lines(
                {
                    "lines": [
                        {"t": index / 10, "text": f"Line {index}"}
                        for index in range(8)
                    ]
                },
                3,
            )

    def test_native_times_share_script_mode_cap(self):
        times = MODULE.normalize_times([index / 10 for index in range(7)])
        self.assertEqual(len(times), 7)
        with self.assertRaisesRegex(SystemExit, "最多支持 7"):
            MODULE.normalize_times([index / 10 for index in range(8)])

    def test_cjk_detection_covers_chinese_japanese_and_korean(self):
        self.assertTrue(MODULE.contains_cjk("中文"))
        self.assertTrue(MODULE.contains_cjk("かな"))
        self.assertTrue(MODULE.contains_cjk("한글"))
        self.assertFalse(MODULE.contains_cjk("English"))

    def test_hangul_detection(self):
        self.assertTrue(MODULE.contains_hangul("한글"))
        self.assertTrue(MODULE.contains_hangul("ㅋㅋ"))
        self.assertFalse(MODULE.contains_hangul("中文"))
        self.assertFalse(MODULE.contains_hangul("かな"))
        self.assertFalse(MODULE.contains_hangul("English"))

    def test_hangul_is_always_cjk(self):
        for sample in ("한글", "ㅋㅋ", "ᄀ"):
            self.assertTrue(MODULE.contains_hangul(sample))
            self.assertTrue(MODULE.contains_cjk(sample))
        for start, end in MODULE.HANGUL_RANGES:
            self.assertTrue(MODULE.contains_cjk(start))
            self.assertTrue(MODULE.contains_cjk(end))

    def test_font_candidates_put_korean_fonts_first_for_hangul(self):
        result = MODULE.font_candidates(None, "안녕하세요")
        self.assertEqual(
            result, MODULE.KOREAN_FONT_CANDIDATES + MODULE.FONT_CANDIDATES
        )
        self.assertLess(
            result.index("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
            result.index("/System/Library/Fonts/PingFang.ttc"),
        )
        self.assertLess(
            result.index("C:/Windows/Fonts/malgun.ttf"),
            result.index("C:/Windows/Fonts/msyh.ttc"),
        )

    def test_font_candidates_keep_user_font_first(self):
        result = MODULE.font_candidates("custom.ttf", "안녕하세요")
        self.assertEqual(result[0], "custom.ttf")
        self.assertEqual(result[1:3], MODULE.KOREAN_FONT_CANDIDATES)

    def test_font_candidates_unchanged_for_chinese_and_japanese(self):
        for text in ("中文台词", "かな"):
            self.assertEqual(
                MODULE.font_candidates(None, text), MODULE.FONT_CANDIDATES
            )
        self.assertEqual(
            MODULE.font_candidates("custom.ttf", "中文"),
            ["custom.ttf"] + MODULE.FONT_CANDIDATES,
        )

    def test_environment_check_local_mode_is_machine_readable(self):
        proc = subprocess.run(
            [sys.executable, str(ENV_SCRIPT), "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["mode"], "local")
        self.assertTrue(payload["ok"])
        components = {item["component"] for item in payload["components"]}
        self.assertIn("Python 3.10+", components)
        self.assertIn("yt-dlp", components)
        self.assertIn("CJK font", components)

    def test_environment_check_url_mode_guides_cookie_recovery(self):
        proc = subprocess.run(
            [sys.executable, str(ENV_SCRIPT), "--url-mode"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn("不要退回本地模式", proc.stdout)
        self.assertIn("--cookies-from-browser chrome", proc.stdout)

    def test_render_one_has_requested_dimensions(self):
        frame = Image.new("RGB", (640, 360), "#336699")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            MODULE, "grab_frame", return_value=frame
        ):
            out = Path(tmp) / "render.jpg"
            MODULE.render_one(
                "unused.mp4",
                [0, 1, 2, 3, 4],
                out,
                (3, 4),
                300,
                0.68,
                0.96,
                0.42,
                layout="fixed",
            )
            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (300, 400))

    def test_render_one_default_keeps_source_geometry_not_seventy_percent(self):
        def fake_frame(_video, seconds):
            color = "#cc0000" if seconds == 0 else "#0033cc"
            return Image.new("RGB", (640, 360), color)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            MODULE, "grab_frame", side_effect=fake_frame
        ):
            out = Path(tmp) / "auto-layout.jpg"
            MODULE.render_one(
                "unused.mp4",
                [0, 1, 2, 3, 4],
                out,
                (3, 4),
                300,
                0.78,
                0.96,
                None,
            )
            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (300, 284))
                self.assertGreater(rendered.getpixel((10, 160))[0], 180)
                self.assertGreater(rendered.getpixel((10, 164))[2], 150)

    def test_missing_input_is_readable_without_traceback(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "render",
                "/no/such/video.mp4",
                "--manifest",
                "/no/such/manifest.json",
                "--out-dir",
                "/tmp/unused-native-subtitle-output",
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("视频不存在或不是文件", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


class NaturalGeometryTests(unittest.TestCase):
    def test_native_subtitles_have_same_size_in_hero_and_every_strip(self):
        for frame_size in [(1280, 720), (720, 1280)]:
            for layout, fit in [("natural", "crop"), ("fixed", "pad"), ("fixed", "crop")]:
                with self.subTest(frame_size=frame_size, layout=layout, fit=fit):
                    w, h = frame_size
                    frame = Image.new("RGB", frame_size, "black")
                    # 宽度覆盖近全帧，模拟长字幕，能同时抓出裁字和字号不一致。
                    ImageDraw.Draw(frame).rectangle(
                        (round(w * 0.03), round(h * 0.88), round(w * 0.97), round(h * 0.91)),
                        fill="white",
                    )
                    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
                        MODULE, "grab_frame", return_value=frame
                    ):
                        out = Path(tmp) / "uniform.jpg"
                        MODULE.render_one("unused", [0, 1, 2, 3, 4], out, (3, 4), 1080,
                                          0.78, 0.96, None, layout=layout, fit=fit)
                        with Image.open(out) as opened:
                            mask = opened.convert("L").point(lambda p: 255 if p > 127 else 0)
                            runs = []
                            for y in range(mask.height):
                                bounds = mask.crop((0, y, mask.width, y + 1)).getbbox()
                                if bounds is not None:
                                    if not runs or runs[-1][1] != y:
                                        runs.append([y, y + 1, bounds[0], bounds[2]])
                                    else:
                                        runs[-1][1] = y + 1
                                        runs[-1][2] = min(runs[-1][2], bounds[0])
                                        runs[-1][3] = max(runs[-1][3], bounds[2])
                            self.assertEqual(len(runs), 5)
                            heights = [r[1] - r[0] for r in runs]
                            widths = [r[3] - r[2] for r in runs]
                            self.assertLessEqual(max(heights) - min(heights), 1)
                            self.assertLessEqual(max(widths) - min(widths), 1)
                            if layout == "fixed":
                                self.assertEqual(opened.size, (1080, 1440))
                                source_height = int(h * 0.96) + 4 * (int(h * 0.96) - int(h * 0.78))
                                scale = min(1080 / w, 1440 / source_height)
                                expected_width = (round(w * 0.97) - round(w * 0.03) + 1) * scale
                                if fit == "pad":
                                    self.assertLessEqual(abs(min(widths) - expected_width), 2)
                                else:
                                    # 长字幕只允许裁到安全边界：不小于留边版，也不碰画布边缘。
                                    self.assertGreaterEqual(min(widths), expected_width - 2)
                                    self.assertGreater(min(r[2] for r in runs), 0)
                                    self.assertLess(max(r[3] for r in runs), opened.width)
                            else:
                                self.assertGreater(min(widths), 1080 * 0.9)

    def test_crop_and_same_width_keep_exact_source_pixels(self):
        frame = Image.new("RGB", (1280, 720), "black")
        ImageDraw.Draw(frame).ellipse((100, 100, 300, 300), fill="white")
        cropped, y0, y1 = MODULE.crop_band(frame, 0, 0.72)
        result = MODULE.scale_to_width(cropped, 1280)
        self.assertEqual((y0, y1), (0, 518))
        self.assertEqual(result.size, (1280, 518))
        self.assertEqual(result.tobytes(), frame.crop((0, 0, 1280, 518)).tobytes())

    def test_scaling_preserves_circle_geometry(self):
        frame = Image.new("RGB", (1280, 518), "black")
        ImageDraw.Draw(frame).ellipse((100, 100, 300, 300), fill="white")
        result = MODULE.scale_to_width(frame, 640)
        bounds = result.convert("L").point(lambda p: 255 if p > 127 else 0).getbbox()
        self.assertEqual(result.size, (640, 259))
        self.assertLessEqual(abs((bounds[2] - bounds[0]) - (bounds[3] - bounds[1])), 1)

    def test_native_natural_retains_full_width_and_band_height(self):
        frame = Image.new("RGB", (640, 360), "#336699")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            MODULE, "grab_frame", return_value=frame
        ):
            out = Path(tmp) / "native.jpg"
            MODULE.render_one("unused", [0, 1, 2, 3, 4], out, (3, 4), None,
                              0.78, 0.96, None, layout="natural")
            with Image.open(out) as rendered:
                # 主图 345 + 四条 (345 - 280)，没有填满固定画布。
                self.assertEqual(rendered.size, (640, 605))

    def test_scripted_crop_does_not_stretch_hero_back_to_source_height(self):
        frame = Image.new("RGB", (1280, 720), "black")
        ImageDraw.Draw(frame).ellipse((100, 100, 300, 300), fill="white")
        lines = [{"t": index, "text": f"Line {index}"} for index in range(5)]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            MODULE, "grab_frame", return_value=frame
        ), mock.patch.object(MODULE, "draw_scripted_subtitle") as draw_text:
            out = Path(tmp) / "script.jpg"
            MODULE.scripted_render_one("unused", lines, out, (3, 4), None,
                                       0.88, None, None, None,
                                       layout="natural", frame_bottom=0.72)
            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (1280, 806))
                bounds = rendered.crop((0, 0, 1280, 518)).convert("L").point(
                    lambda p: 255 if p > 127 else 0
                ).getbbox()
                self.assertEqual(bounds[2] - bounds[0], bounds[3] - bounds[1])
            self.assertEqual([call.args[1] for call in draw_text.call_args_list],
                             [line["text"] for line in lines])

    def test_cli_rejects_conflicting_layout_and_invalid_crop_before_io(self):
        for options, message in [
            (["--layout", "natural", "--aspect", "3:4"], "不接受"),
            (["--layout", "natural", "--hero-fraction", "0.7"], "不接受"),
            (["--frame-top", "0.8", "--frame-bottom", "0.2"], "裁切必须满足"),
        ]:
            with self.subTest(options=options):
                proc = subprocess.run(
                    [sys.executable, str(SCRIPT), "render-script", "unused.mp4",
                     "--script", "unused.json", "--out", "unused.jpg", *options],
                    capture_output=True, text=True,
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(message, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)

    def test_cli_rejects_invalid_native_fit_options_before_io(self):
        for options, message in [
            (["--layout", "natural", "--fit", "crop"], "不接受 --fit"),
            (["--layout", "natural", "--crop-center", "0.4"], "不接受 --fit"),
            (["--crop-center", "1.5"], "0–1"),
            (["--fit", "pad", "--crop-center", "0.4"], "只用于 --fit crop"),
        ]:
            with self.subTest(options=options):
                proc = subprocess.run(
                    [sys.executable, str(SCRIPT), "render", "unused.mp4",
                     "--manifest", "unused.json", "--out-dir", "unused", *options],
                    capture_output=True, text=True,
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(message, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)


class SixLineCardTests(unittest.TestCase):
    def test_geometry_and_rendered_strips(self):
        self.assertEqual(MODULE.six_line_geometry(1080, 1440), (870, 114, 870 / 1440))
        colors = [(30 + i * 25, 50 + i * 20, 70 + i * 15) for i in range(6)]
        frames = [Image.new("RGB", (1080, 870), color) for color in colors]
        lines = [{"t": i, "text": f"Line {i}"} for i in range(6)]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            MODULE, "grab_frame", side_effect=frames
        ), mock.patch.object(MODULE, "draw_scripted_subtitle") as draw_text:
            out = Path(tmp) / "six-line.jpg"
            MODULE.scripted_render_one(
                "unused", lines, out, (3, 4), 1080, 0.60, None, None, None,
                six_line_card=True,
            )
            calls = draw_text.call_args_list
            self.assertEqual(len(calls), 6)
            self.assertEqual(calls[0].args[0].size, (1080, 870))
            self.assertTrue(all(call.args[0].size == (1080, 114) for call in calls[1:]))
            centers = [calls[0].args[2]] + [
                870 + i * 114 + call.args[2]
                for i, call in enumerate(calls[1:])
            ]
            self.assertEqual(centers, [813, 927, 1041, 1155, 1269, 1383])
            self.assertTrue(all(call.args[4] == 63 for call in calls))
            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (1080, 1440))
                # Distinct solid-color frames fill every row, including each seam.
                for i, y in enumerate((869, 870, 983, 984, 1097, 1098, 1211, 1212, 1325, 1326, 1439)):
                    expected = colors[0 if y < 870 else 1 + (y - 870) // 114]
                    actual = rendered.getpixel((540, y))
                    self.assertTrue(all(abs(a - e) <= 8 for a, e in zip(actual, expected)),
                                    (i, y, actual, expected))

    def test_invalid_cli_combinations_fail_before_video_io(self):
        for options, message in [
            (["--layout", "natural"], "只支持固定 3:4"),
            (["--hero-fraction", "0.6"], "不接受 --hero-fraction"),
            (["--aspect", "16:9"], "只支持固定 3:4"),
        ]:
            with self.subTest(options=options):
                proc = subprocess.run(
                    [sys.executable, str(SCRIPT), "render-script", "unused.mp4",
                     "--script", "unused.json", "--out", "unused.jpg",
                     "--six-line-card", *options],
                    capture_output=True, text=True,
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(message, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)

    def test_requires_exactly_six_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "unused.mp4"
            video.touch()
            script = Path(tmp) / "five.json"
            script.write_text(json.dumps({"lines": [
                {"t": i, "text": f"Line {i}"} for i in range(5)
            ]}), encoding="utf-8")
            args = mock.Mock(video=str(video), script=str(script), six_line_card=True)
            with mock.patch.object(MODULE, "video_metadata", return_value=(1080, 870, 10)):
                with self.assertRaisesRegex(SystemExit, "恰好 6 句"):
                    MODULE.command_render_script(args)

    def test_long_line_shrinks_before_reaching_safe_width(self):
        class MeasuredDraw:
            rendered = None

            def textbbox(self, position, text, font, stroke_width):
                return (0, 0, round(len(text) * font * 0.62) + 2 * stroke_width, font)

            def text(self, position, text, font, **kwargs):
                self.rendered = (position, text, font, kwargs)

        measured = MeasuredDraw()
        image = Image.new("RGB", (1080, 114), "white")
        with mock.patch.object(MODULE.ImageDraw, "Draw", return_value=measured), mock.patch.object(
            MODULE, "load_subtitle_font", side_effect=lambda path, size, text: size
        ):
            MODULE.draw_scripted_subtitle(image, "M" * 28, 57, None, 63, round(1080 * 0.92))
        position, text, chosen_size, kwargs = measured.rendered
        stroke = kwargs["stroke_width"]
        width = measured.textbbox((0, 0), text, chosen_size, stroke)[2]
        self.assertLess(chosen_size, 63)
        self.assertLessEqual(width, round(1080 * 0.92))
        self.assertGreaterEqual(position[0], 0)
        self.assertLessEqual(position[0] + width, image.width)
        self.assertGreaterEqual(position[1], 0)
        self.assertLessEqual(position[1] + chosen_size, image.height)


def subtitle_band(width, height, left, right, background="#5a5a5a"):
    """灰底上画白色黑描边的竖笔画，模拟烧录字幕。"""
    band = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(band)
    for x in range(left, right - 3, 9):
        draw.rectangle((x, height * 0.3, x + 3, height * 0.7), fill="white",
                       outline="black", width=1)
    return band


class SideCropTests(unittest.TestCase):
    def assertSubtitlesInside(self, canvas):
        """白色笔画的左右边界都不能贴到画布边缘，否则说明字被裁了。"""
        bright = canvas.convert("L").point(lambda p: 255 if p > 200 else 0)
        bounds = bright.getbbox()
        self.assertIsNotNone(bounds)
        self.assertGreater(bounds[0], 0)
        self.assertLess(bounds[2], canvas.width)

    def test_subtitle_extent_finds_text_and_ignores_plain_band(self):
        extent = MODULE.subtitle_extent(subtitle_band(640, 40, 200, 440))
        self.assertIsNotNone(extent)
        self.assertLessEqual(abs(extent[0] - 200), 3)
        self.assertLessEqual(abs(extent[1] - 436), 6)
        self.assertIsNone(MODULE.subtitle_extent(Image.new("RGB", (640, 40), "#5a5a5a")))

    def stack_with_subtitles(self, left, right, strips=4):
        hero = Image.new("RGB", (640, 300), "#336699")
        hero.paste(subtitle_band(640, 40, left, right), (0, 260))
        bands = [subtitle_band(640, 40, left, right) for _ in range(strips)]
        stack = MODULE.stack_parts([hero, *bands])
        extents = [MODULE.subtitle_extent(b) for b in [hero.crop((0, 260, 640, 300)), *bands]]
        return stack, extents

    def test_narrow_subtitles_fill_canvas_without_black_bars(self):
        stack, extents = self.stack_with_subtitles(260, 380)
        canvas, note = MODULE.fit_fixed_canvas(stack, extents, (300, 400))
        self.assertEqual(canvas.size, (300, 400))
        self.assertIn("无黑边", note)
        for y in (2, 397):
            self.assertGreater(max(canvas.getpixel((150, y))), 40)

    def test_wide_subtitles_limit_crop_and_keep_text(self):
        stack, extents = self.stack_with_subtitles(60, 580)
        canvas, note = MODULE.fit_fixed_canvas(stack, extents, (300, 400))
        self.assertIn("只裁去", note)
        padded = ImageOps.pad(stack, (300, 400), color="black")
        # 裁得比留边版少黑边，但所有字幕边界都在画布内。
        self.assertLess(canvas.convert("L").getbbox()[1], padded.convert("L").getbbox()[1])
        self.assertSubtitlesInside(canvas)

    def test_unknown_subtitle_or_pad_mode_falls_back_to_padding(self):
        stack, extents = self.stack_with_subtitles(260, 380)
        expected = ImageOps.pad(stack, (300, 400), method=Image.Resampling.LANCZOS, color="black")
        for fit, items, message in [
            ("crop", [extents[0], None, *extents[2:]], "第 2 句"),
            ("pad", extents, "--fit pad"),
        ]:
            with self.subTest(fit=fit):
                canvas, note = MODULE.fit_fixed_canvas(stack, items, (300, 400), fit)
                self.assertIn(message, note)
                self.assertEqual(canvas.tobytes(), expected.tobytes())

    def test_crop_center_moves_window_but_never_cuts_subtitles(self):
        hero = Image.new("RGB", (640, 300), "#336699")
        ImageDraw.Draw(hero).rectangle((0, 0, 100, 259), fill="#ff0000")
        stack = MODULE.stack_parts([hero, *[subtitle_band(640, 40, 260, 380)] * 4])
        extents = [(260, 380)] * 5
        left, _ = MODULE.fit_fixed_canvas(stack, extents, (300, 400), crop_center=0.0)
        centered, _ = MODULE.fit_fixed_canvas(stack, extents, (300, 400), crop_center=0.5)
        # 期望窗口靠左时会尽量左移，但仍须容纳字幕左右安全边界。
        self.assertLess(left.getpixel((5, 100))[2], centered.getpixel((5, 100))[2])
        self.assertSubtitlesInside(left)


class DuplicateFrameTests(unittest.TestCase):
    @staticmethod
    def frame(offset):
        image = Image.new("RGB", (320, 180), (40, 40, 40))
        ImageDraw.Draw(image).rectangle((offset, 40, offset + 60, 120), fill=(230, 200, 60))
        return image

    def test_identical_frames_are_rejected(self):
        frames = [self.frame(20)] * 4
        with self.assertRaises(SystemExit) as raised:
            MODULE.ensure_distinct_frames(frames, [1, 2, 3, 4])
        self.assertIn("静态封面", str(raised.exception))

    def test_moving_frames_pass(self):
        frames = [self.frame(20 + 50 * index) for index in range(4)]
        MODULE.ensure_distinct_frames(frames, [1, 2, 3, 4])

    def test_repeated_native_subtitle_band_is_rejected(self):
        frames = [self.frame(20 + 50 * index) for index in range(3)]
        bands = [self.frame(20), self.frame(120), self.frame(120)]
        with self.assertRaises(SystemExit) as raised:
            MODULE.ensure_distinct_frames(frames, [1, 2, 3], bands)
        self.assertIn("2.00s 与 3.00s", str(raised.exception))

    def test_cli_stops_on_static_video_unless_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "static.mp4"
            subprocess.run(
                [
                    MODULE.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=gray:size=640x360:rate=10",
                    "-t", "3", "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(video),
                ],
                check=True,
                capture_output=True,
            )
            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps({"images": [{"title": "static", "times": [0.5, 1.5, 2.5]}]}),
                encoding="utf-8",
            )
            command = [
                sys.executable, str(SCRIPT), "render", str(video),
                "--manifest", str(manifest), "--out-dir", str(tmp_path / "out"),
            ]
            blocked = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("静态封面", blocked.stderr)
            self.assertFalse((tmp_path / "out" / "01_static.jpg").exists())

            allowed = subprocess.run(
                [*command, "--allow-duplicate-frames"], capture_output=True, text=True
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertTrue((tmp_path / "out" / "01_static.jpg").is_file())


class CheckSourceTests(unittest.TestCase):
    @staticmethod
    def make_video(path, size, seconds=3):
        subprocess.run(
            [
                MODULE.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=10",
                "-t", str(seconds), "-c:v", "mpeg4", "-pix_fmt", "yuv420p",
                str(path),
            ],
            check=True,
            capture_output=True,
        )

    @staticmethod
    def check(video, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "check-source", str(video), *extra],
            capture_output=True,
            text=True,
        )

    def test_clean_hd_source_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "hd.mkv"
            self.make_video(video, "1280x720")
            proc = self.check(video, "--min-height", "720")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("自检通过", proc.stdout)
            self.assertNotIn("警告", proc.stderr)

    def test_low_resolution_warns_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "low.mkv"
            self.make_video(video, "640x360")
            proc = self.check(video)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("警告", proc.stderr)

    def test_min_height_fails_low_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "low.mkv"
            self.make_video(video, "640x360")
            proc = self.check(video, "--min-height", "720")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("低于 --min-height 720", proc.stderr)

    def test_corrupt_stream_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "bad.mkv"
            self.make_video(video, "1280x720")
            data = bytearray(video.read_bytes())
            start = len(data) // 3
            for index in range(start, start + 4000):
                data[index] = (data[index] * 7 + 13) % 256
            video.write_bytes(bytes(data))
            proc = self.check(video, "--seconds", "3")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("解码前 3 秒出现错误", proc.stderr)

    def test_unreadable_file_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "junk.mp4"
            video.write_bytes(b"not a video")
            proc = self.check(video)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("源视频自检失败", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)


class CliIntegrationTests(unittest.TestCase):
    def test_sample_band_and_render_with_synthetic_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "synthetic.mp4"
            subprocess.run(
                [
                    MODULE.FFMPEG,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=640x360:rate=10",
                    "-t",
                    "3",
                    "-c:v",
                    "mpeg4",
                    "-pix_fmt",
                    "yuv420p",
                    str(video),
                ],
                check=True,
                capture_output=True,
            )

            sample = tmp_path / "candidate.jpg"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "sample",
                    str(video),
                    "--start",
                    "0.5",
                    "--end",
                    "2.5",
                    "--interval",
                    "1",
                    "--out",
                    str(sample),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(sample.is_file())

            default_sample = tmp_path / "default-candidate.jpg"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "sample",
                    str(video),
                    "--out",
                    str(default_sample),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(default_sample.is_file())

            focused_sample = tmp_path / "focused-candidate.jpg"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "sample",
                    str(video),
                    "-t",
                    "1",
                    "-t",
                    "2",
                    "--around",
                    "0.2",
                    "--out",
                    str(focused_sample),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(focused_sample.is_file())

            band = tmp_path / "band.jpg"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "band",
                    str(video),
                    "-t",
                    "1",
                    "--out",
                    str(band),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(band.is_file())

            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {"images": [{"title": "合成测试", "times": [0.5, 1, 1.5, 2, 2.5]}]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out_dir = tmp_path / "output"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "render",
                    str(video),
                    "--manifest",
                    str(manifest),
                    "--out-dir",
                    str(out_dir),
                    "--width",
                    "300",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            output = out_dir / "01_合成测试.jpg"
            self.assertTrue(output.is_file())
            self.assertTrue((out_dir / "final_contact_sheet.jpg").is_file())
            self.assertTrue((out_dir / "原生字幕时间点.json").is_file())
            with Image.open(output) as rendered:
                self.assertEqual(rendered.size, (300, 284))

            script = tmp_path / "script.json"
            script.write_text(
                json.dumps(
                    {
                        "lines": [
                            {"t": 0.5, "text": "First point"},
                            {"t": 1.0, "text": "Second point"},
                            {"t": 1.5, "text": "Third point"},
                            {"t": 2.0, "text": "Fourth point"},
                            {"t": 2.5, "text": "Fifth point"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            scripted_output = tmp_path / "scripted.jpg"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "render-script",
                    str(video),
                    "--script",
                    str(script),
                    "--out",
                    str(scripted_output),
                    "--width",
                    "300",
                    "--font-size",
                    "18",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            with Image.open(scripted_output) as rendered:
                self.assertEqual(rendered.size, (300, 400))

            for command, inputs, expected in [
                ("render", ["--manifest", str(manifest), "--out-dir", str(tmp_path / "natural")], (640, 605)),
                ("render-script", ["--script", str(script), "--out", str(tmp_path / "natural-script.jpg"),
                                   "--frame-bottom", "0.72"], (640, 403)),
            ]:
                subprocess.run(
                    [sys.executable, str(SCRIPT), command, str(video), *inputs, "--layout", "natural"],
                    check=True, capture_output=True, text=True,
                )
                natural_path = (tmp_path / "natural" / "01_合成测试.jpg" if command == "render"
                                else tmp_path / "natural-script.jpg")
                with Image.open(natural_path) as rendered:
                    self.assertEqual(rendered.size, expected)

            fixed_dir = tmp_path / "explicit-fixed"
            subprocess.run(
                [sys.executable, str(SCRIPT), "render", str(video),
                 "--manifest", str(manifest), "--out-dir", str(fixed_dir),
                 "--aspect", "3:4", "--width", "300"],
                check=True, capture_output=True, text=True,
            )
            with Image.open(fixed_dir / "01_合成测试.jpg") as rendered:
                self.assertEqual(rendered.size, (300, 400))

            repeated = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "render",
                    str(video),
                    "--manifest",
                    str(manifest),
                    "--out-dir",
                    str(out_dir),
                    "--width",
                    "300",
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("--overwrite", repeated.stderr)


if __name__ == "__main__":
    unittest.main()
