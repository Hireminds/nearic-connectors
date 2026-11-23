"""Task-state behavior; no model or third-party test dependency."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("task_state", ROOT / "scripts/spec-kit-task-state.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TaskStateTests(unittest.TestCase):
    def test_mixed_tasks(self):
        self.assertEqual(MODULE.count_tasks("- [x] T001 Done\n- [ ] T002 Next\n"), (2, 1))

    def test_uppercase_completion(self):
        self.assertEqual(MODULE.count_tasks("- [X] T001 Done\n"), (1, 0))

    def test_fenced_examples_are_ignored(self):
        text = "```markdown\n- [ ] T999 Example\n```\n- [x] T001 Done\n"
        self.assertEqual(MODULE.count_tasks(text), (1, 0))

    def test_tilde_fence_and_nested_backticks(self):
        text = "~~~~\n```\n- [ ] T999 Example\n~~~~\n- [x] T001 Done\n"
        self.assertEqual(MODULE.count_tasks(text), (1, 0))

    def test_empty_tasks_refused(self):
        with self.assertRaisesRegex(ValueError, "No tasks"):
            MODULE.count_tasks("# Empty\n")

    def test_duplicate_ids_refused(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            MODULE.count_tasks("- [x] T001 One\n- [ ] T001 Two\n")

    def test_malformed_task_refused(self):
        with self.assertRaisesRegex(ValueError, "Malformed"):
            MODULE.count_tasks("- [x] T001 One\n- [?] T002 Broken\n")

    def test_unclosed_fence_refused(self):
        with self.assertRaisesRegex(ValueError, "Unclosed"):
            MODULE.count_tasks("- [x] T001 One\n```\n- [ ] T002 Hidden\n")

    def test_missing_id_never_disappears_from_count(self):
        with self.assertRaisesRegex(ValueError, "Malformed"):
            MODULE.count_tasks("- [x] T001 One\n- [ ] Missing ID\n")


if __name__ == "__main__":
    unittest.main()
