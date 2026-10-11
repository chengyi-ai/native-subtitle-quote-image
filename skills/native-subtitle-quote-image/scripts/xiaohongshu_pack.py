#!/usr/bin/env python3
"""Validate and export an offline Xiaohongshu editorial package; never publish."""
import argparse
import csv
import json
import math
from pathlib import Path


def validate(pack, base):
    """Return editorial gaps; reject malformed or internally inconsistent input."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def text(value, label):
        require(isinstance(value, str) and bool(value.strip()), f'{label}: non-empty text required')

    require(isinstance(pack, dict), 'package must be an object')
    require(pack.get('schema_version') == 1, 'schema_version must be 1')
    require(pack.get('status') in ('draft', 'ready'), 'status must be draft or ready')
    text(pack.get('id'), 'id')
    require(isinstance(pack.get('demonstration'), bool), 'demonstration must be boolean')
    gaps = ['Demonstration only: fictional source, not for publication.'] if pack['demonstration'] else []
    profile = pack.get('profile')
    require(isinstance(profile, dict), 'profile must be an object')
    text(profile.get('positioning'), 'positioning')
    require(isinstance(profile.get('audience'), list) and profile['audience'], 'audience required')
    for item in profile['audience']:
        text(item, 'audience item')
    limits = profile.get('editorial_limits', {})
    require(isinstance(limits, dict), 'editorial_limits must be an object')
    for key, default in [('title_chars', 20), ('body_chars', 1000)]:
        value = limits.get(key, default)
        require(type(value) is int and value > 0, f'{key}: positive integer required')
    evidence = pack.get('evidence')
    require(isinstance(evidence, list) and evidence, 'evidence list required')
    ids = {}
    for item in evidence:
        require(isinstance(item, dict), 'evidence item must be an object')
        for field in ('id', 'source_title', 'source_url', 'speaker', 'original_text', 'text'):
            text(item.get(field), f'evidence.{field}')
        require(item['id'] not in ids, 'duplicate evidence id')
        ids[item['id']] = item
        require(item.get('kind') in ('verbatim', 'translation', 'summary'), 'invalid evidence kind')
        start, end = item.get('start_seconds'), item.get('end_seconds')
        require(all(type(t) in (int, float) and math.isfinite(t) for t in (start, end)), 'finite numeric timestamps required')
        require(0 <= start < end, 'invalid evidence time range')
        if item['kind'] == 'verbatim':
            require(item['text'] == item['original_text'], 'verbatim must equal original_text')
        require(type(item.get('verified')) is bool, 'verified must be boolean')
        require(item.get('reuse_status') in ('confirmed', 'unknown', 'denied'), 'invalid reuse_status')
        if item['reuse_status'] == 'confirmed':
            text(item.get('reuse_basis'), 'reuse_basis')
        if not item['verified']:
            gaps.append(f"Evidence {item['id']}: source/speaker/text not verified.")
        if item['reuse_status'] != 'confirmed':
            gaps.append(f"Evidence {item['id']}: reuse {item['reuse_status']}.")
    post = pack.get('post')
    require(isinstance(post, dict), 'post required')
    for field in ('cover_text', 'body', 'interpretation', 'action'):
        text(post.get(field), f'post.{field}')
    titles = post.get('titles')
    require(isinstance(titles, list) and len(titles) == 3, 'exactly three titles required')
    for title in titles:
        text(title, 'title')
        require(len(title) <= limits.get('title_chars', 20), 'title exceeds editorial limit')
    selected = post.get('selected_title')
    require(type(selected) is int and 0 <= selected < 3, 'invalid selected_title index')
    require(len(post['body']) <= limits.get('body_chars', 1000), 'body exceeds editorial limit')
    require(isinstance(post.get('tags'), list) and 3 <= len(post['tags']) <= 5, 'three to five tags required')
    for tag in post['tags']:
        text(tag, 'tag')
        require(not any(c.isspace() for c in tag) and not tag.startswith('#'), 'tags must omit # and whitespace')
    refs = post.get('evidence_ids')
    require(isinstance(refs, list) and refs and all(isinstance(ref, str) and ref in ids for ref in refs), 'unknown or missing evidence reference')
    for ref in refs:
        require(ids[ref]['text'] in post['body'], f'body missing evidence text: {ref}')
    strategy = pack.get('strategy')
    require(isinstance(strategy, dict), 'strategy required')
    require(strategy.get('goal') in ('discovery', 'trust', 'conversion'), 'invalid content goal')
    for field in ('pain_point', 'cta', 'success_metric', 'commercial_hypothesis'):
        text(strategy.get(field), f'strategy.{field}')
    scores = strategy.get('scores')
    weights = {'audience_fit': .30, 'pain_specificity': .25, 'action_value': .25, 'commercial_fit': .20}
    text(strategy.get('score_rationale'), 'score_rationale')
    score = None
    if scores is None:
        require(pack['status'] == 'draft', 'ready requires editorial scores')
    else:
        require(isinstance(scores, dict) and set(scores) == set(weights), 'four editorial scores required')
        require(not pack['demonstration'] and all(e['verified'] and e['reuse_status'] == 'confirmed' for e in evidence), 'score only verified reusable evidence')
        for name, value in scores.items():
            require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 5, f'invalid score: {name}')
        score = round(sum(scores[key] * weight * 20 for key, weight in weights.items()), 1)
    offer = strategy.get('offer')
    if strategy['goal'] == 'conversion':
        require(isinstance(offer, dict) and offer.get('confirmed_available') is True, 'conversion requires available offer')
        for field in ('name', 'deliverable', 'entry'):
            text(offer.get(field), f'offer.{field}')
    assets = pack.get('assets')
    require(isinstance(assets, list), 'assets must be a list')
    if not assets:
        gaps.append('No rendered images delivered.')
    for asset in assets:
        require(isinstance(asset, dict), 'asset must be an object')
        text(asset.get('path'), 'asset.path')
        require(asset.get('mode') in ('native', 'script', 'original-card'), 'invalid image mode')
        require(type(asset.get('visual_checked')) is bool, 'visual_checked must be boolean')
        require(isinstance(asset.get('evidence_ids'), list), 'asset evidence_ids required')
        require(all(isinstance(ref, str) and ref in ids for ref in asset['evidence_ids']), 'unknown image evidence')
        if asset['mode'] in ('native', 'script'):
            require(bool(asset['evidence_ids']), 'subtitle image must reference evidence')
        if not (base / asset['path']).is_file():
            gaps.append(f"Missing image: {asset['path']}")
        if not asset['visual_checked']:
            gaps.append(f"Visual QA incomplete: {asset['path']}")
    if pack['status'] == 'ready':
        require(not gaps, 'ready blocked: ' + '; '.join(gaps))
    return gaps, score


def csv_safe(value):
    """Treat source strings as text when opening exports in spreadsheet apps."""
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def export(pack, source, out):
    gaps, score = validate(pack, source.parent)
    # A new directory prevents partial overwrite of prior reviewed packages.
    out.mkdir(parents=True, exist_ok=False)
    post = pack['post']
    title = post['titles'][post['selected_title']]
    sources = '\n'.join(f"- {e['source_title']} | {e['speaker']} | {e['start_seconds']}–{e['end_seconds']}s | {e['kind']} | {e['source_url']}" for e in pack['evidence'])
    body = f"# {title}\n\n状态：{pack['status']}（未发布）\n\n{post['body']}\n\n## 我的解读\n\n{post['interpretation']}\n\n## 一步行动\n\n{post['action']}\n\n{pack['strategy']['cta']}\n\n" + ' '.join('#' + t for t in post['tags'])
    body += f"\n\n## 来源与文字性质\n\n{sources}\n\n封面编辑标题：{post['cover_text']}（不作为人物引语）\n\n其他标题候选：\n" + '\n'.join('- ' + t for t in post['titles']) + '\n'
    (out / 'post.md').write_text(body, encoding='utf-8')
    fields = ['id', 'source_title', 'source_url', 'speaker', 'start_seconds', 'end_seconds', 'kind', 'original_text', 'text', 'verified', 'reuse_status', 'reuse_basis']
    with (out / 'evidence.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in pack['evidence']:
            writer.writerow({key: csv_safe(item.get(key, '')) for key in fields})
    strategy = pack['strategy']
    (out / 'strategy.md').write_text(f"# 内容与商业设计\n\n定位：{pack['profile']['positioning']}\n\n目的：{strategy['goal']}\n\n痛点：{strategy['pain_point']}\n\n编辑评分：{str(score) + '/100' if score is not None else '未评分'}（非传播概率）\n\n评分依据：{strategy['score_rationale']}\n\n商业假设：{strategy['commercial_hypothesis']}\n\nCTA：{strategy['cta']}\n\n主要指标：{strategy['success_metric']}\n\n产品：{json.dumps(strategy.get('offer'), ensure_ascii=False)}\n", encoding='utf-8')
    review = f"# 发布前检查\n\n状态：{pack['status']}；脚本只检查结构和显式状态，不验证来源真假，不自动发布。\n\n"
    review += '\n'.join('- ' + gap for gap in gaps) if gaps else '结构检查通过；仍须以实际视频回看和逐张视觉 QA 为依据。'
    review += '\n\n## 图片清单\n\n' + '\n'.join(f"- {a['path']} | {a['mode']} | visual_checked={a['visual_checked']}" for a in pack['assets']) + '\n'
    (out / 'review.md').write_text(review, encoding='utf-8')
    with (out / 'metrics.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['post_id', 'observed_at', 'window', 'impressions', 'reads', 'saves', 'new_followers', 'qualified_needs', 'orders', 'revenue', 'production_minutes', 'attribution_basis', 'notes'])
        for window in ('24h', '7d'):
            writer.writerow([csv_safe(pack['id']), '', window] + [''] * 10)
    (out / 'pack.json').write_text(json.dumps(pack, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return gaps, score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if not args.check_only and args.out_dir is None:
        parser.error('--out-dir required unless --check-only')
    try:
        pack = json.loads(args.input.read_text(encoding='utf-8'))
        gaps, score = validate(pack, args.input.parent) if args.check_only else export(pack, args.input, args.out_dir)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Package rejected: {exc}\n')
    print(f"{pack['status']}: editorial score {score if score is not None else 'unscored'}; {len(gaps)} review gaps; not published")
    for gap in gaps:
        print('- ' + gap)


if __name__ == '__main__':
    main()
