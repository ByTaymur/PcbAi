import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.evidence_output import report_path


class EvidenceOutputTests(unittest.TestCase):
    def test_audit_cannot_replace_published_report_and_escape_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='pcbai-evidence-') as temporary:
            root = Path(temporary)
            published = report_path(root, 'G1-result.json', publish=True)
            published.write_text('published', encoding='utf-8')
            audit = report_path(root, 'G1-result.json')
            audit.write_text('audit', encoding='utf-8')
            self.assertEqual(published.read_text(), 'published')
            for output in (published, root / '../escape.json', root / 'pcbai.py'):
                with self.assertRaises(ValueError):
                    report_path(root, output.name, output=output)
            self.assertEqual(report_path(root, published.name, publish=True, output=published), published)

    def test_audit_hardlink_cannot_mutate_published_evidence(self):
        with tempfile.TemporaryDirectory(prefix='pcbai-evidence-') as temporary:
            root = Path(temporary)
            published = report_path(root, 'S7-result.json', publish=True)
            published.write_text('published', encoding='utf-8')
            audit = report_path(root, 'S7-result.json')
            os.link(published, audit)
            with self.assertRaisesRegex(ValueError, 'Hardlink'):
                report_path(root, 'S7-result.json')
            self.assertEqual(published.read_text(), 'published')

    def test_engine_benchmark_markdown_link_rejected_before_motor_runs(self):
        from scripts import bench_engines
        with tempfile.TemporaryDirectory(prefix='pcbai-bench-evidence-') as temporary:
            root = Path(temporary)
            sentinel = root / 'sentinel.md'
            sentinel.write_text('KEEP', encoding='utf-8')
            json_path = report_path(root, 'engines.json')
            os.link(sentinel, json_path.with_suffix('.md'))
            with patch.object(bench_engines, 'ROOT', root), patch('sys.argv', ['bench', '--output', str(json_path)]), patch(
                    'scripts.bench_engines.find_kicad_cli') as discovery:
                with self.assertRaisesRegex(ValueError, 'Hardlink'):
                    bench_engines.main()
                discovery.assert_not_called()
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'KEEP')
