import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "skills" / "codex-usage-dashboard" / "scripts"


class PosixInstallerTest(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX installer test")
    def test_install_and_new_version_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            refreshed_plugin = root / "refreshed-plugin"
            shutil.copytree(PLUGIN_ROOT, refreshed_plugin)
            refreshed_manifest_path = refreshed_plugin / ".codex-plugin/plugin.json"
            refreshed_manifest = json.loads(refreshed_manifest_path.read_text())
            refreshed_manifest["version"] = "0.2.0"
            refreshed_manifest_path.write_text(json.dumps(refreshed_manifest, indent=2) + "\n")
            fake_bin = root / "bin"
            fake_bin.mkdir()
            call_log = root / "codex-calls.txt"
            plugin_json = json.dumps(
                {
                    "installed": [
                        {
                            "pluginId": "codex-usage-dashboard@open-codex-plugins",
                            "source": {"path": str(refreshed_plugin)},
                        }
                    ]
                }
            )
            fake_codex = fake_bin / "codex"
            fake_codex.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' \"$*\" >> {str(call_log)!r}\n"
                "if [ \"$*\" = \"plugin list --json\" ]; then\n"
                f"  printf '%s\\n' {plugin_json!r}\n"
                "fi\n"
            )
            fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)
            install_root = root / "installed"
            environment = os.environ.copy()
            environment["PATH"] = str(fake_bin) + os.pathsep + environment["PATH"]
            environment["CODEX_CLI_PATH"] = str(fake_codex)
            subprocess.run(
                [
                    "bash",
                    str(SCRIPTS / "install.sh"),
                    "--install-root",
                    str(install_root),
                    "--enable-auto-update",
                    "--no-service",
                ],
                check=True,
                env=environment,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "bash",
                    str(install_root / "update.sh"),
                    "--install-root",
                    str(install_root),
                    "--no-service",
                ],
                check=True,
                env=environment,
                capture_output=True,
                text=True,
            )
            calls = call_log.read_text().splitlines()
            self.assertEqual(
                calls,
                [
                    "plugin marketplace upgrade open-codex-plugins",
                    "plugin add codex-usage-dashboard@open-codex-plugins",
                    "plugin list --json",
                ],
            )
            self.assertEqual((install_root / "app/VERSION").read_text().strip(), "0.2.0")
            self.assertEqual((install_root / "previous/VERSION").read_text().strip(), "0.1.0")
            self.assertTrue((install_root / "auto-update-enabled").exists())


if __name__ == "__main__":
    unittest.main()
