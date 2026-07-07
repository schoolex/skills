import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import diff_position
import review_common
import review_threads
import submit_review


SAMPLE_DIFF = """diff --git a/src/foo.py b/src/foo.py
index 1111111..2222222 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -10,3 +10,4 @@ def foo():
 line1
-line2
+line2a
 line3
@@ -20,2 +21,3 @@ def bar():
 old
+new
 context
diff --git a/src/old_name.py b/src/new_name.py
similarity index 90%
rename from src/old_name.py
rename to src/new_name.py
--- a/src/old_name.py
+++ b/src/new_name.py
@@ -1 +1 @@
-old
+new
diff --git a/src/deleted.py b/src/deleted.py
deleted file mode 100644
index 3333333..0000000 100644
--- a/src/deleted.py
+++ /dev/null
@@ -1 +0,0 @@
-gone
"""


class DiffPositionTests(unittest.TestCase):
    def test_parse_diff_counts_only_hunk_lines(self) -> None:
        entries = diff_position.parse_diff(SAMPLE_DIFF)
        foo_entries = [entry for entry in entries if entry.path == "src/foo.py"]
        self.assertEqual([entry.position for entry in foo_entries], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(foo_entries[0].old_line, 10)
        self.assertEqual(foo_entries[0].new_line, 10)
        self.assertEqual(foo_entries[1].old_line, 11)
        self.assertIsNone(foo_entries[1].new_line)
        self.assertIsNone(foo_entries[2].old_line)
        self.assertEqual(foo_entries[2].new_line, 11)
        self.assertEqual(foo_entries[5].new_line, 22)

    def test_find_matches_by_new_line(self) -> None:
        entries = diff_position.parse_diff(SAMPLE_DIFF)
        matches = diff_position.find_matches(
            entries,
            path="src/foo.py",
            needle=None,
            prefix="any",
            match_mode="exact",
            new_line=22,
            old_line=None,
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].position, 6)
        self.assertEqual(matches[0].side, "RIGHT")
        self.assertEqual(matches[0].text, "new")

    def test_find_matches_by_old_line_uses_left_side(self) -> None:
        entries = diff_position.parse_diff(SAMPLE_DIFF)
        matches = diff_position.find_matches(
            entries,
            path="src/deleted.py",
            needle=None,
            prefix="any",
            match_mode="exact",
            new_line=None,
            old_line=1,
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].side, "LEFT")
        self.assertEqual(matches[0].path, "src/deleted.py")

    def test_parse_diff_prefers_new_path_for_renames(self) -> None:
        entries = diff_position.parse_diff(SAMPLE_DIFF)
        renamed = [entry for entry in entries if entry.path == "src/new_name.py"]
        self.assertEqual(len(renamed), 2)


