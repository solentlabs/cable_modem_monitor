#!/bin/bash
# Fresh Start Script - Reset VS Code state to test new developer experience
# This is ONLY needed to test what a brand new developer sees
# Normal development doesn't require this script

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Fresh Start - Reset VS Code State"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This script resets VS Code's memory of this project."
echo "Use this to test the new developer onboarding experience."
echo ""
echo "⚠️  Note: This is ONLY for testing. Normal development doesn't need this."
echo ""

# Step 1: Check if VS Code is running
if pgrep -f "code" > /dev/null 2>&1; then
  echo "⚠️  VS Code appears to be running"
  echo ""
  read -p "Close all VS Code windows and press Enter to continue (or Ctrl+C to cancel)... "
fi

# Step 2: Detect OS and set cache path
if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "linux"* ]]; then
  CACHE_PATH="$HOME/.config/Code/User/workspaceStorage"
  OS_NAME="Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
  CACHE_PATH="$HOME/Library/Application Support/Code/User/workspaceStorage"
  OS_NAME="macOS"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
  CACHE_PATH="$APPDATA/Code/User/workspaceStorage"
  OS_NAME="Windows"
else
  echo "❌ Unknown OS type: $OSTYPE"
  echo "Manually clear: VS Code Settings → Clear Workspace Cache"
  exit 1
fi

echo "🖥️  Detected: $OS_NAME"
echo ""

# Step 3: Clear workspace cache for this project
echo "🧹 Clearing VS Code workspace cache for this project..."
if [ -d "$CACHE_PATH" ]; then
  found=0
  for dir in "$CACHE_PATH"/*; do
    if [ -f "$dir/workspace.json" ]; then
      if grep -q "cable_modem_monitor" "$dir/workspace.json" 2>/dev/null; then
        echo "   → Removing: $(basename "$dir")"
        rm -rf "$dir"
        found=$((found + 1))
      fi
    fi
  done

  if [ $found -gt 0 ]; then
    echo "   ✅ Cleared $found workspace cache folder(s)"
  else
    echo "   → No cached workspace found (already clean)"
  fi
else
  echo "   → Workspace cache directory not found"
  echo "   → This is normal on first install"
fi

# Step 4: Optional - Remove .venv
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Optional: Test Setup From Scratch"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Remove .venv to test the complete setup process?"
echo "(This simulates a brand new clone)"
echo ""
read -p "Remove .venv? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
  if [ -d ".venv" ]; then
    echo "   → Removing .venv..."
    rm -rf .venv
    echo "   ✅ Removed .venv"
  else
    echo "   → No .venv found"
  fi
else
  echo "   → Keeping .venv (faster testing)"
fi

# Step 5: Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Fresh start ready!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Now open VS Code to see the new developer experience:"
echo ""
echo "   code ."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "What You Should See:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Notifications (in order):"
echo "  1. 'Dev Container configuration available...'"
echo "     → Your choice: Use it OR dismiss"
echo ""
echo "  2. 'Install recommended extensions?'"
echo "     → Click 'Install' (6 essential extensions)"
echo ""
echo "What You Should NOT See:"
echo "  ❌ GitLens notification (removed - optional)"
echo "  ❌ CodeQL error notifications (removed - optional)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "If you dismissed Dev Container:"
echo "   ./scripts/setup.sh"
echo ""
echo "Then validate everything works:"
echo "   make validate"
echo ""
echo "Or use VS Code task:"
echo "   Ctrl+Shift+P → Tasks: Run Task → Quick Validation"
echo ""
