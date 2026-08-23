<div align="center">
  <img src="assets/native-subtitle-quote-image-icon.png" alt="原生字幕拼图项目图标" width="184">

  <h1>原生字幕拼图</h1>

  <p><strong>Native Subtitle Quote Image · 把视频内嵌字幕变成 3:4 社交长图</strong></p>
  <p><em>保留原画面，也保留原字幕。</em></p>

  <p>中文 · <a href="README_EN.md">English</a></p>

  <p>
    <a href="https://github.com/chengyi-ai/native-subtitle-quote-image/actions/workflows/validate.yml"><img src="https://img.shields.io/github/actions/workflow/status/chengyi-ai/native-subtitle-quote-image/validate.yml?branch=main&style=flat-square&label=test" alt="测试状态"></a>
    <a href="https://github.com/chengyi-ai/native-subtitle-quote-image/releases"><img src="https://img.shields.io/github/v/release/chengyi-ai/native-subtitle-quote-image?style=flat-square&label=release" alt="最新版本"></a>
    <a href="https://github.com/chengyi-ai/native-subtitle-quote-image/stargazers"><img src="https://img.shields.io/github/stars/chengyi-ai/native-subtitle-quote-image?style=flat-square" alt="GitHub Stars"></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/chengyi-ai/native-subtitle-quote-image?style=flat-square" alt="MIT License"></a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Agent_Skills-open_format-f97316?style=flat-square" alt="开放 Agent Skills 格式">
    <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/docs-中文-e11d48?style=flat-square" alt="中文文档">
  </p>

  <p>
    <a href="#这是什么">这是什么</a> ·
    <a href="#demo">Demo</a> ·
    <a href="#安装">安装</a> ·
    <a href="#使用">使用</a> ·
    <a href="#判断边界">判断边界</a> ·
    <a href="#项目验证">验证</a> ·
    <a href="https://github.com/chengyi-ai/native-subtitle-quote-image/issues">反馈</a>
  </p>
</div>

---

## 这是什么

这是一个可直接安装到兼容 Agent 中的开放 Skill：它从带有**画面内嵌字幕**的视频精确取帧，把一张主画面和多条原生字幕画面拼成适合社交平台发布的 3:4 长图。

它不会 OCR 后重绘字幕，也不会翻译或覆盖文字。成品里的画面和字幕都来自原视频帧。

仓库内包含：

- 可复制到兼容 Agent 的独立 Skill；
- 符合 Codex 插件结构的安装包；
- 自动生成带时间点的候选帧总览；
- 生成字幕区域预览、3:4 JPG、时间点清单和最终总览图的本地脚本。

## Demo

下面两张图来自真实处理结果：第一张展示单张成品，第二张展示一次多图任务的成套输出。

### 单张拼图

<p align="center">
  <img src="examples/demo-native-subtitle-collage.jpg" alt="原生字幕拼图单张 Demo" width="420">
</p>

### 成套输出总览

<p align="center">
  <img src="examples/demo-output-overview.jpg" alt="原生字幕拼图成套输出总览" width="720">
</p>

> 示例图片只用于展示 Skill 的输出效果；图片及其中出现的第三方内容不属于本仓库 MIT License 的授权范围。

## 安装

### Codex Skill Installer

在 Codex 中调用 `$skill-installer`，并让它安装下面的 Skill 目录：

```text
https://github.com/chengyi-ai/native-subtitle-quote-image/tree/main/skills/native-subtitle-quote-image
```

### 手动安装到 Codex

```bash
git clone https://github.com/chengyi-ai/native-subtitle-quote-image.git
mkdir -p ~/.codex/skills
cp -R native-subtitle-quote-image/skills/native-subtitle-quote-image ~/.codex/skills/
```

重新打开 Codex 任务后即可使用 `$native-subtitle-quote-image`。

### 其他 Agent

该 Skill 使用开放的 Agent Skills 目录格式。把 `skills/native-subtitle-quote-image/` 复制到目标 Agent 支持的 Skills 目录；具体目录和启用方式以目标 Agent 的说明为准。

## 使用

在 Agent 中直接输入：

```text
使用 $native-subtitle-quote-image，把这个带内嵌中文字幕的视频做成原生字幕拼图。
```

Agent 会先检查字幕和裁切区域，再选择字幕稳定出现的时间点，最后生成：

- 逐张 3:4 JPG；
- `原生字幕时间点.json`；
- `final_contact_sheet.jpg` 总览图。

### 本地脚本

依赖 Python 3.10+、Pillow，以及 FFmpeg 或可提供 FFmpeg 的 `imageio-ffmpeg`：

```bash
python3 -m pip install -r skills/native-subtitle-quote-image/requirements.txt
```

先生成带时间点的候选帧总览，减少反复试时间点：

```bash
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py sample VIDEO \
  --start 30 --end 120 --interval 5 --out candidate-contact-sheet.jpg
```

不传 `--start`、`--end` 和 `--interval` 时，脚本会在整段视频中自动均匀抽取最多 24 帧。确认字幕区域和时间点后，再使用 `band` 与 `render`；完整参数可通过 `--help` 查看。

脚本默认拒绝覆盖已有图片。确认需要替换当前输出时，显式添加 `--overwrite`。

## 判断边界

### 这个 Skill 适合什么视频？

- 关闭播放器的 CC/字幕开关后，字幕仍然留在画面里；
- 任意截取一帧，字幕会直接出现在图片像素中；
- 使用者有权处理和发布输入视频及生成画面。

### 什么情况不适合？

- 字幕可以单独关闭、切换语言或下载为 `.srt`；
- 任务需要自动翻译、OCR 后改字或重新绘制字幕；
- 需要把低清视频“增强”为真实高清画质。

本 Skill 会保留原视频的画面与烧录字幕。外挂字幕合成、翻译和重绘属于不同工作流，不在这里混合实现。

### 素材从哪里来？

优先使用自己拍摄并添加字幕的视频、已经获得授权的素材，或明确允许再利用的公开视频。公开生成图片前，仍需确认素材使用权。

## 项目验证

```bash
python3 scripts/validate_repo.py
python3 -m unittest discover -s tests -v
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py --help
```

每次推送和 Pull Request 都会在 Python 3.10 与 3.13 环境中通过 GitHub Actions 自动运行检查。

## 开源许可

代码与 Skill 指令采用 [MIT License](LICENSE)。输入视频、生成图片及其中出现的第三方内容不因本许可证获得额外授权。
