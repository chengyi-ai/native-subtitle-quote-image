import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'native-subtitle-quote-image'
SCRIPT = SKILL / 'scripts' / 'xiaohongshu_pack.py'
spec = importlib.util.spec_from_file_location('xiaohongshu_pack', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackTests(unittest.TestCase):
    def setUp(self):
        self.pack = json.loads((SKILL / 'assets' / 'xiaohongshu-pack.example.json').read_text(encoding='utf-8'))
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def ready(self):
        pack = copy.deepcopy(self.pack)
        pack.update(status='ready', demonstration=False)
        pack['strategy']['scores'] = {'audience_fit': 4, 'pain_specificity': 4, 'action_value': 5, 'commercial_fit': 2}
        pack['evidence'][0].update(verified=True, reuse_status='confirmed', reuse_basis='Self-produced test fixture')
        image = self.base / 'frame.jpg'
        image.write_bytes(b'test file; visual QA is an explicit human assertion')
        pack['assets'] = [{'path': 'frame.jpg', 'mode': 'native', 'visual_checked': True, 'evidence_ids': ['e1']}]
        return pack

    def test_draft_exposes_gaps_and_unknown_metrics(self):
        source = self.base / 'input.json'
        gaps, score = module.export(self.pack, source, self.base / 'out')
        self.assertIsNone(score)
        self.assertEqual(len(gaps), 4)
        self.assertIn('未发布', (self.base / 'out' / 'post.md').read_text(encoding='utf-8'))
        import csv
        with (self.base / 'out' / 'metrics.csv').open(encoding='utf-8-sig') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([r['window'] for r in rows], ['24h', '7d'])
        self.assertEqual(rows[0]['reads'], '')

    def test_ready_accepts_complete_assertions(self):
        self.assertEqual(module.validate(self.ready(), self.base)[0], [])

    def test_ready_rejects_draft_gaps(self):
        self.pack['status'] = 'ready'
        self.pack['strategy']['scores'] = {'audience_fit': 4, 'pain_specificity': 4, 'action_value': 5, 'commercial_fit': 2}
        with self.assertRaises(ValueError):
            module.validate(self.pack, self.base)

    def test_ready_rejects_missing_image(self):
        pack = self.ready()
        (self.base / 'frame.jpg').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing image'):
            module.validate(pack, self.base)

    def test_ready_rejects_visual_unchecked(self):
        pack = self.ready()
        pack['assets'][0]['visual_checked'] = False
        with self.assertRaisesRegex(ValueError, 'Visual QA'):
            module.validate(pack, self.base)

    def test_quote_cannot_silently_change(self):
        self.pack['evidence'][0]['text'] = 'Changed claim'
        with self.assertRaisesRegex(ValueError, 'verbatim'):
            module.validate(self.pack, self.base)

    def test_timestamps_reject_nan_bool_negative_and_reversal(self):
        for start, end in [(float('nan'), 45), (True, 45), (-1, 45), (45, 30)]:
            with self.subTest(start=start):
                pack = copy.deepcopy(self.pack)
                pack['evidence'][0].update(start_seconds=start, end_seconds=end)
                with self.assertRaises(ValueError):
                    module.validate(pack, self.base)

    def test_no_unavailable_offer_for_conversion(self):
        self.pack['strategy']['goal'] = 'conversion'
        with self.assertRaisesRegex(ValueError, 'available offer'):
            module.validate(self.pack, self.base)

    def test_unknown_evidence_and_missing_quote(self):
        for field, value in [('evidence_ids', ['unknown']), ('body', 'No source text')]:
            with self.subTest(field=field):
                pack = copy.deepcopy(self.pack)
                pack['post'][field] = value
                with self.assertRaises(ValueError):
                    module.validate(pack, self.base)

    def test_title_editorial_limit(self):
        self.pack['post']['titles'][0] = 'x' * 21
        with self.assertRaisesRegex(ValueError, 'title exceeds'):
            module.validate(self.pack, self.base)

    def test_output_never_overwrites(self):
        out = self.base / 'out'
        module.export(self.pack, self.base / 'input.json', out)
        with self.assertRaises(FileExistsError):
            module.export(self.pack, self.base / 'input.json', out)

    def test_formula_cells_are_text(self):
        self.assertEqual(module.csv_safe(' =CMD()'), "' =CMD()")
        self.assertEqual(module.csv_safe('ordinary'), 'ordinary')

    def test_cli_reports_invalid_json_and_draft(self):
        path = self.base / 'input.json'
        path.write_text('{', encoding='utf-8')
        result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--check-only'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 1)
        path.write_text(json.dumps(self.pack), encoding='utf-8')
        result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--check-only'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0)
        self.assertIn('not published', result.stdout)


if __name__ == '__main__':
    unittest.main()
