#!/usr/bin/env python3
"""Append complete editorial revisions and derive comparable scores, offline."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

RUBRIC = 'xhs-editorial-v1'
WEIGHTS = {'audience_fit': 20, 'specificity': 20, 'structure': 15,
           'actionability': 20, 'credibility': 15, 'commercial_fit': 10}
LABELS = dict(zip(WEIGHTS, ['受众匹配', '问题具体', '结构可读', '行动价值', '表达可信', '商业承接']))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def text(value, name):
    require(isinstance(value, str) and bool(value.strip()), name + ': non-empty text required')


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_revision(revision):
    require(isinstance(revision, dict), 'revision must be an object')
    for key in ('topic', 'audience', 'skill_version', 'evidence_note', 'remaining_gaps', 'reviewer'):
        text(revision.get(key), key)
    require(type(revision.get('version')) is int and revision['version'] > 0, 'positive integer version required')
    require(revision.get('rubric_id') == RUBRIC, 'rubric mismatch: start a separate series for a new rubric')
    require(revision.get('status') in ('draft', 'ready'), 'invalid status')
    post = revision.get('post')
    require(isinstance(post, dict), 'complete post required')
    for key in ('title', 'cover_text', 'body', 'cta'):
        text(post.get(key), 'post.' + key)
    require(isinstance(post.get('tags'), list) and 3 <= len(post['tags']) <= 5, 'three to five tags required')
    for tag in post['tags']:
        text(tag, 'tag')
        require(not tag.startswith('#') and not any(c.isspace() for c in tag), 'invalid tag')
    pages = post.get('pages')
    require(isinstance(pages, list) and len(pages) >= 2, 'complete page-by-page copy required')
    for page in pages:
        require(isinstance(page, dict), 'page must be an object')
        text(page.get('heading'), 'page.heading')
        text(page.get('text'), 'page.text')
    changes = revision.get('improvements')
    require(isinstance(changes, list) and changes, 'improvement log required (baseline may describe initial state)')
    for change in changes:
        text(change, 'improvement')
    scores = revision.get('scores')
    reasons = revision.get('score_reasons')
    require(isinstance(scores, dict) and set(scores) == set(WEIGHTS), 'six scores required')
    require(isinstance(reasons, dict) and set(reasons) == set(WEIGHTS), 'six score reasons required')
    for key, score in scores.items():
        require(type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 5, 'invalid score: ' + key)
        text(reasons[key], 'score reason ' + key)
    # This is an editorial assessment of the supplied copy, never a claim of source or image verification.
    return round(sum(scores[k] * weight / 5 for k, weight in WEIGHTS.items()), 1)


def validate_history(history):
    require(isinstance(history, dict) and history.get('schema_version') == 1, 'invalid history schema')
    require(history.get('rubric_id') == RUBRIC and history.get('weights') == WEIGHTS, 'rubric weights changed')
    require(isinstance(history.get('revisions'), list), 'revisions must be a list')
    previous = None
    for index, entry in enumerate(history['revisions'], 1):
        require(isinstance(entry, dict), 'invalid entry')
        revision = entry.get('revision')
        total = validate_revision(revision)
        require(revision['version'] == index, 'versions must be consecutive')
        require(revision['topic'] == history['topic'] and revision['audience'] == history['audience'], 'topic/audience changed: start a separate series')
        payload = {'revision': revision, 'previous_sha256': previous, 'total': total}
        require(entry.get('sha256') == digest(payload), 'snapshot changed: hash mismatch')
        require(entry.get('total') == total and entry.get('previous_sha256') == previous, 'broken score/hash chain')
        previous = entry['sha256']
    return previous


def append(history, revision):
    total = validate_revision(revision)
    if history is None:
        history = {'schema_version': 1, 'rubric_id': RUBRIC, 'weights': WEIGHTS,
                   'topic': revision['topic'], 'audience': revision['audience'], 'revisions': []}
    previous = validate_history(history)
    require(revision['version'] == len(history['revisions']) + 1, 'append only: next consecutive version required')
    require(revision['topic'] == history['topic'] and revision['audience'] == history['audience'], 'topic/audience mismatch')
    payload = {'revision': revision, 'previous_sha256': previous, 'total': total}
    history['revisions'].append(dict(payload, sha256=digest(payload)))
    return history


def report(history):
    validate_history(history)
    lines = ['# 小红书完整推文迭代记录', '', '主题：' + history['topic'], '', '受众：' + history['audience'], '',
             '评分口径：' + RUBRIC + '。固定六项权重，逐项 0–5 分。总分为加权和。', '',
             '分数是编辑自评，不代表阅读、涨粉、转化效果；不替代来源或图片核验。允许持平或下降。', '',
             '| 版本 | Skill 版本 | 总分 | 较上版 | 优化点 |', '| --- | --- | ---: | ---: | --- |']
    previous_total = None
    for entry in history['revisions']:
        r = entry['revision']
        delta = '—' if previous_total is None else f"{entry['total'] - previous_total:+.1f}"
        summary = '；'.join(r['improvements']).replace('|', '\\|').replace('\n', ' ')
        lines.append(f"| V{r['version']} | {r['skill_version']} | {entry['total']:.1f} | {delta} | {summary} |")
        previous_total = entry['total']
    previous_scores = None
    for entry in history['revisions']:
        r, p = entry['revision'], entry['revision']['post']
        lines += ['', f"## V{r['version']} — {p['title']}", '', f"状态：{r['status']}，未发布。评审者：{r['reviewer']}。", '',
                  '### 完整小红书正文', '', p['body'], '', p['cta'], '', ' '.join('#' + t for t in p['tags']), '',
                  '### 封面与每页图文文稿', '', '封面：' + p['cover_text'], '']
        for index, page in enumerate(p['pages'], 1):
            lines += [f"**第 {index} 页：{page['heading']}**", '', page['text'], '']
        lines += ['### 优化点', ''] + ['- ' + change for change in r['improvements']]
        lines += ['', '### 综合评分依据', '', '| 维度 | 权重 | 得分 / 5 | 较上版 | 依据 |', '| --- | ---: | ---: | ---: | --- |']
        for key, weight in WEIGHTS.items():
            delta = '—' if previous_scores is None else f"{r['scores'][key] - previous_scores[key]:+.1f}"
            reason = r['score_reasons'][key].replace('|', '\\|').replace('\n', ' ')
            lines.append(f"| {LABELS[key]} | {weight}% | {r['scores'][key]} | {delta} | {reason} |")
        lines += ['', f"**综合评分：{entry['total']:.1f}/100**", '', '来源与核验：' + r['evidence_note'], '',
                  '待优化 / 验证：' + r['remaining_gaps'], '', '快照 SHA-256：`' + entry['sha256'] + '`']
        previous_scores = r['scores']
    return '\n'.join(lines) + '\n'


def atomic_write(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(contents)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, required=True)
    parser.add_argument('--revision', type=Path, help='append the next complete revision')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        require(args.history.resolve() != args.report.resolve(), 'history and report paths must differ')
        history = json.loads(args.history.read_text(encoding='utf-8')) if args.history.exists() else None
        if args.revision:
            require(args.revision.resolve() not in (args.history.resolve(), args.report.resolve()), 'input paths must differ')
            revision = json.loads(args.revision.read_text(encoding='utf-8'))
            history = append(history, revision)
        require(history is not None, 'history missing: supply first revision')
        output = report(history)
        if args.revision:
            atomic_write(args.history, json.dumps(history, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        atomic_write(args.report, output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Iteration rejected: {exc}\n')
    print(f"{len(history['revisions'])} complete revisions; editorial scores only; not published")


if __name__ == '__main__':
    main()
