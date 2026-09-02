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
            self.assertEqual(stored_report.name, f'{completed["report_hash"]}.html')
            self.assertIn(
                completed["report_hash"], stored_report.read_text(encoding="utf-8")
            )
            rendered = stored_report.read_text(encoding="utf-8")
            self.assertIn('data-copy-report-id', rendered)
            self.assertLess(rendered.index("data-vidra-report-copy"), rendered.index("</body>"))

            next_transcript = root / "next.vtt"
            next_transcript.write_text("new verified transcript " * 20, encoding="utf-8")
            prepared = self.run_vidra(
                root / "home",
                "report",
                "add-video",
                completed["report_hash"],
                "https://youtu.be/next456",
                "--title",
                "Next video",
            )
            self.assertEqual(prepared["result"], "addition_prepared")
            self.assertTrue(Path(prepared["manifest"]).is_file())
            updated_report = root / "updated.html"
            updated_report.write_text(
                '<!doctype html><body><a href="../">Все видео</a>'
                '<iframe src="https://www.youtube.com/embed/flow123"></iframe>'
                '<iframe src="https://www.youtube.com/embed/next456"></iframe>'
                "Updated</body>",
                encoding="utf-8",
            )
            attached = self.run_vidra(
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
            self.assertEqual(attached["result"], "attached")
            self.assertIn("Updated", stored_report.read_text(encoding="utf-8"))
            with sqlite3.connect(root / "home" / "vidra.sqlite3") as connection:
                run_status = connection.execute(
                    "SELECT status FROM runs WHERE video_id=? ORDER BY id DESC LIMIT 1",
                    (prepared["video_id"],),
                ).fetchone()[0]
            self.assertEqual(run_status, "analyzed")
            additions = self.run_vidra(
                root / "home",
                "report",
                "additions",
                completed["report_hash"],
                "--json",
            )
            self.assertEqual([item["title"] for item in additions], ["Next video"])
            validated = self.run_vidra(
                root / "home", "report", "validate", completed["report_hash"]
            )
            self.assertEqual(validated["result"], "valid")

            moved = self.run_vidra(
                root / "home",
                "report",
                "move",
                completed["report_hash"],
                "ai/code-review",
            )
            stored_report = root / "home" / moved["report_url"]
            self.assertTrue(stored_report.is_file())
            categories = self.run_vidra(root / "home", "category", "tree", "--json")
            self.assertEqual(categories, [{"category": "ai/code-review", "reports": 1}])

            removed = self.run_vidra(
                root / "home", "queue", "remove", video_id, "--yes"
            )
            self.assertTrue(removed["files_preserved"])
            self.assertTrue(stored_report.is_file())
