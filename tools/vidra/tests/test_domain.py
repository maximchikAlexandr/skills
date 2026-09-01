from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from vidra.domain import (
    normalize_source,
    report_slug,
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

    def test_report_slug_is_safe_and_bounded(self):
        self.assertEqual(report_slug("  Практика: HTTP/3!  "), "практика-http-3")
        self.assertEqual(len(report_slug("a" * 100)), 48)
