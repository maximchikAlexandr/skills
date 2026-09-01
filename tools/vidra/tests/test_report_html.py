from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from vidra.cli import with_report_identity


class ReportHtmlTests(TestCase):
    def test_identity_follows_library_link_and_is_idempotent(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "report.html"
            source.write_text(
                '<html><body><header><a href="../">← Все видео</a><strong>Title</strong></header></body></html>',
                encoding="utf-8",
            )
            first = with_report_identity(source, "abc123def456").decode()
            source.write_text(first, encoding="utf-8")
            second = with_report_identity(source, "abc123def456").decode()

        self.assertEqual(second.count('data-vidra-report-id="true"'), 1)
        self.assertEqual(second.count('data-vidra-report-copy="true"'), 1)
        self.assertLess(second.index("Все видео"), second.index("ID отчёта"))
        self.assertLess(second.index("ID отчёта"), second.index("abc123def456"))
        self.assertIn('aria-label="Скопировать ID отчёта"', second)

    def test_copy_script_is_allowed_by_self_contained_report_csp(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "report.html"
            source.write_text(
                "<html><head><meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\"></head>"
                '<body><a href="../">All videos</a></body></html>',
                encoding="utf-8",
            )
            rendered = with_report_identity(source, "abc123def456").decode()

        self.assertIn("script-src 'unsafe-inline'", rendered)
