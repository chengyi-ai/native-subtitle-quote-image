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
    <a href="#完整工作流">完整工作流</a> ·
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

这是一个可直接安装到兼容 Agent 中的开放 Skill：它从本地视频或用户有权处理的在线视频开始，经过来源获取、文字稿定位、选题选句、精确取帧、裁切、拼图和逐张质检，把带有**画面内嵌字幕**的视频变成适合社交平台发布的 3:4 长图。

它不会 OCR 后重绘字幕，也不会翻译或覆盖文字。成品里的画面和字幕都来自原视频帧。

仓库内包含：

- 可复制到兼容 Agent 的独立 Skill；
- 符合 Codex 插件结构的安装包；
- `yt-dlp`、Deno/Node 和辅助文字时间轴的 URL 工作流；
- 用文字稿选题、再回到真实视频帧校准字幕的完整方法；
- 自动生成带时间点的候选帧总览；
- 生成字幕区域预览、聚焦候选帧、3:4 JPG、时间点清单和最终总览图的本地脚本；
- 核心模式与 URL 模式的只读环境诊断。

## 完整工作流

```text
本地视频 / YouTube 链接
        ↓
yt-dlp 获取视频、元数据和辅助字幕轨（URL 模式）
        ↓
确认字幕真的烧录在画面里
        ↓
字幕轨或 Whisper 建立带时间戳的内容索引（可选）
        ↓
视频理解 / 选题 / 写作 Skill 提名主题（可选）
        ↓
回到真实视频帧，校准每句字幕稳定出现的时间点
        ↓
预览字幕区域 → manifest → 3:4 渲染 → 逐张 QA
```

这里最重要的边界是：**字幕轨和语音识别只负责理解、选题和定位；最终图片中的字必须来自视频画面本身。**

Skill 支持三种工作模式：

1. **本地成片模式**：视频已经下载，画面已有烧录字幕；不需要 `yt-dlp` 或 Whisper。
2. **URL 完整模式**：使用 `yt-dlp` 获取用户有权处理的视频与时间轴，再确认烧录字幕、选句和出图。
3. **内容生产模式**：完成“读视频 → 选题 → 写文章/帖子 → 原生字幕截图”；其他内容 Skill 作为上游，本 Skill 始终负责最终真实画面和质检。

### 组件分层

| 组件 | 本地模式 | URL 模式 | 用途 |
|---|---:|---:|---|
| `native-subtitle-quote-image` | 必需 | 必需 | 选帧、裁切、拼图和最终 QA |
| Python 3.10+ | 必需 | 必需 | 运行 Skill 脚本 |
| Pillow | 必需 | 必需 | 裁图、拼图、导出 JPG |
| `imageio-ffmpeg` 或 FFmpeg | 必需 | 必需 | 读取视频与精确取帧 |
| `yt-dlp` | 不需要 | 必需 | 获取在线视频、元数据和字幕轨 |
| Deno；或显式启用 Node.js | 不需要 | YouTube 必需 | 完整解析 YouTube 格式 |
| Whisper / 语音识别 Skill | 可选 | 可选 | 没有可用字幕轨时生成时间索引 |
| 选题、写作或视频理解 Skill | 可选 | 可选 | 从文字稿提名主题并生产配套内容 |

详细说明：

- [URL 获取、yt-dlp、Deno/Node 与文字时间轴](skills/native-subtitle-quote-image/references/yt-dlp-and-transcripts.md)
- [从读视频、选题到交付的完整工作流](skills/native-subtitle-quote-image/references/end-to-end-workflow.md)

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

### 安装核心依赖

```bash
python3 -m pip install -r skills/native-subtitle-quote-image/requirements.txt
python3 skills/native-subtitle-quote-image/scripts/check_environment.py
```

### URL 模式

URL 模式额外需要 `yt-dlp` 和 JavaScript runtime。yt-dlp 官方当前推荐 Deno；已有 Node.js 时也可以使用，但命令要添加 `--js-runtimes node`。

```bash
python3 -m pip install -U "yt-dlp[default]"
python3 skills/native-subtitle-quote-image/scripts/check_environment.py --url-mode
```

环境诊断不会自动安装或修改软件。缺少组件时，Agent 应先说明用途并取得授权。

### 其他 Agent

该 Skill 使用开放的 Agent Skills 目录格式。把 `skills/native-subtitle-quote-image/` 复制到目标 Agent 支持的 Skills 目录；具体目录和启用方式以目标 Agent 的说明为准。

## 使用

在 Agent 中直接输入：

```text
使用 $native-subtitle-quote-image，把这个带内嵌中文字幕的视频做成原生字幕拼图。
```

输入是链接时：

```text
使用 $native-subtitle-quote-image，读取这个 YouTube 链接，先检查下载权限和烧录字幕，再选 3 个适合传播的主题，制作成原生字幕拼图并逐张质检。
```

需要配合内容生产时：

```text
先根据视频文字稿提炼选题并写文章，再用 $native-subtitle-quote-image 为每个核心观点制作一张保留原字幕的配图；不要把文章文案画进图片。
```

Agent 会先检查字幕和裁切区域，再选择字幕稳定出现的时间点，最后生成：

- 逐张 3:4 JPG；
- `原生字幕时间点.json`；
- `final_contact_sheet.jpg` 总览图。

### 本地脚本

先生成带时间点的候选帧总览，减少反复试时间点：

```bash
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py sample VIDEO \
  --start 30 --end 120 --interval 5 --out candidate-contact-sheet.jpg
```

不传 `--start`、`--end` 和 `--interval` 时，脚本会在整段视频中自动均匀抽取最多 24 帧。确认字幕区域和时间点后，再使用 `band` 与 `render`；完整参数可通过 `--help` 查看。

文字稿已经给出候选时间点时，围绕每个时间点生成前、中、后三帧，避免截到字幕切换瞬间：

```bash
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py sample VIDEO \
  -t 61.2 -t 68.9 -t 74.5 -t 82.0 -t 88.4 \
  --around 0.8 --out focused-candidates.jpg
```

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
python3 skills/native-subtitle-quote-image/scripts/check_environment.py
python3 skills/native-subtitle-quote-image/scripts/native_subtitle_stitch.py --help
```

每次推送和 Pull Request 都会在 Python 3.10 与 3.13 环境中通过 GitHub Actions 自动运行检查。

## 开源许可

代码与 Skill 指令采用 [MIT License](LICENSE)。输入视频、生成图片及其中出现的第三方内容不因本许可证获得额外授权。
