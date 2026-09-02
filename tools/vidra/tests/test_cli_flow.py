import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

SOURCE = "https://www.youtube.com/watch?v=flow123"


class CliFlowTests(TestCase):
    def run_vidra(self, home: Path, *arguments: str):
        env = {**os.environ, "VIDRA_HOME": str(home)}
        result = subprocess.run(
            [sys.executable, "-m", "vidra.cli", *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_queue_to_report_and_record_removal_preserves_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            transcript = root / "transcript.txt"
            transcript.write_text("verified transcript " * 20, encoding="utf-8")
            report = root / "report.html"
            report.write_text(
                "<!doctype html><title>Report</title><body>Report</body>",
                encoding="utf-8",
            )
            queued = self.run_vidra(root / "home", "queue", "add", SOURCE)
            video_id = str(queued["video"]["id"])
            self.run_vidra(
                root / "home", "analyze", "begin", video_id, "--user-approved"
            )
            completed = self.run_vidra(
                root / "home",
                "analyze",
                "complete",
                video_id,
                "--transcript-file",
                str(transcript),
                "--report-file",
                str(report),
                "--title",
                "Flow report",
            )
            stored_report = root / "home" / completed["report_url"]
            self.assertTrue(stored_report.is_file())
            self.assertEqual(stored_report.name, f"{completed['report_hash']}.html")
            rendered = stored_report.read_text(encoding="utf-8")
            self.assertIn(completed["report_hash"], rendered)
            self.assertIn("data-copy-report-id", rendered)

            next_transcript = root / "next.vtt"
            next_transcript.write_text(
                "new verified transcript " * 20, encoding="utf-8"
            )
            prepared = self.run_vidra(
                root / "home",
                "report",
                "add-video",
                completed["report_hash"],
                "https://youtu.be/next456",
                "--title",
                "Next video",
            )
            updated_report = root / "updated.html"
            updated_report.write_text(
                '<!doctype html><body><a href="../">Все видео</a><iframe src="https://www.youtube.com/embed/flow123"></iframe><iframe src="https://www.youtube.com/embed/next456"></iframe>Updated</body>',
                encoding="utf-8",
            )
            self.run_vidra(
                root / "home",
                "report",
                "add",
                completed["report_hash"],
                "https://youtu.be/next456",
                "--transcript-file",
                str(next_transcript),
                "--report-file",
                str(updated_report),
            )
            with sqlite3.connect(root / "home" / "vidra.sqlite3") as connection:
                status = connection.execute(
                    "SELECT status FROM runs WHERE video_id=? ORDER BY id DESC LIMIT 1",
                    (prepared["video_id"],),
                ).fetchone()[0]
            self.assertEqual(status, "analyzed")

            moved = self.run_vidra(
                root / "home",
                "report",
                "move",
                completed["report_hash"],
                "ai/code-review",
            )
            stored_report = root / "home" / moved["report_url"]
            self.assertTrue(stored_report.is_file())
            self.assertIn('href="../../../"', stored_report.read_text(encoding="utf-8"))
            removed = self.run_vidra(
                root / "home", "queue", "remove", video_id, "--yes"
            )
            self.assertTrue(removed["files_preserved"])
            self.assertTrue(stored_report.is_file())

    def test_project_report_registration_uses_hash_filename(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "utopia.html"
            report.write_text(
                "<!doctype html><html><body>Deep dive</body></html>", encoding="utf-8"
            )
            registered = self.run_vidra(
                root / "home",
                "project",
                "register",
                "deeplethe/utopia",
                "--report-file",
                str(report),
                "--title",
                "Utopia",
                "--revision",
                "0f3ff5af",
                "--summary",
                "Knowledge platform",
                "--stars",
                "1900",
            )
            project = registered["project"]
            self.assertEqual(project["repository_key"], "deeplethe/utopia")
            self.assertRegex(project["report_hash"], r"^[0-9a-f]{12}$")
            stored = root / "home" / project["report_url"]
            self.assertTrue(stored.is_file())
            self.assertIn("Все проекты", stored.read_text(encoding="utf-8"))
            listed = self.run_vidra(root / "home", "project", "list", "--json")
            self.assertEqual(
                [item["report_hash"] for item in listed], [project["report_hash"]]
            )
