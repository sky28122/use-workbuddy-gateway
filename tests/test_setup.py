import json
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import unittest
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "setup.ps1"


def powershell_executable():
    candidates = (
        os.environ.get("POWERSHELL_EXE"),
        shutil.which("pwsh"),
        shutil.which("powershell"),
    )
    return next(path for path in candidates if path and pathlib.Path(path).exists())


class SetupPlanTests(unittest.TestCase):
    def test_plan_only_is_non_mutating_and_pinned(self):
        command = [
            powershell_executable(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SETUP),
            "-PlanOnly",
            "-SkillTargets",
            "codex",
        ]
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        plan = json.loads(completed.stdout)
        self.assertFalse(plan["will_mutate"])
        self.assertEqual(plan["skill_targets"], ["codex"])
        self.assertRegex(plan["upstream_ref"], r"^[0-9a-f]{40}$")
        self.assertEqual(plan["listen"], "127.0.0.1:7863")

    def test_vendored_upstream_archive_is_pinned_and_clean(self):
        archive = ROOT / "vendor" / "workbuddy2api-source.zip"
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        setup_text = SETUP.read_text(encoding="utf-8")
        match = re.search(
            r"ExpectedUpstreamHash\s*=\s*'([0-9a-f]{64})'",
            setup_text,
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), digest)
        with zipfile.ZipFile(archive) as bundle:
            names = set(bundle.namelist())
        self.assertIn("LICENSE", names)
        self.assertIn("go.mod", names)
        self.assertNotIn("API_KEY.txt", names)
        self.assertFalse(any(name.startswith("auths/") for name in names))

    def test_invalid_port_is_rejected_before_mutation(self):
        command = [
            powershell_executable(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SETUP),
            "-PlanOnly",
            "-ListenAddress",
            "127.0.0.1:99999",
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
