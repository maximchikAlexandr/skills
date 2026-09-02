from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from vidra.domain import (
    normalize_category,
    normalize_source,
    report_hash,
    report_validation_errors,
    require_transition,
)


class DomainTests(TestCase):
    def test_youtube_variants_have_one_identity(self):
        variants = (
            "https://www.youtube.com/watch?v=abc123&t=10",
            "https://youtu.be/abc123",
            "https://youtube.com/embed/abc123",
        )
        self.assertEqual(
            {normalize_source(value).key for value in variants}, {"youtube:abc123"}
        )

    def test_local_source_is_resolved_and_stable(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "video.mp4"
            source = normalize_source(str(path))
            self.assertEqual(source.url, str(path.resolve()))
            self.assertTrue(source.key.startswith("source:"))

    def test_only_explicit_lifecycle_transitions_are_allowed(self):
        require_transition("queued", "analyzing")
        require_transition("analyzing", "failed")
        with self.assertRaisesRegex(ValueError, "invalid video transition"):
            require_transition("queued", "analyzed")

    def test_report_hash_is_short_and_stable(self):
        first = report_hash(b"html", ("youtube:b", "youtube:a"), "stamp")
        second = report_hash(b"html", ("youtube:a", "youtube:b"), "stamp")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)

    def test_category_is_a_safe_relative_path(self):
        self.assertEqual(normalize_category("AI / Code Review"), "ai/code-review")
        with self.assertRaisesRegex(ValueError, "invalid category"):
            normalize_category("ai/../review")

    def test_report_validation_is_pure_and_checks_every_source(self):
        html = (
            '<a href="../">Все видео</a>'
            '<iframe src="https://www.youtube.com/embed/a"></iframe>'
            '<a class="ts">00:10</a><a class="yt">▶</a>'
            '<span data-vidra-report-id="true">hash123</span>'
        )
        self.assertEqual(report_validation_errors(html, ("a",), "hash123"), ())
        self.assertEqual(
            report_validation_errors(html, ("a", "b"), "hash123"),
            ("missing_player:b",),
        )
