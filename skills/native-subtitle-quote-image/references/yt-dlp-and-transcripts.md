# URL 获取与时间轴

当输入是 YouTube 等在线视频链接，而不是本地视频时，读取本文件。`yt-dlp` 只负责获取用户有权处理的视频、元数据和字幕时间轴；最终图片仍由 `native_subtitle_stitch.py` 从视频像素取帧。

## 先区分两种“字幕”

| 内容 | 用途 | 能否直接出现在最终图片中 |
|---|---|---|
| 画面内烧录字幕 | 最终成品的文字来源 | 可以，必须从真实视频帧保留 |
| YouTube 字幕轨、VTT/SRT、Whisper 文字稿 | 理解内容、选题、定位时间点 | 不可以直接覆盖到成品上 |

有字幕轨不等于视频画面有字幕。下载后必须实际取帧检查；若画面没有烧录字幕，停止原生字幕工作流并向用户说明，可改用“重新绘制字幕”的另一套工作流，但不要在本 Skill 内偷偷切换。

## 官方依据

- [yt-dlp 官方 README](https://github.com/yt-dlp/yt-dlp#readme)
- [安装说明](https://github.com/yt-dlp/yt-dlp/wiki/Installation)
- [External JavaScript 指南](https://github.com/yt-dlp/yt-dlp/wiki/EJS)

yt-dlp 当前要求 Python 3.10+。完整 YouTube 支持强烈建议 FFmpeg、`yt-dlp-ejs` 和 JavaScript runtime。官方优先推荐 Deno；Node.js、QuickJS、Bun 也可用，但 Deno 之外的 runtime 需要通过 `--js-runtimes` 显式启用。

## 环境检查

先运行 Skill 自带的只读诊断：

```bash
python3 "<SKILL_DIR>/scripts/check_environment.py" --url-mode
```

它不会安装软件，只报告：

- Python、Pillow、FFmpeg provider 是否可用；
- `yt-dlp` 版本；
- Deno 或其他 JavaScript runtime；
- 可选的 Whisper/语音识别能力。

缺少组件时先向用户说明，再取得安装授权。不要擅自修改系统 Python、包管理器或 shell 配置。

### 安装与更新原则

- 核心渲染依赖：`python3 -m pip install -r "<SKILL_DIR>/requirements.txt"`。
- yt-dlp 可使用官方独立可执行文件，或安装 PyPI 的 `yt-dlp[default]`；`default` extra 会带上官方推荐的 Python 依赖。
- 官方文档当前建议普通用户使用 nightly；若稳定版遇到站点解析问题，先按官方说明更新 nightly，再判断是不是命令或权限问题。
- Deno 使用官方安装方式；若环境已经有 Node.js，可保留 Node，并在每条 yt-dlp 命令中加入 `--js-runtimes node`。

示例（使用 pip 的环境）：

```bash
python3 -m pip install -U "yt-dlp[default]"
```

稳定版出现站点解析错误、且用户同意更新时：

```bash
python3 -m pip install -U --pre "yt-dlp[default]"
```

不要把“安装成功”和“能解析当前链接”混为一谈；安装后至少运行：

```bash
yt-dlp --version
yt-dlp --no-playlist --skip-download --print "%(id)s | %(title)s | %(duration_string)s" "URL"
```

## 获取顺序

### 1. 只读检查元数据

```bash
yt-dlp --no-playlist --skip-download \
  --print "%(id)s | %(title)s | %(channel)s | %(duration_string)s" \
  "URL"
```

使用 Node.js 时：

```bash
yt-dlp --js-runtimes node --no-playlist --skip-download \
  --print "%(id)s | %(title)s | %(channel)s | %(duration_string)s" \
  "URL"
```

先确认链接指向单个目标视频。默认添加 `--no-playlist`，避免一个播放列表被意外整批下载。

### 2. 列出字幕轨

```bash
yt-dlp --no-playlist --list-subs "URL"
```

记录可用语言标签，不要假设一定叫 `zh`、`en` 或 `en-orig`。

### 3. 只下载文字时间轴

优先人工字幕，同时允许自动字幕作为备选：

```bash
yt-dlp --no-playlist --skip-download \
  --write-subs --write-auto-subs \
  --sub-langs "zh.*,en.*" --sub-format vtt \
  -o "source/%(id)s/%(id)s.%(ext)s" \
  "URL"
```

字幕轨只用来建立“内容—时间点”索引。不要把 VTT 文本直接画回最终图片，也不要因为文字稿里有一句话，就假设该时刻画面内的烧录字幕完全相同。

### 4. 下载视频

通常不需要 4K。1080p 足以做 1440×1920 的社交图；输出尺寸可能放大，但不应宣称提升了真实清晰度。

```bash
yt-dlp --no-playlist \
  -f "bv*[height<=1080]+ba/b[height<=1080]" \
  -o "source/%(id)s/%(id)s.%(ext)s" \
  "URL"
```

分离的视频和音频需要 FFmpeg 合并。原生字幕取帧不依赖音频，但保留带音频的完整源文件方便复核内容。重复执行时复用已有文件，不要无理由重新下载。

## 没有可用字幕轨

按以下顺序处理：

1. 检查视频描述、章节和人工字幕轨；
2. 检查自动字幕轨；
3. 如果画面本身有烧录字幕，可先用候选帧总览人工选句；
4. 用户确实需要长视频的语义选段时，再询问是否允许使用本地 Whisper 或环境中已有的语音转写 Skill。

Whisper 是可选上游，只为生成带时间戳文字稿。它的识别文本不能替代画面内原生字幕，时间点也必须回到视频帧验证。

## 登录、Cookies 与访问限制

- 只处理用户有权访问、下载和再利用的内容。
- 遇到登录、年龄验证或用户自己的非公开视频时，先说明原因并取得授权，再考虑 `--cookies-from-browser`。
- 不要求用户粘贴账号密码，不导出或提交 Cookie 文件，不把浏览器配置、访问令牌或绝对路径写入仓库。
- 不绕过 DRM、付费墙、地区限制或其他访问控制。
- Cookies 失败时停止并报告，不要反复尝试多个浏览器账户。

## 常见故障

### `yt-dlp` 有版本但 YouTube 格式不完整

先看诊断里是否存在 JavaScript runtime。Deno 默认启用；Node.js 环境必须显式添加：

```bash
yt-dlp --js-runtimes node ...
```

随后更新 yt-dlp。不要先改一串实验性 extractor 参数，因为这会让工作流难以复现。

### 字幕语言下载不到

先运行 `--list-subs`，按真实语言标签修改 `--sub-langs`。不要把自动翻译字幕当成人工原字幕。

### 视频下载成功，但图片里没有字幕

这是输入类型不符合本 Skill，而不是渲染失败。说明该视频只有独立字幕轨；若用户同意，转到重新绘制字幕的工作流。

### 下载很慢或中断

保留工作目录和分片，重试同一条命令以复用缓存。连续失败后报告网络或站点限制，不要无限重试。
