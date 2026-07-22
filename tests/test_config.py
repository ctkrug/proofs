from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from proof_factory import config


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
COMMON_ENV = DEPLOY / "proof-factory.env"


def _environment_file() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in COMMON_ENV.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or not name:
            raise AssertionError(f"invalid environment-file line: {raw!r}")
        values[name] = value
    return values


class TypedConfigurationTests(unittest.TestCase):
    def test_getters_are_dynamic(self) -> None:
        with patch.dict(os.environ, {"PROOF_TEST_NUMBER": "7"}):
            self.assertEqual(config.get_int("PROOF_TEST_NUMBER", 1), 7)
            os.environ["PROOF_TEST_NUMBER"] = "9"
            self.assertEqual(config.get_int("PROOF_TEST_NUMBER", 1), 9)

    def test_malformed_values_fail_closed(self) -> None:
        cases = (
            ("PROOF_TEST_BOOL", "sometimes", lambda: config.get_bool("PROOF_TEST_BOOL", False)),
            ("PROOF_TEST_INT", "1.5", lambda: config.get_int("PROOF_TEST_INT", 1)),
            ("PROOF_TEST_PATH", "relative/path", lambda: config.get_path("PROOF_TEST_PATH", "/tmp")),
            (
                "PROOF_TEST_URL",
                "http://collector.example",
                lambda: config.get_https_url("PROOF_TEST_URL"),
            ),
        )
        for name, value, getter in cases:
            with self.subTest(name=name), patch.dict(os.environ, {name: value}):
                with self.assertRaises(config.ConfigurationError):
                    getter()

    def test_checked_in_environment_passes_full_validation(self) -> None:
        values = _environment_file()
        with patch.dict(os.environ, values, clear=True):
            config.validate_environment()

    def test_validation_rejects_enabled_telemetry_without_endpoint(self) -> None:
        values = _environment_file()
        values["PHOENIX_ENDPOINT"] = ""
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaisesRegex(config.ConfigurationError, "PHOENIX_ENDPOINT is required"):
                config.validate_environment()

    def test_service_profiles_isolate_unrelated_optional_integrations(self) -> None:
        values = _environment_file()
        values["PHOENIX_ENDPOINT"] = "malformed"
        values["PROOF_RUNTIME_KV_NAMESPACE_ID"] = "malformed"
        with patch.dict(os.environ, values, clear=True):
            config.validate_environment("lab")
            with self.assertRaises(config.ConfigurationError):
                config.validate_environment("lane")
            with self.assertRaises(config.ConfigurationError):
                config.validate_environment("runtime")


class SystemdConfigurationTests(unittest.TestCase):
    def test_every_service_requires_shared_config_and_validates_before_start(self) -> None:
        services = sorted(DEPLOY.glob("*.service"))
        self.assertTrue(services)
        for service in services:
            with self.subTest(service=service.name):
                text = service.read_text()
                self.assertIn("EnvironmentFile=/etc/proof-factory/proof-factory.env", text)
                self.assertRegex(
                    text,
                    r"ExecStartPre=/root/proof-factory/\.venv/bin/python -m proof_factory\.config "
                    r"validate --profile [a-z]+",
                )

    def test_credential_file_scope_is_unchanged(self) -> None:
        credential_services = {
            path.name
            for path in DEPLOY.glob("*.service")
            if "EnvironmentFile=-/root/project-factory/.env" in path.read_text()
        }
        self.assertEqual(credential_services, {
            "proof-factory-easy.service",
            "proof-factory-hard.service",
            "proof-factory-publish.service",
            "proof-factory-runtime-sync.service",
        })

    def test_shared_file_contains_no_credentials(self) -> None:
        names = set(_environment_file())
        forbidden = {name for name in names if any(marker in name for marker in (
            "API_KEY", "API_TOKEN", "PASSWORD", "SECRET", "PRIVATE_KEY", "ACCOUNT_ID",
        ))}
        self.assertEqual(forbidden, set())

    def test_lane_safety_and_lab_resource_limits_remain_unit_scoped(self) -> None:
        easy = (DEPLOY / "proof-factory-easy.service").read_text()
        hard = (DEPLOY / "proof-factory-hard.service").read_text()
        lab = (DEPLOY / "proof-factory-lab.service").read_text()
        self.assertIn("Environment=PROOF_CODEX_SANDBOX=danger-full-access", easy)
        self.assertIn("Environment=PROOF_CODEX_SANDBOX=workspace-write", hard)
        self.assertIn("/root/.local/bin", easy)
        self.assertIn("/root/.local/bin", hard)
        for directive in (
            "CPUQuota=100%", "MemoryHigh=3400M", "MemoryMax=3600M", "TimeoutStartSec=25h",
            "IPAddressDeny=any", "NoNewPrivileges=true",
        ):
            self.assertIn(directive, lab)

    def test_installer_places_config_before_reloading_units(self) -> None:
        script = (ROOT / "scripts" / "install-box.sh").read_text()
        install_at = script.index("install -m 0644 deploy/proof-factory.env")
        reload_at = script.index("systemctl daemon-reload")
        self.assertLess(install_at, reload_at)


if __name__ == "__main__":
    unittest.main()
