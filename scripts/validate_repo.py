#!/usr/bin/env python3
"""Validate repository packaging invariants without external dependencies."""

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "native-subtitle-quote-image"
SKILL_FILE = SKILL_DIR / "SKILL.md"
OPENAI_YAML = SKILL_DIR / "agents" / "openai.yaml"
RENDERER = SKILL_DIR / "scripts" / "native_subtitle_stitch.py"
README = ROOT / "README.md"
PLUGIN = ROOT / ".codex-plugin" / "plugin.json"
EXPECTED_NAME = "native-subtitle-quote-image"
EXPECTED_VERSION = "1.1.0"


def main():
    errors = []
    required = [
        ROOT / "LICENSE",
        README,
        PLUGIN,
        SKILL_FILE,
        OPENAI_YAML,
        SKILL_DIR / "requirements.txt",
        RENDERER,
        ROOT / ".github" / "workflows" / "validate.yml",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"缺少文件: {path.relative_to(ROOT)}")

    try:
        plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"plugin.json 无法解析: {exc}")
        plugin = {}
    if plugin.get("name") != EXPECTED_NAME:
        errors.append("plugin.json name 与 Skill 目录不一致")
    if plugin.get("version") != EXPECTED_VERSION:
        errors.append(
            f"plugin.json version 应为 {EXPECTED_VERSION}，实际为 {plugin.get('version')}"
        )
    if plugin.get("skills") != "./skills/":
        errors.append("plugin.json skills 必须指向 ./skills/")

    skill_text = SKILL_FILE.read_text(encoding="utf-8") if SKILL_FILE.is_file() else ""
    frontmatter = re.match(r"\A---\n(.*?)\n---\n", skill_text, flags=re.DOTALL)
    if not frontmatter:
        errors.append("SKILL.md 缺少有效 YAML frontmatter")
    else:
        header = frontmatter.group(1)
        if not re.search(rf"^name:\s*{re.escape(EXPECTED_NAME)}\s*$", header, re.MULTILINE):
            errors.append("SKILL.md name 不正确")
        if not re.search(r"^description:\s*\S.+$", header, re.MULTILINE):
            errors.append("SKILL.md description 不能为空")

    yaml_text = OPENAI_YAML.read_text(encoding="utf-8") if OPENAI_YAML.is_file() else ""
    if f"${EXPECTED_NAME}" not in yaml_text:
        errors.append("agents/openai.yaml default_prompt 未引用当前 Skill")

    readme_text = README.read_text(encoding="utf-8") if README.is_file() else ""
    for source in re.findall(r'<img\s+[^>]*src="([^"]+)"', readme_text):
        if source.startswith(("http://", "https://")):
            continue
        if not (ROOT / source).is_file():
            errors.append(f"README 图片不存在: {source}")
    if "~/.codex/skills" not in readme_text:
        errors.append("README 缺少 Codex 默认 Skill 安装目录")

    if RENDERER.is_file():
        try:
            compile(RENDERER.read_text(encoding="utf-8"), str(RENDERER), "exec")
        except SyntaxError as exc:
            errors.append(f"渲染脚本语法错误: {exc}")

    public_text_files = [README, SKILL_FILE, OPENAI_YAML, RENDERER, PLUGIN]
    for path in public_text_files:
        if path.is_file() and "/Users/" in path.read_text(encoding="utf-8"):
            errors.append(f"包含本机绝对路径: {path.relative_to(ROOT)}")

    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Repository is valid: {EXPECTED_NAME} v{EXPECTED_VERSION}")


if __name__ == "__main__":
    main()
