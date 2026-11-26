"""Deterministic rendering cases, independent of model quality."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo_ui import EMPTY_REPLY, completed_reply


class ReplyTests(unittest.TestCase):
    def test_empty_fences(self):
        for text in ("", "  ", "```sql\n```\n```\n```", "<code>\n</code>"):
            with self.subTest(text=text):
                self.assertEqual(completed_reply(text), EMPTY_REPLY)

    def test_markdown_and_sql(self):
        sql = "SELECT COUNT(*) FROM sales;"
        fenced = f"```sql\n{sql}\n```"
        self.assertEqual(completed_reply(sql), fenced)
        self.assertEqual(completed_reply(f"<code>\n{fenced}\n</code>"), fenced)
        mixed = f"The query counts rows.\n\n{fenced}"
        self.assertEqual(completed_reply(mixed), mixed)
        prose = "A paragraph about statistics. " * 100
        self.assertEqual(completed_reply(prose), prose)


if __name__ == "__main__":
    unittest.main()
