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
    <a href="#complete-workflow">Workflow</a> ·
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

This open Agent Skill starts with a local video or an online video the user has the right to process. It handles source acquisition, transcript-assisted discovery, topic and quote selection, exact frame calibration, cropping, collage rendering, and per-image QA for videos with **burned-in subtitles**.

It does not run OCR and redraw the words, translate the subtitles, or place new text over the video. Every frame and subtitle in the result comes from the source video.

The repository includes:

- a standalone Skill for compatible agents;
- a Codex-compatible plugin package;
- a URL workflow covering `yt-dlp`, Deno/Node, and auxiliary subtitle tracks;
- a transcript-to-topic method that always returns to real video frames;
- candidate-frame contact sheets with timestamps;
- local tools for focused frame candidates, subtitle-band previews, 3:4 JPGs, timestamp manifests, and final contact sheets;
- a read-only environment checker for local and URL modes.

## Complete workflow

```text
Local video / YouTube URL
        ↓
yt-dlp obtains video, metadata, and auxiliary subtitle tracks (URL mode)
        ↓
Confirm that subtitles are actually burned into the pixels
        ↓
Subtitle track or Whisper builds a timestamped content index (optional)
        ↓
Video analysis / topic / writing Skills propose themes (optional)
        ↓
Return to real frames and calibrate stable subtitle timestamps
        ↓
Band preview → manifest → 3:4 render → per-image QA
```

The central rule is: **subtitle tracks and speech recognition help with understanding and navigation; the words in every final image must come from the video pixels.**

Three modes are supported:

1. **Local finished-video mode**: the video is already available and contains burned-in subtitles. `yt-dlp` and Whisper are unnecessary.
2. **Full URL mode**: use `yt-dlp` to obtain a video and timeline the user has the right to process, then verify burned-in subtitles and create the images.
3. **Content-production mode**: read the video, select topics, write an article or post, and create native-subtitle visuals. Upstream content Skills help with analysis; this Skill remains the source of truth for final frames and QA.

### Component layers

| Component | Local mode | URL mode | Role |
|---|---:|---:|---|
| `native-subtitle-quote-image` | Required | Required | Frame selection, cropping, collage rendering, and final QA |
| Python 3.10+ | Required | Required | Runs the Skill scripts |
| Pillow | Required | Required | Cropping, collage composition, and JPG export |
| `imageio-ffmpeg` or FFmpeg | Required | Required | Video decoding and exact frame extraction |
| `yt-dlp` | Not needed | Required | Online video, metadata, and subtitle-track acquisition |
| Deno, or explicitly enabled Node.js | Not needed | Required for full YouTube support | Full YouTube format extraction |
| Whisper / speech-to-text Skill | Optional | Optional | Builds a timeline when no subtitle track is available |
| Topic, writing, or video-understanding Skill | Optional | Optional | Proposes themes and produces companion content from the transcript |

Detailed implementation guides (Chinese; the commands are language-independent):

- [URL acquisition, yt-dlp, Deno/Node, and timelines](skills/native-subtitle-quote-image/references/yt-dlp-and-transcripts.md)
- [End-to-end topic selection, frame calibration, rendering, and QA](skills/native-subtitle-quote-image/references/end-to-end-workflow.md)

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

### Install core dependencies

```bash
python3 -m pip install -r skills/native-subtitle-quote-image/requirements.txt
python3 skills/native-subtitle-quote-image/scripts/check_environment.py
```

### URL mode

URL mode also needs `yt-dlp` and a JavaScript runtime. yt-dlp currently recommends Deno. An existing Node.js installation also works when `--js-runtimes node` is added to yt-dlp commands.

```bash
python3 -m pip install -U "yt-dlp[default]"
python3 skills/native-subtitle-quote-image/scripts/check_environment.py --url-mode
```

The checker never installs or changes software. When something is missing, the agent should explain why it is needed and ask before installing it.

### Other agents

The Skill uses the open Agent Skills directory format. Copy `skills/native-subtitle-quote-image/` into the Skills directory supported by your agent and follow that agent's activation instructions.

## Use

Prompt your agent with:

```text
Use $native-subtitle-quote-image to turn this video with burned-in subtitles into native subtitle quote images.
```

For a URL:

```text
Use $native-subtitle-quote-image with this YouTube URL. Check download rights and burned-in subtitles first, then select three useful themes, create native subtitle collages, and inspect every image.
```

For a content pipeline:

```text
Use the timestamped transcript to choose topics and draft the article, then use $native-subtitle-quote-image to create one original-subtitle visual for each core point. Do not draw article copy into the images.
```

The workflow checks the subtitle band, selects stable subtitle frames, and delivers:

- 3:4 JPG files;
- `原生字幕时间点.json`, the timestamp manifest;
- `final_contact_sheet.jpg`, the output overview.

### Local CLI

Generate a timestamped candidate-frame sheet before choosing exact frames:

```bash
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py sample VIDEO \
  --start 30 --end 120 --interval 5 --out candidate-contact-sheet.jpg
```

When `--start`, `--end`, and `--interval` are omitted, the CLI samples up to 24 frames across the full video. Use `band` to preview the crop and `render` to create the final set. Run `--help` for all options.

When a transcript already provides candidate timestamps, generate before/middle/after frames around each point:

```bash
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py sample VIDEO \
  -t 61.2 -t 68.9 -t 74.5 -t 82.0 -t 88.4 \
  --around 0.8 --out focused-candidates.jpg
```

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
python3 skills/native-subtitle-quote-image/scripts/check_environment.py
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py --help
```

GitHub Actions runs the checks on Python 3.10 and 3.13 for every push and pull request.

## License

Code and Skill instructions are released under the [MIT License](LICENSE). No additional rights are granted for input videos, generated images, or third-party content appearing in them.
