---
name: native-subtitle-quote-image
description: 将本地视频或用户有权处理的在线视频中已经烧录在画面里的字幕，经过来源获取、文字稿定位、选题选句、精确取帧、裁切、3:4 拼图和逐张质检，制作成原生字幕社交长图。用户要求保留原视频字幕、YouTube 原生字幕截图、字幕帧拼图、不要重绘字幕、主画面加字幕条，或修改既有拼图的时间点、字幕区域、比例和画面数量时使用；独立字幕轨重绘、自动翻译覆字不属于本 Skill。
---

# 原生字幕拼图

最终成品中的文字必须来自视频画面像素。字幕轨、OCR、Whisper 和大模型文字稿只能帮助理解内容与定位时间点，不得把它们重新绘制或覆盖到成品上。

## 先选择模式

- **本地视频，时间点明确**：直接执行本文件的核心流程。
- **YouTube 等 URL**：先读取 [references/yt-dlp-and-transcripts.md](references/yt-dlp-and-transcripts.md)，获取用户有权处理的视频和辅助时间轴，再回到核心流程。
- **需要读视频、选题、写文章并配图**：读取 [references/end-to-end-workflow.md](references/end-to-end-workflow.md)，按内容生产模式协作。
- **长视频、时间点未知或需要多张成套输出**：读取完整工作流中的选题、聚焦采样和质检章节。

若视频只有可开关的字幕轨，画面本身没有烧录字幕，停止并说明本 Skill 不适用。只有用户明确同意后，才转到“重新绘制字幕”的其他工作流。

## 路径与环境

将 `<SKILL_DIR>` 解析为当前 `SKILL.md` 所在目录的绝对路径；不要假设 Agent 的工作目录就是 Skill 目录。

先运行只读环境诊断：

```bash
python3 "<SKILL_DIR>/scripts/check_environment.py"
```

URL 模式改用：

```bash
python3 "<SKILL_DIR>/scripts/check_environment.py" --url-mode
```

核心模式需要 Python 3.10+、Pillow，以及 FFmpeg 或 `imageio-ffmpeg`。缺失时先向用户说明并取得安装授权，再运行：

```bash
python3 -m pip install -r "<SKILL_DIR>/requirements.txt"
```

环境检查只报告状态，不负责安装。不要擅自修改系统 Python、shell 配置、浏览器 Cookies 或包管理器。

## 不可变规则

- 默认输出 3:4、1440×1920。
- 每张图默认使用 5 个严格递增的时间点：第一帧做主画面，其余四帧做字幕条。
- 主画面和字幕条都保留原字幕；不要翻译、改写、重排或覆盖文字。
- 默认字幕区域为画面高度的 `0.68–0.96`；两行字幕或位置偏高时先预览再调整。
- 保存最终时间点 manifest、逐张 JPG 和 `final_contact_sheet.jpg`。
- 不覆盖已有成品；创建新输出目录。只有用户明确要求替换时才添加 `--overwrite`。
- 源视频低清时可以输出 1440×1920 版面，但必须说明这不等于真实清晰度提升。

## 核心流程

### 1. 确认输入与字幕类型

确认视频是本地文件，并且字幕直接烧录在画面内。关闭播放器的字幕开关后仍存在、任意截图里都能看到文字，才属于本 Skill 的输入。

不知道时间点时，先生成整段候选帧：

```bash
python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" sample VIDEO \
  --out candidate-contact-sheet.jpg
```

默认在整段视频中均匀抽取最多 24 帧。需要细看一个区间时：

```bash
python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" sample VIDEO \
  --start 30 --end 120 --interval 5 \
  --out candidate-contact-sheet.jpg
```

### 2. 从文字稿时间点找稳定字幕帧

文字稿时间戳常落在字幕刚出现的瞬间。对多个候选时间点生成前、中、后三帧：

```bash
python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" sample VIDEO \
  -t 61.2 -t 68.9 -t 74.5 -t 82.0 -t 88.4 \
  --around 0.8 --out focused-candidates.jpg
```

