#!/bin/bash
# =============================================================================
# AI Engineering Environment Setup Script
# Tested on: Ubuntu 22.04, macOS 13+, Windows WSL2
# Run: chmod +x setup.sh && ./setup.sh
# =============================================================================

set -e  # Exit on any error

echo "🚀 AI Engineering Environment Setup"
echo "===================================="

# Detect OS
OS="$(uname -s)"
echo "Detected OS: $OS"

# ─── 1. PYTHON 3.11+ ──────────────────────────────────────────────────────────
echo ""
echo "📦 Installing Python 3.11..."

if [[ "$OS" == "Linux" ]]; then
    sudo apt update -y
    sudo apt install -y python3.11 python3.11-venv python3-pip curl git wget unzip
elif [[ "$OS" == "Darwin" ]]; then
    # Install Homebrew if missing
    if ! command -v brew &>/dev/null; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python@3.11 git curl wget
fi

python3 --version

# ─── 2. UV (Fast Python Package Manager) ──────────────────────────────────────
echo ""
echo "📦 Installing UV (faster than pip)..."
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"
uv --version

# ─── 3. DOCKER ────────────────────────────────────────────────────────────────
echo ""
echo "🐳 Installing Docker..."
if [[ "$OS" == "Linux" ]]; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    sudo systemctl enable docker
    sudo systemctl start docker
elif [[ "$OS" == "Darwin" ]]; then
    echo "Install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
fi

# ─── 4. OLLAMA (Local LLMs — FREE) ────────────────────────────────────────────
echo ""
echo "🦙 Installing Ollama..."
curl -fsSL https://ollama.ai/install.sh | sh

echo "Pulling Llama 3.1 8B (requires ~5GB disk)..."
ollama pull llama3.1:8b &   # Run in background
echo "Pulling nomic-embed-text for embeddings..."
ollama pull nomic-embed-text &

# ─── 5. GIT CONFIG ────────────────────────────────────────────────────────────
echo ""
echo "⚙️  Configuring Git..."
read -p "Enter your Git name: " GIT_NAME
read -p "Enter your Git email: " GIT_EMAIL
git config --global user.name "$GIT_NAME"
git config --global user.email "$GIT_EMAIL"
git config --global init.defaultBranch main
git config --global core.editor "code --wait"
git config --global pull.rebase false

# ─── 6. SSH KEY FOR GITHUB ────────────────────────────────────────────────────
echo ""
echo "🔑 Generating SSH key for GitHub..."
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -C "$GIT_EMAIL" -f ~/.ssh/id_ed25519 -N ""
    echo ""
    echo "📋 Copy this public key to GitHub (Settings → SSH Keys):"
    cat ~/.ssh/id_ed25519.pub
fi

# ─── 7. VS CODE EXTENSIONS ────────────────────────────────────────────────────
echo ""
echo "💻 Installing VS Code extensions..."
if command -v code &>/dev/null; then
    code --install-extension ms-python.python
    code --install-extension ms-python.pylance
    code --install-extension charliermarsh.ruff
    code --install-extension ms-python.mypy-type-checker
    code --install-extension ms-azuretools.vscode-docker
    code --install-extension eamodio.gitlens
    code --install-extension github.copilot
    code --install-extension humao.rest-client
    code --install-extension rangav.vscode-thunder-client
    code --install-extension mtxr.sqltools
    code --install-extension redhat.vscode-yaml
    code --install-extension ms-vscode.makefile-tools
    echo "✅ VS Code extensions installed"
else
    echo "⚠️  VS Code not found. Install from: https://code.visualstudio.com/"
fi

echo ""
echo "✅ Setup complete! Restart your terminal and run: source ~/.bashrc"