class SubmitReviewTests(unittest.TestCase):
    def write_comments(self, payload: list[dict]) -> str:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "comments.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_with_signoff_is_idempotent(self) -> None:
        signed = review_common.with_signoff("Hello", review_common.DEFAULT_SIGNOFF)
        self.assertEqual(
            review_common.with_signoff(signed, review_common.DEFAULT_SIGNOFF),
            signed,
        )

    def test_load_comments_accepts_line_position_file_and_reply_shapes(self) -> None:
        path = self.write_comments(
            [
                {"path": "src/z.py", "position": 9, "body": "Position note"},
                {"path": "src/a.py", "line": 42, "side": "right", "body": "Line note"},
                {"path": "src/b.py", "subject_type": "file", "body": "File note"},
                {"in_reply_to": 12345, "body": "Reply note"},
            ]
        )
        review_comments, replies = review_common.load_comments(
            path, review_common.DEFAULT_SIGNOFF
        )
        self.assertEqual(
            [comment["path"] for comment in review_comments],
            ["src/a.py", "src/b.py", "src/z.py"],
        )
        self.assertEqual(review_comments[0]["line"], 42)
        self.assertEqual(review_comments[0]["side"], "RIGHT")
        self.assertEqual(review_comments[1]["subject_type"], "file")
        self.assertEqual(review_comments[2]["position"], 9)
        self.assertEqual(replies[0]["in_reply_to"], 12345)
        self.assertTrue(
            str(review_comments[0]["body"]).endswith(review_common.DEFAULT_SIGNOFF)
        )

    def test_load_optional_comments_accepts_missing_file(self) -> None:
        self.assertEqual(
            review_common.load_optional_comments(None, review_common.DEFAULT_SIGNOFF),
            ([], []),
        )

    def test_load_comments_rejects_suggestion_with_position(self) -> None:
        path = self.write_comments(
            [
                {
                    "path": "src/a.py",
                    "position": 4,
                    "body": "```suggestion\nvalue = normalize(raw)\n```",
                }
            ]
        )
        with self.assertRaisesRegex(ValueError, "line/side instead of diff position"):
            review_common.load_comments(path, review_common.DEFAULT_SIGNOFF)

    def test_load_comments_rejects_left_side_suggestions(self) -> None:
        path = self.write_comments(
            [
                {
                    "path": "src/a.py",
                    "line": 7,
                    "side": "LEFT",
                    "body": "```suggestion\nvalue = normalize(raw)\n```",
                }
            ]
        )
        with self.assertRaisesRegex(ValueError, "RIGHT side"):
            review_common.load_comments(path, review_common.DEFAULT_SIGNOFF)

    def test_load_comments_rejects_invalid_paths(self) -> None:
        path = self.write_comments(
            [{"path": "../secret.txt", "position": 1, "body": "Nope"}]
        )
        with self.assertRaisesRegex(ValueError, "must not traverse parent directories"):
            review_common.load_comments(path, review_common.DEFAULT_SIGNOFF)

    def test_submit_review_reexports_shared_helpers(self) -> None:
        self.assertIs(submit_review.load_optional_comments, review_common.load_optional_comments)
        self.assertIs(submit_review.load_comments, review_common.load_comments)
        self.assertIs(submit_review.build_review_payload, review_common.build_review_payload)

    def test_validate_review_anchors_accepts_current_diff_lines(self) -> None:
        entries = diff_position.parse_diff(SAMPLE_DIFF)
        review_common.validate_review_anchors(
            [
                {"path": "src/foo.py", "line": 11, "side": "RIGHT", "body": "Line"},
                {"path": "src/foo.py", "position": 2, "body": "Position"},
                {"path": "src/foo.py", "subject_type": "file", "body": "File"},
            ],
            entries,
        )

    def test_validate_review_anchors_rejects_missing_line(self) -> None:
        entries = diff_position.parse_diff(SAMPLE_DIFF)
        with self.assertRaisesRegex(ValueError, "anchor is not present"):
            review_common.validate_review_anchors(
                [{"path": "src/foo.py", "line": 999, "side": "RIGHT", "body": "Line"}],
                entries,
            )

    def test_submit_review_allows_empty_comments_file_for_dry_run(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        body_path = Path(temp_dir.name) / "body.txt"
        body_path.write_text("Looks good", encoding="utf-8")

        with mock.patch.object(
            sys,
            "argv",
            [
                "submit_review.py",
                "--repo",
                "owner/repo",
                "--pr",
                "1",
                "--body-file",
                str(body_path),
                "--dry-run",
            ],
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(submit_review.main(), 0)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["review"]["comments"], [])
        self.assertEqual(payload["replies"], [])

    def test_submit_review_replies_only_dry_run_does_not_require_body(self) -> None:
        comments_path = self.write_comments([{"in_reply_to": 12345, "body": "Fixed"}])

        with mock.patch.object(
            sys,
            "argv",
            [
                "submit_review.py",
                "--repo",
                "owner/repo",
                "--pr",
                "1",
                "--comments-file",
                comments_path,
                "--replies-only",
                "--dry-run",
            ],
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(submit_review.main(), 0)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(len(payload["replies"]), 1)


class ReviewThreadTests(unittest.TestCase):
    def test_parse_repo_accepts_owner_repo(self) -> None:
        self.assertEqual(review_threads.parse_repo("owner/repo"), ("owner", "repo"))

    def test_parse_repo_rejects_invalid_repo(self) -> None:
        with self.assertRaisesRegex(ValueError, "owner/repo"):
            review_threads.parse_repo("owner/repo/extra")


if __name__ == "__main__":
    unittest.main()