从总览中选择字幕完整显示的中间帧。相邻时间点必须对应不同句字幕；避免空字幕、同句重复、切换残影、转场、黑帧、广告贴片和人物闭眼。

### 3. 预览字幕区域

```bash
python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" band VIDEO -t 61.2 \
  --band-top 0.68 --band-bottom 0.96 \
  --out band-preview.jpg
```

检查红线是否包含完整字幕与描边，同时避免不必要的黑边。字幕位置变化时抽查视频开头、中段、结尾。

### 4. 建立 manifest

```json
{
  "images": [
    {
      "title": "模型独立工作时长正在快速增长",
      "times": [61.6, 69.3, 75.0, 82.4, 88.8]
    }
  ]
}
```

标题只用于文件命名和交付说明，不会画进图片。`times` 必须来自最终确认的真实帧，不要把未经回看验证的文字稿时间戳直接交给渲染器。

### 5. 渲染

```bash
python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" render VIDEO \
  --manifest manifest.json --out-dir OUTPUT_DIR \
  --aspect 3:4 --width 1440 \
  --band-top 0.68 --band-bottom 0.96
```

### 6. 逐张检查并有界返工

先看 `final_contact_sheet.jpg`，再用图像查看工具打开每张原尺寸 JPG。检查：

- 字幕完整、稳定、无重复，顺序与原视频一致；
- 主画面主体完整，没有异常切脸、巨大空白或无关 UI；
- 字幕条之间没有黑边、白缝、缩放变形；
- 文件数量、尺寸、manifest 和总览图一致；
- 一张图表达一个连贯观点，没有用文章文案替换原字幕。

有问题时只调整对应时间点 `0.3–1.5` 秒或字幕区域，再渲染到新目录。连续三轮仍找不到稳定画面时，换片段或报告限制，不要无限微调。

## 与其他工具或 Skill 协作

- `yt-dlp`：URL 模式的来源获取工具，不是最终渲染器。
- 字幕轨或 Whisper：生成带时间戳的内容索引，只用于理解和定位。
- 视频理解、选题或内容分析 Skill：提名值得传播的主题和时间范围。
- 写作 Skill：围绕已确认主题写文章或帖子；不能改变图片中的原字幕。
- 本 Skill：最终时间点、真实画面、原生字幕裁切和视觉 QA 的真源。

复用上游已经下载的视频、文字稿和缓存，不重复消耗网络或转写成本。不要假设用户一定安装了某个命名 Skill；如果没有，就完成最低限度的文字稿阅读和主题选择。用户只要求做图时，不擅自写文章、发布内容或下载额外素材。

## 停止条件

出现以下情况时停止并说明：

- 用户没有下载、处理或发布来源素材的权限；
- 链接需要绕过 DRM、付费墙、地区限制或其他访问控制；
- 视频没有画面内烧录字幕；
- 找不到可稳定显示的字幕帧；
- 源画质或遮挡严重到无法达到可读交付。

登录或用户自己的非公开视频需要 Cookies 时，必须先取得授权；不索取密码、不导出 Cookie 文件、不把浏览器数据写入仓库。

## 资源

- [references/yt-dlp-and-transcripts.md](references/yt-dlp-and-transcripts.md)：URL 获取、Deno/Node、字幕轨、Whisper 与访问限制。
- [references/end-to-end-workflow.md](references/end-to-end-workflow.md)：从读视频、选题到交付的完整流程与 QA。
- `scripts/check_environment.py`：核心模式和 URL 模式环境诊断。
- `scripts/native_subtitle_stitch.py`：`sample`、`band`、`render` 三个阶段的执行器。
- `requirements.txt`：核心渲染依赖。

## 交付

提供输出目录、总览图、逐张成品、时间点 manifest 和已完成的检查。直接展示总览图。只有用户需要分享包时再生成 ZIP；不得把未经逐张打开检查的图片报告为完成。
