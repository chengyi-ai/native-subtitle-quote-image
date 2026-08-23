#!/usr/bin/env python3
"""把带内嵌字幕的视频精确取帧并拼成原生字幕长图。"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

try:
    import imageio_ffmpeg

    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG = shutil.which("ffmpeg")
    if not FFMPEG:
        sys.exit("找不到 ffmpeg；请安装 ffmpeg 或 imageio-ffmpeg")


def ffmpeg(args, context="FFmpeg 处理失败"):
    try:
        return subprocess.run(
            [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        raise SystemExit(f"找不到 FFmpeg 可执行文件: {FFMPEG}") from None
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace").strip()
        detail = "\n".join(stderr.splitlines()[-4:]) or "没有返回错误详情"
        raise SystemExit(f"{context}:\n{detail}") from None


def input_file(value, label):
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"{label}不存在或不是文件: {path}")
    return path


def video_metadata(path):
    proc = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    stderr = proc.stderr or ""
    size_match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})[\s,]", stderr)
    duration_match = re.search(
        r"Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)", stderr
    )
    if not size_match or not duration_match:
        raise SystemExit(f"无法读取视频尺寸或时长: {path}")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return int(size_match.group(1)), int(size_match.group(2)), duration


def validate_time(value, label="时间点"):
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise SystemExit(f"{label}必须是数字: {value!r}") from None
    if not math.isfinite(seconds) or seconds < 0:
        raise SystemExit(f"{label}必须是大于等于 0 的有限数字: {value!r}")
    return seconds


def grab_frame(path, seconds):
    """先快速跳转，再精确解码 3 秒，避免长 GOP 视频错帧。"""
    seconds = validate_time(seconds)
    preseek = max(0.0, seconds - 3.0)
    offset = seconds - preseek
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        ffmpeg(
            [
                "-ss",
                f"{preseek:.3f}",
                "-i",
                str(path),
                "-ss",
                f"{offset:.3f}",
                "-frames:v",
                "1",
                tmp,
            ],
            context=f"取帧失败 @ {seconds:.2f}s",
        )
        if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
            raise SystemExit(f"取帧失败 @ {seconds:.2f}s")
        with Image.open(tmp) as opened:
            image = opened.convert("RGB")
            image.load()
        return image
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def parse_aspect(value):
    try:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError
        width, height = (float(x) for x in parts)
    except Exception as exc:
        raise argparse.ArgumentTypeError("比例必须写成 3:4 这样的格式") from exc
    if not math.isfinite(width) or not math.isfinite(height):
        raise argparse.ArgumentTypeError("比例必须是有限数字")
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("比例必须为正数")
    return width, height


def safe_title(value):
    cleaned = re.sub(r"[\\/:*?\"<>|\n\r]+", "_", str(value)).strip(" ._")
    return cleaned or "未命名"


def normalize_times(values, label="时间点"):
    if not isinstance(values, list) or len(values) < 2:
        raise SystemExit(f"{label}必须是至少包含 2 项的数组")
    times = [
        validate_time(value, f"{label}[{index}]")
        for index, value in enumerate(values)
    ]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise SystemExit(f"{label}必须严格递增: {values}")
    return times


def crop_band(frame, top, bottom):
    if not 0 <= top < bottom <= 1:
        raise SystemExit("字幕区域必须满足 0 <= top < bottom <= 1")
    y0, y1 = int(frame.height * top), int(frame.height * bottom)
    if y1 <= y0:
        raise SystemExit("--band-bottom 必须大于 --band-top")
    return frame.crop((0, y0, frame.width, y1)), y0, y1


def fit_lower(image, size, vertical=0.72):
    return ImageOps.fit(
        image,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, vertical),
    )


def render_one(video, times, out_path, aspect, out_width, top, bottom, hero_fraction):
    times = normalize_times(times)
    aw, ah = aspect
    out_height = round(out_width * ah / aw)
    hero_height = round(out_height * hero_fraction)
    remaining = out_height - hero_height
    strip_count = len(times) - 1
    base_strip = remaining // strip_count
    strip_heights = [base_strip] * strip_count
    strip_heights[-1] += remaining - sum(strip_heights)

    first = grab_frame(video, times[0])
    _, _, subtitle_bottom = crop_band(first, top, bottom)
    wanted_hero_source_h = min(
        subtitle_bottom,
        max(1, round(first.width * hero_height / out_width)),
    )
    hero_source = first.crop(
        (0, subtitle_bottom - wanted_hero_source_h, first.width, subtitle_bottom)
    )
    hero = fit_lower(hero_source, (out_width, hero_height), vertical=0.75)

    strips = []
    for seconds, height in zip(times[1:], strip_heights):
        frame = grab_frame(video, seconds)
        band, _, _ = crop_band(frame, top, bottom)
        strips.append(fit_lower(band, (out_width, height), vertical=0.72))

    canvas = Image.new("RGB", (out_width, out_height), "black")
    canvas.paste(hero, (0, 0))
    y = hero_height
    for strip in strips:
        canvas.paste(strip, (0, y))
        y += strip.height
    canvas.save(out_path, quality=93, subsampling=0)
    print(f"完成: {out_path} ({out_width}x{out_height})")


def contact_sheet(paths, out_path, columns=4):
    if not paths:
        return
    columns = min(columns, len(paths))
    with Image.open(paths[0]) as first:
        thumb_w = 360
        thumb_h = max(1, round(thumb_w * first.height / first.width))
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * thumb_h), "#111111")
    for index, path in enumerate(paths):
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            thumb = ImageOps.fit(image, (thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, ((index % columns) * thumb_w, (index // columns) * thumb_h))
    sheet.save(out_path, quality=92, subsampling=0)


def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remainder = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remainder:04.1f}"
    return f"{minutes:02d}:{remainder:04.1f}"


def build_sample_times(start, end, interval, max_frames):
    start = validate_time(start, "--start")
    end = validate_time(end, "--end")
    if end <= start:
        raise SystemExit("--end 必须大于 --start")
    if max_frames <= 0:
        raise SystemExit("--max-frames 必须为正整数")
    if interval is None:
        interval = max(0.25, (end - start) / 23)
    interval = validate_time(interval, "--interval")
    if interval == 0:
        raise SystemExit("--interval 必须大于 0")
    count = int(math.floor((end - start) / interval)) + 1
    if count > max_frames:
        suggested = (end - start) / max(1, max_frames - 1)
        raise SystemExit(
            f"候选帧数量为 {count}，超过上限 {max_frames}；"
            f"请把 --interval 调整为至少 {suggested:.2f} 秒"
        )
    return [start + index * interval for index in range(count)]


def sample_contact_sheet(video, times, out_path, video_size, columns, thumb_width):
    frame_width, frame_height = video_size
    thumb_height = max(1, round(thumb_width * frame_height / frame_width))
    label_height = 28
    columns = min(columns, len(times))
    rows = (len(times) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * thumb_width, rows * (thumb_height + label_height)),
        "#111111",
    )
    for index, seconds in enumerate(times):
        frame = grab_frame(video, seconds)
        thumb = ImageOps.contain(
            frame, (thumb_width, thumb_height), Image.Resampling.LANCZOS
        )
        tile = Image.new("RGB", (thumb_width, thumb_height + label_height), "#111111")
        tile.paste(thumb, ((thumb_width - thumb.width) // 2, 0))
        draw = ImageDraw.Draw(tile)
        draw.text((8, thumb_height + 7), format_timestamp(seconds), fill="white")
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        sheet.paste(tile, (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=90, subsampling=0)


def refuse_existing(paths, overwrite):
    existing = [path for path in paths if path.exists()]
    if existing and not overwrite:
        listed = "\n".join(f"- {path}" for path in existing[:8])
        raise SystemExit(
            "以下输出已存在；请使用新的输出路径，或明确添加 --overwrite:\n" + listed
        )


def command_band(args):
    video = input_file(args.video, "视频")
    _, _, duration = video_metadata(video)
    timestamp = validate_time(args.time, "--time")
    if timestamp >= duration:
        raise SystemExit(f"--time 必须小于视频时长 {duration:.2f}s")
    out_path = Path(args.out).expanduser().resolve()
    refuse_existing([out_path], args.overwrite)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame = grab_frame(video, timestamp)
    _, y0, y1 = crop_band(frame, args.band_top, args.band_bottom)
    draw = ImageDraw.Draw(frame)
    line_width = max(3, frame.height // 300)
    draw.line((0, y0, frame.width, y0), fill="red", width=line_width)
    draw.line((0, y1, frame.width, y1), fill="red", width=line_width)
    frame.save(out_path, quality=93)
    print(f"字幕区域预览: {out_path} (y={y0}-{y1})")


def command_sample(args):
    video = input_file(args.video, "视频")
    width, height, duration = video_metadata(video)
    decode_margin = min(0.5, duration / 10)
    latest_decodable = max(0.0, duration - decode_margin)
    end = latest_decodable if args.end is None else validate_time(args.end, "--end")
    if end > duration + 0.05:
        raise SystemExit(f"--end 超出视频时长 {duration:.2f}s")
    end = min(end, latest_decodable)
    times = build_sample_times(args.start, end, args.interval, args.max_frames)
    if args.columns <= 0:
        raise SystemExit("--columns 必须为正整数")
    if args.thumb_width < 120:
        raise SystemExit("--thumb-width 不能小于 120")
    out_path = Path(args.out).expanduser().resolve()
    refuse_existing([out_path], args.overwrite)
    sample_contact_sheet(
        video, times, out_path, (width, height), args.columns, args.thumb_width
    )
    print(f"候选帧总览: {out_path}")
    print("时间点: " + ", ".join(f"{value:.2f}" for value in times))


def command_render(args):
    video = input_file(args.video, "视频")
    manifest_path = input_file(args.manifest, "manifest")
    try:
        with manifest_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"manifest JSON 格式错误（第 {exc.lineno} 行第 {exc.colno} 列）: {exc.msg}"
        ) from None

    items = data.get("images") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise SystemExit("manifest 必须包含非空 images 数组")

    _, _, duration = video_metadata(video)
    jobs = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise SystemExit(f"images 第 {index} 项必须是对象")
        title = safe_title(item.get("title", f"图片{index}"))
        times = normalize_times(item.get("times"), f"images[{index}].times")
        if times[-1] >= duration:
            raise SystemExit(
                f"images[{index}].times 的最后时间点 {times[-1]:.2f}s "
                f"必须小于视频时长 {duration:.2f}s"
            )
        jobs.append((index, title, times))

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [out_dir / f"{index:02d}_{title}.jpg" for index, title, _ in jobs]
    manifest_target = out_dir / "原生字幕时间点.json"
    contact_target = out_dir / "final_contact_sheet.jpg"
    guarded = [*outputs, contact_target]
    if manifest_path != manifest_target:
        guarded.append(manifest_target)
    refuse_existing(guarded, args.overwrite)

    for (_, _, times), out_path in zip(jobs, outputs):
        render_one(
            video,
            times,
            out_path,
            args.aspect,
            args.width,
            args.band_top,
            args.band_bottom,
            args.hero_fraction,
        )

    if manifest_path != manifest_target:
        shutil.copyfile(manifest_path, manifest_target)
    contact_sheet(outputs, contact_target)
    print(f"总览图: {contact_target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("sample", help="生成带时间点的候选帧总览")
    sample.add_argument("video")
    sample.add_argument("--start", type=float, default=0.0)
    sample.add_argument("--end", type=float)
    sample.add_argument("--interval", type=float)
    sample.add_argument("--max-frames", type=int, default=48)
    sample.add_argument("--columns", type=int, default=4)
    sample.add_argument("--thumb-width", type=int, default=320)
    sample.add_argument("--out", default="candidate-contact-sheet.jpg")
    sample.add_argument("--overwrite", action="store_true")
    sample.set_defaults(func=command_sample)

    band = sub.add_parser("band", help="预览字幕裁切区域")
    band.add_argument("video")
    band.add_argument("-t", "--time", type=float, required=True)
    band.add_argument("--band-top", type=float, default=0.68)
    band.add_argument("--band-bottom", type=float, default=0.96)
    band.add_argument("--out", default="band-preview.jpg")
    band.add_argument("--overwrite", action="store_true")
    band.set_defaults(func=command_band)

    render = sub.add_parser("render", help="按 manifest 渲染整套拼图")
    render.add_argument("video")
    render.add_argument("--manifest", required=True)
    render.add_argument("--out-dir", required=True)
    render.add_argument("--aspect", type=parse_aspect, default=parse_aspect("3:4"))
    render.add_argument("--width", type=int, default=1440)
    render.add_argument("--band-top", type=float, default=0.68)
    render.add_argument("--band-bottom", type=float, default=0.96)
    render.add_argument("--hero-fraction", type=float, default=0.42)
    render.add_argument("--overwrite", action="store_true")
    render.set_defaults(func=command_render)

    args = parser.parse_args()
    if hasattr(args, "band_top") and not 0 <= args.band_top < args.band_bottom <= 1:
        raise SystemExit("字幕区域必须满足 0 <= top < bottom <= 1")
    if getattr(args, "width", 1) <= 0:
        raise SystemExit("--width 必须为正数")
    if hasattr(args, "hero_fraction") and not 0.25 <= args.hero_fraction <= 0.75:
        raise SystemExit("--hero-fraction 必须在 0.25–0.75 之间")
    args.func(args)


if __name__ == "__main__":
    main()
