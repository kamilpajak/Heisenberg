#!/bin/bash
# Setup git hooks for Heisenberg project

set -e

HOOKS_DIR=".git/hooks"

echo "Setting up git hooks..."

# Set local hooksPath to override any global setting
git config --local core.hooksPath .git/hooks

# Create pre-commit hook
cat > "$HOOKS_DIR/pre-commit" << 'HOOK'
#!/bin/bash
# Pre-commit hook: lint and format code

echo "Running ruff check..."
uv run ruff check src tests --fix --quiet

echo "Running ruff format..."
uv run ruff format src tests --quiet

# Stage any auto-fixes
git add -u
HOOK
chmod +x "$HOOKS_DIR/pre-commit"

# Create commit-msg hook
cat > "$HOOKS_DIR/commit-msg" << 'HOOK'
#!/bin/bash
# Validate conventional commit format

commit_msg=$(cat "$1")
pattern="^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)(\(.+\))?: .+"

if ! echo "$commit_msg" | grep -qE "$pattern"; then
    echo "ERROR: Commit message must follow Conventional Commits format:"
    echo "  type(scope): description"
    echo "  Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore"
    echo ""
    echo "Your message: $commit_msg"
    exit 1
fi
HOOK
chmod +x "$HOOKS_DIR/commit-msg"

echo "Git hooks installed successfully!"
echo "  - pre-commit: ruff check + format"
echo "  - commit-msg: conventional commits validation"
