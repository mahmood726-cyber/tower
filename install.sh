#!/usr/bin/env bash
#
# Tower Installer
# One-command installation for scientists
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/.../install.sh | bash
#   OR
#   bash install.sh
#

set -e

# Colors for friendly output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

print_banner() {
    echo ""
    echo -e "${CYAN}╭─────────────────────────────────────────╮${NC}"
    echo -e "${CYAN}│${NC}  ${BOLD}Tower Installer${NC}                        ${CYAN}│${NC}"
    echo -e "${CYAN}│${NC}  Research Workflow Made Simple          ${CYAN}│${NC}"
    echo -e "${CYAN}╰─────────────────────────────────────────╯${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}→${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS="linux" ;;
        Darwin*)    OS="mac" ;;
        CYGWIN*|MINGW*|MSYS*) OS="windows" ;;
        *)          OS="unknown" ;;
    esac
    echo "$OS"
}

# Check if command exists
has_command() {
    command -v "$1" &> /dev/null
}

# Check Python
check_python() {
    if has_command python3; then
        PYTHON_CMD="python3"
        PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
        return 0
    elif has_command python; then
        PYTHON_CMD="python"
        PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
        # Check if it's Python 3
        if [[ "$PYTHON_VERSION" == 2.* ]]; then
            return 1
        fi
        return 0
    fi
    return 1
}

# Show Python install instructions
show_python_help() {
    local os="$1"
    echo ""
    echo -e "  ${BOLD}Tower needs Python 3.8 or newer.${NC}"
    echo ""
    echo "  To install Python:"
    echo ""
    case "$os" in
        mac)
            echo "    ${CYAN}brew install python3${NC}"
            echo ""
            echo "  Don't have Homebrew? Install it first:"
            echo "    ${CYAN}/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${NC}"
            ;;
        linux)
            echo "    Ubuntu/Debian: ${CYAN}sudo apt install python3${NC}"
            echo "    Fedora:        ${CYAN}sudo dnf install python3${NC}"
            echo "    Arch:          ${CYAN}sudo pacman -S python${NC}"
            ;;
        windows)
            echo "    1. Go to ${CYAN}https://python.org/downloads${NC}"
            echo "    2. Download Python 3.x"
            echo "    3. Run installer (check 'Add to PATH')"
            ;;
        *)
            echo "    Visit ${CYAN}https://python.org/downloads${NC}"
            ;;
    esac
    echo ""
    echo "  Then run this installer again."
    echo ""
}

# Get Tower directory
get_tower_dir() {
    # If running from within tower repo, use that
    if [ -f "$(dirname "$0")/scripts/tower_run.sh" ]; then
        echo "$(cd "$(dirname "$0")" && pwd)"
    elif [ -f "./scripts/tower_run.sh" ]; then
        echo "$(pwd)"
    else
        # Default install location
        echo "$HOME/tower"
    fi
}

# Create directory structure
setup_directories() {
    local tower_dir="$1"

    mkdir -p "$tower_dir/control/backups"
    mkdir -p "$tower_dir/control/queues"
    mkdir -p "$tower_dir/control/alerts"
    mkdir -p "$tower_dir/artifacts"
    mkdir -p "$tower_dir/proofpacks"
    mkdir -p "$tower_dir/worktrees"
    mkdir -p "$tower_dir/scripts"
}

# Initialize status.json if needed
init_status() {
    local tower_dir="$1"
    local status_file="$tower_dir/control/status.json"

    if [ ! -f "$status_file" ]; then
        cat > "$status_file" << 'EOF'
{
  "spec_version": "v1.5.7",
  "cards": [],
  "last_updated": null
}
EOF
    fi
}

# Add tower alias to shell config
setup_path() {
    local tower_dir="$1"
    local shell_rc=""

    # Detect shell config file
    if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
        shell_rc="$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
        shell_rc="$HOME/.bashrc"
    elif [ -f "$HOME/.bash_profile" ]; then
        shell_rc="$HOME/.bash_profile"
    fi

    if [ -z "$shell_rc" ]; then
        print_warning "Could not detect shell config file"
        echo "    Add this to your shell config manually:"
        echo "    ${CYAN}alias tower='$tower_dir/tower-cli'${NC}"
        return 1
    fi

    # Check if already configured
    if grep -q "tower-cli" "$shell_rc" 2>/dev/null; then
        return 0
    fi

    # Add alias
    echo "" >> "$shell_rc"
    echo "# Tower - Research Workflow" >> "$shell_rc"
    echo "alias tower='$tower_dir/tower-cli'" >> "$shell_rc"

    return 0
}

# Main installation
main() {
    print_banner

    local os=$(detect_os)
    print_step "Detected OS: $os"

    # Check Python
    print_step "Checking for Python..."
    if ! check_python; then
        print_error "Python not found"
        show_python_help "$os"
        exit 1
    fi
    print_success "Found Python $PYTHON_VERSION ($PYTHON_CMD)"

    # Check Git
    print_step "Checking for Git..."
    if has_command git; then
        GIT_VERSION=$(git --version | cut -d' ' -f3)
        print_success "Found Git $GIT_VERSION"
    else
        print_warning "Git not found (optional, but recommended)"
    fi

    # Determine install location
    TOWER_DIR=$(get_tower_dir)
    print_step "Install location: $TOWER_DIR"

    # Setup directories
    print_step "Setting up directories..."
    setup_directories "$TOWER_DIR"
    print_success "Directories created"

    # Initialize status.json
    print_step "Initializing status file..."
    init_status "$TOWER_DIR"
    print_success "Status file ready"

    # Make scripts executable
    print_step "Setting permissions..."
    chmod +x "$TOWER_DIR/tower-cli" 2>/dev/null || true
    chmod +x "$TOWER_DIR/scripts/"*.sh 2>/dev/null || true
    print_success "Permissions set"

    # Setup PATH
    print_step "Adding tower to PATH..."
    if setup_path "$TOWER_DIR"; then
        print_success "Added to PATH"
    fi

    # Done!
    echo ""
    echo -e "${GREEN}╭─────────────────────────────────────────╮${NC}"
    echo -e "${GREEN}│${NC}  ${BOLD}Installation Complete!${NC}                 ${GREEN}│${NC}"
    echo -e "${GREEN}╰─────────────────────────────────────────╯${NC}"
    echo ""
    echo "  To start using Tower:"
    echo ""
    echo "    1. Restart your terminal, OR run:"
    echo "       ${CYAN}source ~/.bashrc${NC}  (or ~/.zshrc)"
    echo ""
    echo "    2. Try these commands:"
    echo "       ${CYAN}tower status${NC}        See your cards"
    echo "       ${CYAN}tower new${NC}           Create a new card"
    echo "       ${CYAN}tower help${NC}          See all commands"
    echo ""
    echo "  Need help? Run: ${CYAN}tower help${NC}"
    echo ""
}

main "$@"
