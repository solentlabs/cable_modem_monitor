#!/bin/bash
# WSL2 Development Environment Setup for Cable Modem Monitor
# Run this in a fresh Ubuntu WSL2 instance:
#   curl -fsSL https://raw.githubusercontent.com/solentlabs/cable_modem_monitor/main/scripts/wsl-setup.sh | bash

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "=========================================="
echo " Cable Modem Monitor - WSL2 Setup"
echo "=========================================="
echo ""

# Step 1: Install Python 3.12
echo -e "${CYAN}[1/6]${NC} Installing Python 3.12..."
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
echo -e "${GREEN}OK${NC} Python $(python3.12 --version)"
echo ""

# Step 2: Install Docker
echo -e "${CYAN}[2/6]${NC} Installing Docker..."
sudo apt install -y docker.io
sudo usermod -aG docker $USER
echo -e "${GREEN}OK${NC} Docker installed"
echo -e "${YELLOW}!${NC} You'll need to restart WSL for docker group to take effect"
echo ""

# Step 3: Install GitHub CLI (for authentication)
echo -e "${CYAN}[3/6]${NC} Installing GitHub CLI..."
sudo apt install -y gh
echo -e "${GREEN}OK${NC} GitHub CLI installed"
echo ""

# Step 4: Clone repository
echo -e "${CYAN}[4/6]${NC} Cloning repository..."
mkdir -p ~/projects/solentlabs/network-monitoring
cd ~/projects/solentlabs/network-monitoring

if [ -d "cable_modem_monitor" ]; then
    echo -e "${YELLOW}!${NC} Repository already exists, pulling latest..."
    cd cable_modem_monitor
    git pull
else
    git clone https://github.com/solentlabs/cable_modem_monitor.git
    cd cable_modem_monitor
fi
echo -e "${GREEN}OK${NC} Repository ready at $(pwd)"
echo ""

# Step 5: Create virtual environment
echo -e "${CYAN}[5/6]${NC} Creating virtual environment..."
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
echo -e "${GREEN}OK${NC} Virtual environment created"
echo ""

# Step 6: Install dependencies
echo -e "${CYAN}[6/6]${NC} Installing dependencies..."
pip install -r requirements-dev.txt
pre-commit install
echo -e "${GREEN}OK${NC} Dependencies installed"
echo ""

echo "=========================================="
echo -e "${GREEN} Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Restart WSL to enable Docker:"
echo "     exit"
echo "     (then in PowerShell: wsl --shutdown)"
echo "     (then reopen Ubuntu)"
echo ""
echo "  2. Navigate to project:"
echo "     cd ~/projects/solentlabs/network-monitoring/cable_modem_monitor"
echo ""
echo "  3. Activate venv:"
echo "     source .venv/bin/activate"
echo ""
echo "  4. Verify everything works:"
echo "     pytest --no-cov -q"
echo ""
echo "  5. Open in VS Code:"
echo "     code ."
echo ""
echo "  6. (Optional) Authenticate with GitHub:"
echo "     gh auth login"
echo ""
