import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
WB_PATH = ROOT / "scripts" / "wb.py"


def load_wb():
    spec = importlib.util.spec_from_file_location("public_wb", WB_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ApiKeyTests(unittest.TestCase):
    def test_environment_key_takes_precedence(self):
        wb = load_wb()
        with mock.patch.dict(
            os.environ,
            {"WB2API_KEY": "from-environment", "WB2API_KEYFILE": "Z:/missing"},
            clear=False,
        ):
            self.assertEqual(wb.api_key(), "from-environment")

    def test_key_file_is_portable(self):
        wb = load_wb()
        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = pathlib.Path(temp_dir) / "API_KEY.txt"
            key_file.write_text("api_key=from-file\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"WB2API_KEY": "", "WB2API_KEYFILE": str(key_file)},
                clear=False,
            ):
                self.assertEqual(wb.api_key(), "from-file")

    def test_path_guard_rejects_cross_drive_paths(self):
        wb = load_wb()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = os.path.realpath(temp_dir)
            with self.assertRaises(ValueError):
                wb._inside(root, "Z:/outside.txt")

    def test_agent_refuses_sensitive_files(self):
        wb = load_wb()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            sensitive_paths = (
                "auths/workbuddy-test.json",
                "API_KEY.txt",
                ".env",
                "config.json",
                "auth.json",
                "access_token.json",
                "session.json",
                "cookies.txt",
            )
            for relative in sensitive_paths:
                secret_file = root / relative
                secret_file.parent.mkdir(parents=True, exist_ok=True)
                secret_file.write_text("TEST_SECRET_MARKER", encoding="utf-8")
                output = wb._exec_tool(
                    os.path.realpath(temp_dir),
                    "read_file",
                    {"path": relative},
                )
                self.assertIn("拒绝", output, relative)
                self.assertNotIn("TEST_SECRET_MARKER", output, relative)

    def test_healthz_headers_do_not_require_api_key(self):
        wb = load_wb()
        with mock.patch.object(
            wb,
            "api_key",
            side_effect=AssertionError("healthz must not read the API key"),
        ):
            headers = wb.request_headers("/healthz")
        self.assertNotIn("Authorization", headers)


class PublicationSafetyTests(unittest.TestCase):
    def test_public_files_do_not_contain_private_markers(self):
        forbidden = (
            "C:" + "/Users/" + "LEE",
            "C:" + chr(92) + "Users" + chr(92) + "LEE",
            "D:" + "/" + "05 任务",
            "D:" + chr(92) + "05 任务",
            "0 " + "记忆",
            "ADMIN_" + "PASSWORD.txt",
            "workbuddy-desktop" + "-ai.info",
        )
        checked = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.suffix.lower() not in {".md", ".py", ".ps1", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            checked.append(path)
            for marker in forbidden:
                self.assertNotIn(marker, text, f"private marker in {path}: {marker}")
        self.assertTrue(checked)


if __name__ == "__main__":
    unittest.main()
