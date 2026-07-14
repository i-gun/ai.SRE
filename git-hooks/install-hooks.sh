#!/bin/bash
# ============================================================================
# Git Hooks Installation Script
# ============================================================================
# Purpose: Install Advisor-integrated Git hooks for the project
# Usage: bash git-hooks/install-hooks.sh
# ============================================================================

echo "🔧 Installing Git Hooks for Advisor Agent Integration"
echo "======================================================"

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"

if [ -z "$PROJECT_ROOT" ]; then
  echo "❌ Error: Not in a Git repository"
  exit 1
fi

HOOKS_DIR="$PROJECT_ROOT/.git/hooks"
HOOKS_SOURCE="$PROJECT_ROOT/git-hooks"

# Ensure hooks directory exists
mkdir -p "$HOOKS_DIR"

# Install each hook
HOOKS=("pre-commit" "post-checkout")

for hook in "${HOOKS[@]}"; do
  SOURCE_FILE="$HOOKS_SOURCE/$hook"
  TARGET_FILE="$HOOKS_DIR/$hook"
  
  if [ -f "$SOURCE_FILE" ]; then
    cp "$SOURCE_FILE" "$TARGET_FILE"
    chmod +x "$TARGET_FILE"
    echo "✓ Installed: $hook"
  else
    echo "⚠ Not found: $SOURCE_FILE"
  fi
done

# Make this post-checkout hook executable to ensure it runs after clone
if [ -f "$HOOKS_DIR/post-checkout" ]; then
  chmod +x "$HOOKS_DIR/post-checkout"
  echo "✓ Ensured post-checkout is executable"
fi

echo ""
echo "✅ Git hooks installed successfully!"
echo ""
echo "Installed Hooks:"
echo "  • pre-commit: Updates README.md and formats files before commit"
echo "  • post-checkout: Reinstalls hooks after checkout/clone"
echo ""
echo "Optional formatting tools for enhanced formatting:"
echo "  • Python: pip install black"
echo "  • JavaScript: npm install -g prettier"
echo "  • Markdown: npm install -g markdownlint"
echo ""
echo "To skip hooks on a specific commit:"
echo "  git commit --no-verify"
