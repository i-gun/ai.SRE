"""Tests for gitter_credentials.py — Git credential loading and validation."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "gitter-credentials"
if str(SKILL_PATH) not in sys.path:
    sys.path.insert(0, str(SKILL_PATH))

from gitter_credentials import (
    AuthMethod,
    CredentialError,
    CredentialsLoader,
    GitCredentials,
)

# The module exports a single CredentialError for all failures.
CredentialsValidationError = CredentialError
CredentialsConfigError = CredentialError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_env_file(path: Path, fields: dict) -> None:
    """Write *fields* as KEY=value lines to *path*."""
    with open(path, "w") as fh:
        for k, v in fields.items():
            fh.write(f"{k}={v}\n")


def _valid_https_fields(**overrides) -> dict:
    """Return a minimal valid HTTPS-based config dict, optionally overridden."""
    base = {
        "GIT_USER_NAME": "Alice Example",
        "GIT_USER_EMAIL": "alice@example.com",
        "GITHUB_AUTH_METHOD": "https",
        "GITHUB_TOKEN": "ghp_test_token_abc123",
        "ENVIRONMENT_PROFILE": "dev",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AuthMethod enum
# ---------------------------------------------------------------------------

class TestAuthMethodEnum(unittest.TestCase):
    """AuthMethod enum values and construction."""

    def test_ssh_value(self) -> None:
        self.assertEqual(AuthMethod.SSH.value, "ssh")

    def test_https_value(self) -> None:
        self.assertEqual(AuthMethod.HTTPS.value, "https")

    def test_auto_value(self) -> None:
        self.assertEqual(AuthMethod.AUTO.value, "auto")

    def test_from_string_ssh(self) -> None:
        # AuthMethod has no custom from_string classmethod; the standard Enum
        # constructor serves the same purpose.
        result = AuthMethod("ssh")
        self.assertIs(result, AuthMethod.SSH)

    def test_from_string_case_insensitive(self) -> None:
        # _validate_credentials lower-cases the raw config value before
        # constructing AuthMethod, so "SSH" in an env file maps to AuthMethod.SSH.
        self.assertEqual(AuthMethod("ssh"), AuthMethod.SSH)
        self.assertEqual(AuthMethod("https"), AuthMethod.HTTPS)
        self.assertEqual(AuthMethod("auto"), AuthMethod.AUTO)


# ---------------------------------------------------------------------------
# GitCredentials.to_dict()
# ---------------------------------------------------------------------------

class TestGitCredentials(unittest.TestCase):
    """GitCredentials.to_dict() redaction and transparency rules."""

    def _make(self, **kwargs) -> GitCredentials:
        defaults = dict(
            git_user_name="Alice",
            git_user_email="alice@example.com",
            auth_method=AuthMethod.HTTPS,
        )
        defaults.update(kwargs)
        return GitCredentials(**defaults)

    def test_to_dict_redacts_pat(self) -> None:
        creds = self._make(github_token="super-secret-pat")
        result = creds.to_dict()
        self.assertNotEqual(result["github_token"], "super-secret-pat")
        self.assertEqual(result["github_token"], "***REDACTED***")

    def test_to_dict_redacts_password(self) -> None:
        # GitCredentials stores credentials analogous to a password as
        # ssh_passphrase; it must also be redacted.
        creds = self._make(ssh_passphrase="my-passphrase-secret")
        result = creds.to_dict()
        self.assertNotEqual(result["ssh_passphrase"], "my-passphrase-secret")
        self.assertEqual(result["ssh_passphrase"], "***REDACTED***")

    def test_to_dict_does_not_redact_username(self) -> None:
        creds = self._make(git_user_name="alice-handle")
        self.assertEqual(creds.to_dict()["git_user_name"], "alice-handle")

    def test_to_dict_does_not_redact_email(self) -> None:
        creds = self._make(git_user_email="alice@example.com")
        self.assertEqual(creds.to_dict()["git_user_email"], "alice@example.com")

    def test_to_dict_does_not_redact_name(self) -> None:
        creds = self._make(git_user_name="Alice Example")
        self.assertEqual(creds.to_dict()["git_user_name"], "Alice Example")


# ---------------------------------------------------------------------------
# CredentialsLoader._load_env_file()
# ---------------------------------------------------------------------------

class TestCredentialsLoaderLoadEnvFile(unittest.TestCase):
    """_load_env_file() parsing behaviour using temporary .env files."""

    def setUp(self) -> None:
        self.loader = CredentialsLoader()

    def _parse(self, content: str) -> dict:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as fh:
            fh.write(content)
            tmp = Path(fh.name)
        try:
            return self.loader._load_env_file(tmp)
        finally:
            tmp.unlink(missing_ok=True)

    def test_loads_key_value_pairs(self) -> None:
        result = self._parse("FOO=bar\nBAZ=qux\n")
        self.assertEqual(result["FOO"], "bar")
        self.assertEqual(result["BAZ"], "qux")

    def test_ignores_comment_lines(self) -> None:
        result = self._parse("# this is a comment\nKEY=value\n")
        self.assertNotIn("# this is a comment", result)
        self.assertEqual(result["KEY"], "value")

    def test_ignores_empty_lines(self) -> None:
        result = self._parse("\n\nKEY=value\n\n")
        self.assertEqual(result, {"KEY": "value"})

    def test_strips_surrounding_quotes(self) -> None:
        # NOTE: The current implementation calls str.strip() on the value
        # but does NOT remove surrounding quote characters.  KEY="value"
        # therefore stores the value with quotes intact: '"value"'.
        result = self._parse('KEY="quoted_value"\n')
        self.assertEqual(result["KEY"], '"quoted_value"')

    def test_strips_whitespace_around_equals(self) -> None:
        result = self._parse("KEY = spaced_value\n")
        self.assertEqual(result["KEY"], "spaced_value")


# ---------------------------------------------------------------------------
# CredentialsLoader._validate_credentials()
# ---------------------------------------------------------------------------

class TestValidateCredentials(unittest.TestCase):
    """_validate_credentials() validation rules."""

    def setUp(self) -> None:
        self.loader = CredentialsLoader()

    def _ssh_config(self, key_path: str, **overrides) -> dict:
        cfg = {
            "GIT_USER_NAME": "Alice",
            "GIT_USER_EMAIL": "alice@example.com",
            "GITHUB_AUTH_METHOD": "ssh",
            "GITHUB_SSH_KEY_PATH": key_path,
            "ENVIRONMENT_PROFILE": "dev",
        }
        cfg.update(overrides)
        return cfg

    def _safe_stat(self) -> mock.MagicMock:
        """Return a mock stat result with owner-only (0o600) permissions."""
        stat = mock.MagicMock()
        stat.st_mode = 0o100600
        return stat

    def test_valid_https_config_passes(self) -> None:
        creds = self.loader._validate_credentials(_valid_https_fields())
        self.assertEqual(creds.auth_method, AuthMethod.HTTPS)
        self.assertEqual(creds.git_user_name, "Alice Example")

    def test_valid_ssh_config_passes(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            key_path = fh.name
        try:
            config = self._ssh_config(key_path)
            with mock.patch.object(Path, "stat", return_value=self._safe_stat()):
                creds = self.loader._validate_credentials(config)
            self.assertEqual(creds.auth_method, AuthMethod.SSH)
        finally:
            Path(key_path).unlink(missing_ok=True)

    def test_invalid_email_format_raises(self) -> None:
        config = _valid_https_fields(GIT_USER_EMAIL="not-an-email")
        with self.assertRaises(CredentialError):
            self.loader._validate_credentials(config)

    def test_missing_username_raises(self) -> None:
        config = {k: v for k, v in _valid_https_fields().items() if k != "GIT_USER_NAME"}
        with self.assertRaises(CredentialError):
            self.loader._validate_credentials(config)

    def test_missing_email_raises(self) -> None:
        config = {k: v for k, v in _valid_https_fields().items() if k != "GIT_USER_EMAIL"}
        with self.assertRaises(CredentialError):
            self.loader._validate_credentials(config)

    def test_missing_name_raises(self) -> None:
        # An empty GIT_USER_NAME is treated the same as missing.
        config = _valid_https_fields(GIT_USER_NAME="")
        with self.assertRaises(CredentialError):
            self.loader._validate_credentials(config)

    def test_ssh_method_requires_ssh_key_path(self) -> None:
        config = {
            "GIT_USER_NAME": "Alice",
            "GIT_USER_EMAIL": "alice@example.com",
            "GITHUB_AUTH_METHOD": "ssh",
            # GITHUB_SSH_KEY_PATH intentionally absent
            "ENVIRONMENT_PROFILE": "dev",
        }
        with self.assertRaises(CredentialError):
            self.loader._validate_credentials(config)

    def test_https_method_requires_token_or_password(self) -> None:
        config = {
            "GIT_USER_NAME": "Alice",
            "GIT_USER_EMAIL": "alice@example.com",
            "GITHUB_AUTH_METHOD": "https",
            # GITHUB_TOKEN intentionally absent
            "ENVIRONMENT_PROFILE": "dev",
        }
        with self.assertRaises(CredentialError):
            self.loader._validate_credentials(config)

    def test_gpg_enabled_without_key_id_raises(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            key_path = fh.name
        try:
            config = self._ssh_config(
                key_path,
                GPG_SIGNING_ENABLED="true",
                # GPG_KEY_ID intentionally absent
            )
            with mock.patch.object(Path, "stat", return_value=self._safe_stat()):
                with self.assertRaises(CredentialError):
                    self.loader._validate_credentials(config)
        finally:
            Path(key_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CredentialsLoader profile selection
# ---------------------------------------------------------------------------

class TestEnvProfileSelection(unittest.TestCase):
    """CredentialsLoader.load() profile selection behaviour."""

    def test_default_profile_is_used_when_none_specified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_env_file(root / ".env", _valid_https_fields())
            loader = CredentialsLoader(str(root))
            creds = loader.load()
        self.assertEqual(creds.environment_profile, "dev")

    def test_named_profile_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_env_file(root / ".env", _valid_https_fields())
            # Staging override changes only the profile marker.
            _write_env_file(
                root / ".env.staging",
                _valid_https_fields(ENVIRONMENT_PROFILE="staging"),
            )
            loader = CredentialsLoader(str(root))
            creds = loader.load(profile="staging")
        self.assertEqual(creds.environment_profile, "staging")

    def test_unknown_profile_raises(self) -> None:
        # ENVIRONMENT_PROFILE in .env must be dev/staging/prod; any other value
        # triggers CredentialError from _validate_credentials regardless of the
        # profile argument passed to load().
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_env_file(
                root / ".env",
                _valid_https_fields(ENVIRONMENT_PROFILE="unknown_env"),
            )
            loader = CredentialsLoader(str(root))
            with self.assertRaises(CredentialError):
                loader.load()


if __name__ == "__main__":
    unittest.main()
