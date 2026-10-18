#!/usr/bin/env bash
# ==============================================================================
# 🐍 Surucucu - One-Line Installer
# Instalação automática do Cockpit de Observabilidade de IA & Hardware no Linux
# ==============================================================================
set -e

COLOR_GREEN="\033[1;32m"
COLOR_CYAN="\033[1;36m"
COLOR_YELLOW="\033[1;33m"
COLOR_RED="\033[1;31m"
COLOR_RESET="\033[0m"

echo -e "${COLOR_CYAN}"
cat << "EOF"
   ___                  ___         
  / __|_  _ _ _ _  _ __/ _ \_ _  __ 
  \__ \ || | '_| || / _| (_) | || | 
  |___/\_,_|_|  \_,_|___\___/ \_,_| 
       🐍 Observability Cockpit
EOF
echo -e "${COLOR_RESET}"

# 1. Verificar dependências do sistema
echo -e "${COLOR_CYAN}🔍 [1/4] Verificando dependências do sistema...${COLOR_RESET}"

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${COLOR_RED}❌ Python 3 não encontrado. Por favor, instale o Python 3 antes de continuar.${COLOR_RESET}"
    exit 1
fi

# Detectar gerenciador de pacotes e verificar GTK3 / PyGObject
MISSING_PKGS=""
if command -v apt-get >/dev/null 2>&1; then
    python3 -c "import gi; gi.require_version('Gtk', '3.0')" 2>/dev/null || MISSING_PKGS="python3-gi python3-gi-cairo gir1.2-gtk-3.0"
    if [ -n "$MISSING_PKGS" ]; then
        echo -e "${COLOR_YELLOW}⚠️  Instalando pacotes gráficos nativos necessários (${MISSING_PKGS})...${COLOR_RESET}"
        sudo apt-get update -qq && sudo apt-get install -y -qq $MISSING_PKGS python3-venv
    fi
elif command -v dnf >/dev/null 2>&1; then
    python3 -c "import gi; gi.require_version('Gtk', '3.0')" 2>/dev/null || sudo dnf install -y python3-gobject gtk3
elif command -v pacman >/dev/null 2>&1; then
    python3 -c "import gi; gi.require_version('Gtk', '3.0')" 2>/dev/null || sudo pacman -S --noconfirm python-gobject gtk3
fi

# 2. Instalar o pacote Surucucu (usando ambiente isolado com system-site-packages para zero conflito)
echo -e "${COLOR_CYAN}📦 [2/4] Instalando a versão mais recente do Surucucu...${COLOR_RESET}"

INSTALL_DIR="$HOME/.local/share/surucucu"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

if command -v pipx >/dev/null 2>&1; then
    pipx install surucucu --force
else
    # Cria venv com acesso às bibliotecas GTK nativas do Linux
    python3 -m venv --system-site-packages "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade --quiet surucucu
    ln -sf "$INSTALL_DIR/venv/bin/surucucu" "$BIN_DIR/surucucu"
fi

# 3. Baixar e instalar ícones e atalho no sistema (.desktop)
echo -e "${COLOR_CYAN}🎨 [3/4] Configurando ícones e atalho no menu de aplicativos...${COLOR_RESET}"

ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_PNG_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
APPS_DIR="$HOME/.local/share/applications"

mkdir -p "$ICON_DIR" "$ICON_PNG_DIR" "$APPS_DIR"

BASE_URL="https://raw.githubusercontent.com/ErikHenning927/surucucu-monitor/main"

# Baixar ícone oficial em SVG e PNG
curl -fsSL "$BASE_URL/assets/icon.svg" -o "$ICON_DIR/surucucu.svg" 2>/dev/null || true
curl -fsSL "$BASE_URL/assets/icon.png" -o "$ICON_PNG_DIR/surucucu.png" 2>/dev/null || true

# Criar atalho no lançador do GNOME / Desktop
cat << EOF > "$APPS_DIR/surucucu.desktop"
[Desktop Entry]
Name=Surucucu
GenericName=Observability Cockpit
Comment=Cockpit suspenso de observabilidade para IA, VRAM, Docker e Sistema
Exec=sh -c "\$HOME/.local/bin/surucucu || surucucu"
Icon=surucucu
Terminal=false
Type=Application
Categories=System;Monitor;Development;
StartupNotify=true
StartupWMClass=surucucu
Keywords=gpu;nvidia;vram;docker;cuda;monitor;ai;
EOF

chmod +x "$APPS_DIR/surucucu.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

# 4. Verificar se ~/.local/bin está no PATH
echo -e "${COLOR_CYAN}⚙️  [4/4] Verificando variáveis de ambiente...${COLOR_RESET}"

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    SHELL_RC=""
    if [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    elif [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    else
        SHELL_RC="$HOME/.profile"
    fi

    if [ -f "$SHELL_RC" ] && ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$SHELL_RC"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    fi
fi

echo -e "\n${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo -e "${COLOR_GREEN}✨ Surucucu instalado com sucesso!${COLOR_RESET}"
echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo -e "Você já pode executar o Surucucu das seguintes formas:"
echo -e ""
echo -e "  ${COLOR_CYAN}surucucu${COLOR_RESET}           # Abre o cockpit no terminal"
echo -e "  ${COLOR_CYAN}surucucu -b${COLOR_RESET}        # Abre em segundo plano (HUD suspenso)"
echo -e "  ${COLOR_CYAN}surucucu --help${COLOR_RESET}    # Exibe todos os comandos"
echo -e ""
echo -e "Ou abra diretamente pelo ${COLOR_YELLOW}Menu de Aplicativos${COLOR_RESET} pesquisando por \"${COLOR_CYAN}Surucucu${COLOR_RESET}\"."
echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}\n"
