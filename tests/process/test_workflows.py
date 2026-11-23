"""Exercise the actual Specify runner with a local Codex stub, never a model."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
CLI = os.environ.get("SPECIFY_CLI") or shutil.which("specify")
STUB = r'''#!/usr/bin/env python3
import os
from pathlib import Path
import re
import sys

prompt = sys.argv[2]
match = re.search(r"speckit[-.]([a-z-]+)", prompt)
if not match:
    sys.exit(9)
step = match.group(1)
log = Path("calls.txt")
with log.open("a") as out:
    out.write(step + "\n")
if os.environ.get("STUB_FAIL") == step:
    sys.exit(7)
feature = Path("specs/fixture")
feature.mkdir(parents=True, exist_ok=True)
if step == "specify":
    (feature / "spec.md").write_text("# Fixture\n")
elif step == "plan":
    (feature / "plan.md").write_text("# Plan\n")
elif step == "tasks":
    (feature / "tasks.md").write_text("- [ ] T001 Build fixture\n")
elif step == "analyze":
    print("STUB_ANALYSIS_REPORT")
elif step == "implement":
    if "STUB_ANALYSIS_REPORT" not in prompt:
        sys.exit(8)
    path = feature / "tasks.md"
    if os.environ.get("STUB_PENDING") != "yes":
        path.write_text(path.read_text().replace("- [ ]", "- [x]"))
elif step == "converge" and os.environ.get("STUB_APPEND") == "yes":
    path = feature / "tasks.md"
    if "T002" not in path.read_text():
        with path.open("a") as out:
            out.write("- [ ] T002 Remaining fixture work\n")
'''


@unittest.skipUnless(CLI, "Install the pinned Specify CLI and put specify on PATH")
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nearic-workflow-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / ".specify", self.root / ".specify",
                        ignore=shutil.ignore_patterns(".cache", "runs", "assessments", "bugs"))
        shutil.copytree(ROOT / ".agents", self.root / ".agents")
        shutil.copytree(ROOT / "scripts", self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / ".specify/feature.json").write_text(
            json.dumps({"feature_directory": "specs/fixture"}))
        stub = self.root / "codex-stub"
        stub.write_text(STUB)
        stub.chmod(0o755)
        self.env = dict(os.environ)
        for name in ("SPECIFY_FEATURE_DIRECTORY", "STUB_FAIL", "STUB_PENDING", "STUB_APPEND"):
            self.env.pop(name, None)
        self.env["SPECKIT_INTEGRATION_CODEX_EXECUTABLE"] = str(stub)
        # Executable detection must also resolve the stub when Codex is not installed.
        self.env["PATH"] = str(self.root) + os.pathsep + self.env.get("PATH", "")

    def run_workflow(self, **settings):
        self.env.update(settings)
        result = subprocess.run(
            [CLI, "workflow", "run", "speckit", "--input", "spec=Fixture",
             "--input", "integration=codex", "--input", "speckit_review_spec_verdict=approve",
             "--input", "speckit_review_plan_verdict=approve", "--json"],
            cwd=self.root, env=self.env, text=True, capture_output=True, timeout=30,
        )
        calls = (self.root / "calls.txt").read_text().splitlines()
        return result, calls

    def test_order_and_clean_completion(self):
        result, calls = self.run_workflow()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls, ["specify", "plan", "tasks", "analyze", "implement", "converge"])

    def test_convergence_appends_work_then_repeats(self):
        result, calls = self.run_workflow(STUB_APPEND="yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls[-4:], ["implement", "converge", "implement", "converge"])
        self.assertNotIn("- [ ]", (self.root / "specs/fixture/tasks.md").read_text())

    def test_failed_analyze_stops_before_implementation(self):
        result, calls = self.run_workflow(STUB_FAIL="analyze")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls[-1], "analyze")
        self.assertNotIn("implement", calls)

    def test_failed_implementation_stops_before_convergence(self):
        result, calls = self.run_workflow(STUB_FAIL="implement")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls[-1], "implement")
        self.assertNotIn("converge", calls)

    def test_pending_tasks_never_finish_successfully(self):
        result, calls = self.run_workflow(STUB_PENDING="yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertLessEqual(calls.count("implement"), 3)
        self.assertIn("- [ ]", (self.root / "specs/fixture/tasks.md").read_text())

    def test_bugfix_and_assess_stay_upstream(self):
        for workflow in ("bugfix", "assess"):
            with self.subTest(workflow=workflow):
                result = subprocess.run([CLI, "workflow", "resolve", workflow],
                                        cwd=self.root, env=self.env, text=True,
                                        capture_output=True, check=True)
                self.assertNotIn("nearic-quality", result.stdout)

    def test_gate_resume_does_not_repeat_completed_steps(self):
        result = subprocess.run(
            [CLI, "workflow", "run", "speckit", "--input", "spec=Fixture",
             "--input", "integration=codex", "--json"],
            cwd=self.root, env=self.env, text=True, capture_output=True, check=True,
        )
        state = json.loads(result.stdout)
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["current_step_id"], "review-spec")
        run_id = state["run_id"]
        for verdict in ("speckit_review_spec_verdict", "speckit_review_plan_verdict"):
            result = subprocess.run(
                [CLI, "workflow", "resume", run_id, "--input", verdict + "=approve", "--json"],
                cwd=self.root, env=self.env, text=True, capture_output=True, check=True,
            )
        self.assertEqual(json.loads(result.stdout)["status"], "completed")
        self.assertEqual((self.root / "calls.txt").read_text().splitlines(),
                         ["specify", "plan", "tasks", "analyze", "implement", "converge"])

    def test_missing_active_feature_refuses_task_state(self):
        result = subprocess.run(
            ["python3", "scripts/spec-kit-task-state.py", "--require-complete"],
            cwd=self.root, env=self.env, text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
