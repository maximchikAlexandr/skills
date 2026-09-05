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
            queued = self.run_vidra(
                root / "home", "project", "queue-add", "deeplethe/utopia"
            )
            self.assertEqual(queued["project"]["source_type"], "github_project")
            self.run_vidra(
                root / "home",
                "project",
                "queue-begin",
                "deeplethe/utopia",
                "--user-approved",
            )
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
                "--category",
                "knowledge/platforms",
            )
            project = registered["project"]
            self.assertEqual(project["repository_key"], "deeplethe/utopia")
            self.assertRegex(project["report_hash"], r"^[0-9a-f]{12}$")
            self.assertEqual(project["category"], "knowledge/platforms")
            stored = root / "home" / project["report_url"]
            self.assertTrue(stored.is_file())
            self.assertIn("Все проекты", stored.read_text(encoding="utf-8"))
            self.assertIn(
                'href="../../../#projects"', stored.read_text(encoding="utf-8")
            )
            moved = self.run_vidra(
                root / "home",
                "project",
                "move",
                project["report_hash"],
                "knowledge/tools",
            )
            moved_report = root / "home" / moved["report_url"]
            self.assertTrue(moved_report.is_file())
            self.assertFalse(stored.exists())
            listed = self.run_vidra(root / "home", "project", "list", "--json")
            self.assertEqual(
                [item["report_hash"] for item in listed], [project["report_hash"]]
            )
            self.assertEqual(listed[0]["category"], "knowledge/tools")
            queue = self.run_vidra(root / "home", "project", "queue-list", "--json")
            self.assertEqual(queue, [])

            replacement = root / "utopia-v2.html"
            replacement.write_text(
                "<!doctype html><html><body>Updated deep dive</body></html>",
                encoding="utf-8",
            )
            replaced = self.run_vidra(
                root / "home", "project", "register", "deeplethe/utopia",
                "--report-file", str(replacement), "--title", "Utopia v2",
                "--revision", "deadbeef", "--category", "knowledge/tools", "--replace",
            )["project"]
            self.assertFalse(moved_report.exists())
            self.assertTrue((root / "home" / replaced["report_url"]).is_file())
            with sqlite3.connect(root / "home" / "vidra.sqlite3") as connection:
                display_name = connection.execute(
                    "SELECT display_name FROM project_registry WHERE repository_key=?",
                    ("deeplethe/utopia",),
                ).fetchone()[0]
            self.assertEqual(display_name, "Utopia v2")

    def test_multiple_skill_reports_share_project_catalog_without_colliding(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            env = {**os.environ, "VIDRA_HOME": str(home)}
            subprocess.run(
                [sys.executable, "-m", "vidra.cli", "init"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            with sqlite3.connect(home / "vidra.sqlite3") as connection:
                connection.execute(
                    "INSERT INTO skill_candidates(repository_key,skill_path,source_url,revision,stars,category,status,discovered_at) VALUES(?,?,?,?,?,?,?,?)",
                    ("owner/toolkit", "skills/debugging/SKILL.md", "https://github.com/owner/toolkit", "abc123", 200, "code-review", "discovered", "2026-09-05T00:00:00+00:00"),
                )
            hashes = []
            for name in ("debugging", "review"):
                report = root / f"{name}.html"
                report.write_text(
                    "<!doctype html><html><body>Skill report</body></html>",
                    encoding="utf-8",
                )
                registered = self.run_vidra(
                    root / "home", "project", "register-skill", "owner/toolkit",
                    "--skill-path", f"skills/{name}/SKILL.md",
                    "--report-file", str(report), "--title", name,
                    "--revision", "abc123", "--category", "ai/skills",
                )["project"]
                hashes.append(registered["report_hash"])
                self.assertEqual(registered["source_type"], "github_skill")
                self.assertEqual(registered["skill_path"], f"skills/{name}/SKILL.md")
                self.assertTrue((root / "home" / registered["report_url"]).is_file())
            self.assertEqual(len(set(hashes)), 2)
            listed = self.run_vidra(root / "home", "project", "list", "--json")
            self.assertEqual(len(listed), 2)
            seen = self.run_vidra(root / "home", "project", "seen", "owner/toolkit")
            self.assertTrue(seen["seen"])
            with sqlite3.connect(home / "vidra.sqlite3") as connection:
                status = connection.execute(
                    "SELECT status FROM skill_candidates WHERE repository_key=? AND skill_path=?",
                    ("owner/toolkit", "skills/debugging/SKILL.md"),
                ).fetchone()[0]
            self.assertEqual(status, "analyzed")

            old_report = home / listed[0]["report_url"]
            replacement = root / "replacement.html"
            replacement.write_text(
                "<!doctype html><html><body>Replacement</body></html>",
                encoding="utf-8",
            )
            replaced = self.run_vidra(
                home, "project", "register-skill", "owner/toolkit",
                "--skill-path", listed[0]["skill_path"], "--report-file", str(replacement),
                "--title", "replacement", "--revision", "def456",
                "--category", "ai/skills", "--replace",
            )["project"]
            self.assertFalse(old_report.exists())
            self.assertTrue((home / replaced["report_url"]).is_file())
