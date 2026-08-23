---
name: native-subtitle-quote-image
description: 将自带画面内嵌中文字幕的视频，按真实字幕出现的精确帧裁切并拼成社交平台长图。用户要求保留原视频字幕、原生字幕拼图、字幕帧截图、不要重绘字幕、主画面加字幕条，或要把这种样式做成固定模板时使用；也用于修改既有原生字幕拼图的时间点、字幕区域、比例和画面数量。
---

# 原生字幕拼图

只处理画面中已经存在字幕的视频。不要重写、翻译或覆盖字幕；成品中的文字必须来自原视频帧。

## 路径与依赖

- 将下文的 `<SKILL_DIR>` 解析为当前 `SKILL.md` 所在目录的绝对路径。不要假设 Agent 的工作目录就是 Skill 目录。
- 使用 Python 3.10+。运行前用脚本自身检查 Pillow 与 FFmpeg：

  ```bash
  python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" --help
  ```

- 依赖缺失时，先向用户说明并取得安装授权，再运行：

  ```bash
  python3 -m pip install -r "<SKILL_DIR>/requirements.txt"
  ```

## 固定样式

- 默认输出 3:4、1440×1920。
- 每张图默认使用 5 个时间点：第一帧作为主画面，其余 4 帧裁成字幕画面条。
- 主画面和字幕条都保留原字幕，按字幕底部向上裁切。
- 默认字幕区域为画面高度的 `0.68–0.96`；实际位置不符时先预览再调整。
- 保存时间点 manifest、总览图和逐张 JPG。
- 不覆盖用户已有成品，使用新的输出目录。

## 工作流

1. 确认输入是本地视频，且字幕烧录在画面内。若只有外挂字幕或没有字幕，先停止并说明这个 Skill 不适用；不要假设用户安装了其他 Skill。
2. 生成带时间点的候选帧总览。未指定区间时，脚本会在整段视频中自动均匀抽取最多 24 帧；需要细看某一区间时再传入起止时间与间隔：

   ```bash
   python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" sample VIDEO \
     --start 30 --end 120 --interval 5 --out candidate-contact-sheet.jpg
   ```

3. 从候选总览中选择字幕完整显示的中间帧。相邻时间点必须对应不同句字幕，避免空字幕、同句重复和字幕切换瞬间。
4. 预览字幕区域：

   ```bash
   python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" band VIDEO -t 60 \
     --band-top 0.68 --band-bottom 0.96 --out band-preview.jpg
   ```

5. 在任务输出目录创建 manifest：

   ```json
   {
     "images": [
       {"title": "热爱让创作发生", "times": [12, 16, 18, 22, 24]}
     ]
   }
   ```

6. 渲染整套：

   ```bash
   python3 "<SKILL_DIR>/scripts/native_subtitle_stitch.py" render VIDEO \
     --manifest manifest.json --out-dir OUTPUT_DIR \
     --aspect 3:4 --width 1440 --band-top 0.68 --band-bottom 0.96
   ```

7. 使用图像查看工具逐张检查最终 JPG 和 `final_contact_sheet.jpg`。检查字幕完整、无重复、无人脸被异常切断、画面条之间无黑边或空白。
8. 有问题时只调整对应 manifest 时间点 0.5–3 秒；确认要替换当前输出后，在重新渲染时添加 `--overwrite`，并再次检查。

## 选帧规则

- 优先选择字幕稳定显示后的中间帧，不取刚出现或即将消失的帧。
- 一张图内的 5 句应能构成连续表达，但允许跨过没有信息量的过渡句。
- 主画面优先人物、环境或关键动作清楚的帧；字幕条允许画面重复，但字幕文字不能重复。
- 原字幕位置较高或有两行字幕时，增大裁切区域，例如 `0.60–0.97`。
- 原视频分辨率较低时仍输出 1440×1920，但明确这是放大尺寸，不宣称提升真实清晰度。

## 资源

- `sample`：生成带时间点的候选帧总览，减少手工试错。
- `band`：预览字幕裁切区域。
- `render`：按 manifest 精确取帧并生成成品。
- `scripts/native_subtitle_stitch.py`：精确取帧、裁切、拼图和总览图生成器。
- `requirements.txt`：运行脚本所需的 Python 依赖。

## 交付

向用户提供输出目录、总览图、时间点 manifest 和 ZIP（若用户需要）。直接展示总览图。不得把未经逐张检查的图片报告为完成。
