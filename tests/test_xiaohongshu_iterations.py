import ast
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
SCRIPT = SKILL / 'scripts' / 'xiaohongshu_iterations.py'
spec = importlib.util.spec_from_file_location('iterations', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class IterationTests(unittest.TestCase):
    def setUp(self):
        self.history = json.loads((SKILL / 'assets' / 'xiaohongshu-iterations.example.json').read_text(encoding='utf-8'))
        self.revision = copy.deepcopy(self.history['revisions'][0]['revision'])

    def test_full_example_matches_report_and_scores(self):
        module.validate_history(self.history)
        self.assertEqual([e['total'] for e in self.history['revisions']], [51, 76, 82])
        self.assertEqual(module.report(self.history), (ROOT / 'examples' / 'xiaohongshu-iterations.md').read_text(encoding='utf-8'))
        for entry in self.history['revisions']:
            self.assertIn(entry['revision']['post']['body'], module.report(self.history))

    def test_append_does_not_require_score_increase(self):
        history = module.append(None, self.revision)
        next_revision = copy.deepcopy(self.revision)
        next_revision['version'] = 2
        next_revision['scores']['actionability'] = 1
        module.append(history, next_revision)
        self.assertIn('-4.0', module.report(history))
        self.assertEqual(history['revisions'][0]['revision']['post']['body'], self.revision['post']['body'])

    def test_reject_duplicate_skipped_and_changed_audience(self):
        history = module.append(None, self.revision)
        for version, audience in [(1, self.revision['audience']), (3, self.revision['audience']), (2, 'different')]:
            revision = copy.deepcopy(self.revision)
            revision.update(version=version, audience=audience)
            with self.assertRaises(ValueError):
                module.append(copy.deepcopy(history), revision)

    def test_tampered_snapshot_and_scores_rejected(self):
        for field, value in [('total', 99), ('previous_sha256', 'wrong')]:
            history = copy.deepcopy(self.history)
            history['revisions'][1][field] = value
            with self.assertRaises(ValueError):
                module.validate_history(history)
        self.history['revisions'][0]['revision']['post']['body'] = 'rewritten'
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            module.validate_history(self.history)

    def test_fixed_rubric_and_complete_copy(self):
        for key in ('post', 'scores', 'score_reasons', 'improvements'):
            revision = copy.deepcopy(self.revision)
            del revision[key]
            with self.assertRaises(ValueError):
                module.validate_revision(revision)
        self.history['weights']['credibility'] = 0
        with self.assertRaises(ValueError):
            module.validate_history(self.history)

    def test_scores_are_finite_numbers(self):
        for score in (True, float('nan'), 6, -1):
            revision = copy.deepcopy(self.revision)
            revision['scores']['credibility'] = score
            with self.assertRaises(ValueError):
                module.validate_revision(revision)

    def test_cli_append_and_rejection_leave_previous_file_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            revision = base / 'revision.json'
            history = base / 'history.json'
            report = base / 'report.md'
            revision.write_text(json.dumps(self.revision), encoding='utf-8')
            command = [sys.executable, str(SCRIPT), '--history', str(history), '--revision', str(revision), '--report', str(report)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            original = history.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            self.assertEqual(history.read_bytes(), original)
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), '--history', str(history), '--report', str(history)], capture_output=True).returncode, 1)

    def test_python_310_syntax_compatibility(self):
        for script in ('xiaohongshu_pack.py', 'xiaohongshu_iterations.py'):
            ast.parse((SKILL / 'scripts' / script).read_text(encoding='utf-8'), feature_version=(3, 10))


if __name__ == '__main__':
    unittest.main()
