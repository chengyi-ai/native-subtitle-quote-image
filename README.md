# 原生字幕拼图 Skill

把带有画面内嵌字幕的视频按精确时间点取帧，生成适合社交平台的 3:4 字幕拼接长图。它保留原视频画面和原生字幕，不重新绘制、翻译或覆盖文字。

本仓库同时提供：

- 可直接复制到兼容 Agent 的独立 Skill；
- 符合 Codex 插件结构的安装包；
- 生成字幕区域预览、成品 JPG、时间点清单和总览图的本地脚本。

## Demo

下面是已有视频的实际处理成品。单张示例保留顶部主画面，并把不同时间点出现的原生字幕裁切后依次拼接成 3:4 长图；总览图展示一次多图任务的成套输出。

### 单张拼图

<p align="center">
  <img src="examples/demo-native-subtitle-collage.jpg" alt="原生字幕拼图单张 Demo" width="420">
</p>

### 成套输出总览

<p align="center">
  <img src="examples/demo-output-overview.jpg" alt="原生字幕拼图成套输出总览" width="720">
</p>

示例图片仅用于展示 Skill 的输出效果；图片及其中出现的第三方内容不属于本仓库 MIT License 的授权范围。

## 安装

### Codex Skill Installer

在 Codex 中调用 `$skill-installer`，并让它安装下面的 Skill 目录：

```text
https://github.com/chengyi-ai/native-subtitle-quote-image/tree/main/skills/native-subtitle-quote-image
```

### 手动安装到 Codex

```bash
git clone https://github.com/chengyi-ai/native-subtitle-quote-image.git
cp -R native-subtitle-quote-image/skills/native-subtitle-quote-image ~/.agents/skills/
```

重新打开 Codex 任务后即可使用 `$native-subtitle-quote-image`。

### 其他 Agent

该 Skill 使用开放的 Agent Skills 目录格式。把 `skills/native-subtitle-quote-image/` 复制到目标 Agent 支持的 Skills 目录；具体目录和启用方式以目标 Agent 的说明为准。

## 依赖

- Python 3.10+
- Pillow
- FFmpeg，或可提供 FFmpeg 的 `imageio-ffmpeg`

```bash
python3 -m pip install -r skills/native-subtitle-quote-image/requirements.txt
```

## 使用

在 Agent 中输入：

```text
使用 $native-subtitle-quote-image，把这个带内嵌中文字幕的视频做成原生字幕拼图。
```

Agent 会先检查视频字幕与裁切区域，再选择字幕稳定出现的时间点，最后生成：

- 逐张 3:4 JPG；
- `原生字幕时间点.json`；
- `final_contact_sheet.jpg` 总览图。

## 适用边界

- 只适用于字幕已经烧录在视频画面中的素材。
- 外挂字幕、自动翻译或重新绘制字幕不属于这个 Skill 的工作范围。
- 使用者应确保自己有权处理和发布输入视频及生成画面。

## 开源许可

代码与 Skill 指令采用 [MIT License](LICENSE)。输入视频、生成图片及其中出现的第三方内容不因本许可证获得额外授权。
