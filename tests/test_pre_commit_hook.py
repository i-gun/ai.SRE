"""Static validation tests for git-hooks files — no hook execution."""
from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = PROJECT_ROOT / "git-hooks"


# ---------------------------------------------------------------------------
# pre-commit
# ---------------------------------------------------------------------------

class TestPreCommitHookFile(unittest.TestCase):
    """Static checks for git-hooks/pre-commit."""

    def setUp(self) -> None:
        self.path = HOOKS_DIR / "pre-commit"
        self.content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def test_pre_commit_file_exists(self) -> None:
        self.assertTrue(self.path.exists(), f"Expected {self.path} to exist")

    def test_pre_commit_has_shebang(self) -> None:
        first_line = self.content.splitlines()[0] if self.content else ""
        self.assertTrue(
            first_line.startswith("#!"),
            f"Expected first line to start with '#!', got: {first_line!r}",
        )

    def test_pre_commit_has_phase1_detection(self) -> None:
        self.assertTrue(
            "PHASE 1" in self.content or "staged" in self.content.lower(),
            "Expected 'PHASE 1' or staged-file detection in pre-commit hook",
        )

    def test_pre_commit_has_phase2_readme(self) -> None:
        self.assertIn("PHASE 2", self.content)
        self.assertIn("README", self.content)

    def test_pre_commit_has_phase3_formatting(self) -> None:
        self.assertIn("PHASE 3", self.content)

    def test_pre_commit_has_phase4_final(self) -> None:
        self.assertIn("PHASE 4", self.content)

    def test_pre_commit_non_empty(self) -> None:
        self.assertGreater(
            len(self.content),
            100,
            "pre-commit hook file is unexpectedly short",
        )


# ---------------------------------------------------------------------------
# post-checkout
# ---------------------------------------------------------------------------

class TestPostCheckoutHookFile(unittest.TestCase):
    """Static checks for git-hooks/post-checkout."""

    def setUp(self) -> None:
        self.path = HOOKS_DIR / "post-checkout"
        self.content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def test_post_checkout_file_exists(self) -> None:
        self.assertTrue(self.path.exists(), f"Expected {self.path} to exist")

    def test_post_checkout_has_shebang(self) -> None:
        first_line = self.content.splitlines()[0] if self.content else ""
        self.assertTrue(
            first_line.startswith("#!"),
            f"Expected first line to start with '#!', got: {first_line!r}",
        )

    def test_post_checkout_non_empty(self) -> None:
        self.assertGreater(
            len(self.content),
            100,
            "post-checkout hook file is unexpectedly short",
        )

    def test_post_checkout_references_hook_reinstallation(self) -> None:
        lower = self.content.lower()
        self.assertTrue(
            "install" in lower or "hooks" in lower,
            "Expected 'install' or 'hooks' reference in post-checkout hook",
        )


# ---------------------------------------------------------------------------
# install-hooks.sh
# ---------------------------------------------------------------------------

class TestInstallHooksScript(unittest.TestCase):
    """Static checks for git-hooks/install-hooks.sh."""

    def setUp(self) -> None:
        self.path = HOOKS_DIR / "install-hooks.sh"
        self.content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def test_install_hooks_file_exists(self) -> None:
        self.assertTrue(self.path.exists(), f"Expected {self.path} to exist")

    def test_install_hooks_has_shebang(self) -> None:
        first_line = self.content.splitlines()[0] if self.content else ""
        self.assertTrue(
            first_line.startswith("#!"),
            f"Expected first line to start with '#!', got: {first_line!r}",
        )

    def test_install_hooks_non_empty(self) -> None:
        self.assertGreater(
            len(self.content),
            100,
            "install-hooks.sh file is unexpectedly short",
        )

    def test_install_hooks_references_pre_commit(self) -> None:
        self.assertIn(
            "pre-commit",
            self.content,
            "Expected install-hooks.sh to reference 'pre-commit'",
        )


# ---------------------------------------------------------------------------
# HOOKS_DOCUMENTATION.md (optional)
# ---------------------------------------------------------------------------

class TestHooksDocumentation(unittest.TestCase):
    """Static checks for git-hooks/HOOKS_DOCUMENTATION.md (optional)."""

    def setUp(self) -> None:
        self.path = HOOKS_DIR / "HOOKS_DOCUMENTATION.md"
        self.content = self.path.read_text(encoding="utf-8") if self.path.exists() else None

    def test_documentation_file_exists(self) -> None:
        self.assertTrue(
            self.path.exists(),
            f"Expected HOOKS_DOCUMENTATION.md at {self.path}",
        )

    def test_documentation_non_empty(self) -> None:
        if self.content is None:
            self.skipTest("HOOKS_DOCUMENTATION.md does not exist")
        self.assertGreater(len(self.content), 0, "HOOKS_DOCUMENTATION.md is empty")

    def test_documentation_has_sections(self) -> None:
        if self.content is None:
            self.skipTest("HOOKS_DOCUMENTATION.md does not exist")
        self.assertTrue(
            any(line.startswith("#") for line in self.content.splitlines()),
            "Expected at least one markdown heading (#) in HOOKS_DOCUMENTATION.md",
        )


if __name__ == "__main__":
    unittest.main()
