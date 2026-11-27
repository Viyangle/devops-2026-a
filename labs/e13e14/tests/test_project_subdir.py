from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "e11e12"))
import pipeline


class ProjectSubdirTests(unittest.TestCase):
    def test_snapshot_retains_original_commit_and_selected_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            logs = root / "logs"

            def git(*args):
                return pipeline.command(["git", *args], repo, logs / "setup.log")

            git("init", "-b", "main")
            project = repo / "fixtures" / "greeting"
            project.mkdir(parents=True)
            (project / "Makefile").write_text("app:\n\ttrue\n")
            (repo / "unrelated").mkdir()
            (repo / "unrelated" / "file").write_text("not part of the project\n")
            git("add", ".")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "Fixture")
            expected = git("rev-parse", "HEAD")
            checkout = root / "snapshot"
            request = {"project_subdir": "fixtures/greeting"}
            actual = pipeline.snapshot(repo, expected, checkout, logs, subdir=pipeline.project_subdir(request))
            selected = pipeline.project_directory(checkout, request)
            self.assertEqual(actual, expected)
            self.assertTrue((selected / "Makefile").is_file())
            self.assertFalse((checkout / "unrelated").exists())
            self.assertEqual(pipeline.command(["git", "rev-parse", "HEAD"], selected, logs / "head"), expected)

    def test_subdirectory_cannot_leave_checkout(self):
        for value in ("../outside", "/outside"):
            with self.subTest(value=value), self.assertRaisesRegex(pipeline.Failure, "inside the repository"):
                pipeline.project_subdir({"project_subdir": value})
