<div align="center">
  <img src="assets/native-subtitle-quote-image-icon.png" alt="Native Subtitle Quote Image project icon" width="184">

  <h1>Native Subtitle Quote Image</h1>

  <p><strong>Turn burned-in video subtitles into 3:4 social quote images</strong></p>
  <p><em>Keep the original frame. Keep the original subtitle.</em></p>

  <p><a href="README.md">中文</a> · English</p>

  <p>
    <a href="https://github.com/chengyi-ai/native-subtitle-quote-image/actions/workflows/validate.yml"><img src="https://img.shields.io/github/actions/workflow/status/chengyi-ai/native-subtitle-quote-image/validate.yml?branch=main&style=flat-square&label=test" alt="Test status"></a>
    <a href="https://github.com/chengyi-ai/native-subtitle-quote-image/releases"><img src="https://img.shields.io/github/v/release/chengyi-ai/native-subtitle-quote-image?style=flat-square&label=release" alt="Latest release"></a>
    <a href="https://github.com/chengyi-ai/native-subtitle-quote-image/stargazers"><img src="https://img.shields.io/github/stars/chengyi-ai/native-subtitle-quote-image?style=flat-square" alt="GitHub Stars"></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/chengyi-ai/native-subtitle-quote-image?style=flat-square" alt="MIT License"></a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Agent_Skills-open_format-f97316?style=flat-square" alt="Open Agent Skills format">
    <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/docs-English-2563eb?style=flat-square" alt="English documentation">
  </p>

  <p>
    <a href="#what-it-does">What it does</a> ·
    <a href="#demo">Demo</a> ·
    <a href="#install">Install</a> ·
    <a href="#use">Use</a> ·
    <a href="#scope">Scope</a> ·
    <a href="#validation">Validation</a> ·
    <a href="https://github.com/chengyi-ai/native-subtitle-quote-image/issues">Feedback</a>
  </p>
</div>

---

## What it does

This open Agent Skill extracts exact frames from videos with **burned-in subtitles**. It combines one main frame with several native subtitle strips into a 3:4 image designed for social publishing.

It does not run OCR and redraw the words, translate the subtitles, or place new text over the video. Every frame and subtitle in the result comes from the source video.

The repository includes:

- a standalone Skill for compatible agents;
- a Codex-compatible plugin package;
- candidate-frame contact sheets with timestamps;
- local tools for subtitle-band previews, 3:4 JPGs, timestamp manifests, and final contact sheets.

## Demo

These are real outputs. The first image shows one finished collage; the second shows a complete multi-image delivery.

### Single collage

<p align="center">
  <img src="examples/demo-native-subtitle-collage.jpg" alt="Single native subtitle collage demo" width="420">
</p>

### Output overview

<p align="center">
  <img src="examples/demo-output-overview.jpg" alt="Native subtitle collage output overview" width="720">
</p>

> The demo images are included only to show the Skill's output. The MIT License does not grant rights to third-party content visible in those images.

## Install

### Codex Skill Installer

Ask `$skill-installer` in Codex to install this Skill directory:

```text
https://github.com/chengyi-ai/native-subtitle-quote-image/tree/main/skills/native-subtitle-quote-image
```

### Manual Codex install

```bash
git clone https://github.com/chengyi-ai/native-subtitle-quote-image.git
mkdir -p ~/.codex/skills
cp -R native-subtitle-quote-image/skills/native-subtitle-quote-image ~/.codex/skills/
```

Open a new Codex task, then invoke `$native-subtitle-quote-image`.

### Other agents

The Skill uses the open Agent Skills directory format. Copy `skills/native-subtitle-quote-image/` into the Skills directory supported by your agent and follow that agent's activation instructions.

## Use

Prompt your agent with:

```text
Use $native-subtitle-quote-image to turn this video with burned-in subtitles into native subtitle quote images.
```

The workflow checks the subtitle band, selects stable subtitle frames, and delivers:

- 3:4 JPG files;
- `原生字幕时间点.json`, the timestamp manifest;
- `final_contact_sheet.jpg`, the output overview.

### Local CLI

Requirements: Python 3.10+, Pillow, and either FFmpeg or `imageio-ffmpeg`:

```bash
python3 -m pip install -r skills/native-subtitle-quote-image/requirements.txt
```

Generate a timestamped candidate-frame sheet before choosing exact frames:

```bash
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py sample VIDEO \
  --start 30 --end 120 --interval 5 --out candidate-contact-sheet.jpg
```

When `--start`, `--end`, and `--interval` are omitted, the CLI samples up to 24 frames across the full video. Use `band` to preview the crop and `render` to create the final set. Run `--help` for all options.

Existing images are protected by default. Add `--overwrite` only when replacing the current output is intentional.

## Scope

### Good input

- The subtitle remains visible after the player's CC/subtitle control is turned off.
- A screenshot contains the subtitle directly in its pixels.
- You have the right to process and publish the video and generated frames.

### Out of scope

- Switchable subtitle tracks or downloadable `.srt` files.
- Subtitle translation, OCR-based rewriting, or redrawing.
- Turning low-resolution source footage into genuinely high-resolution footage.

Use footage you created, licensed material, or public video that clearly permits reuse. Confirm usage rights before publishing generated images.

## Validation

```bash
python3 scripts/validate_repo.py
python3 -m unittest discover -s tests -v
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py --help
```

GitHub Actions runs the checks on Python 3.10 and 3.13 for every push and pull request.

## License

Code and Skill instructions are released under the [MIT License](LICENSE). No additional rights are granted for input videos, generated images, or third-party content appearing in them.
