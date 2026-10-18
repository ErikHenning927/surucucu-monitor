"""
Configurações persistentes, caminhos e sanitização de ambiente para o Surucucu.
"""

import os
import sys
import json

# -----------------------------------------------------------------------------
# Sanitização de ambiente para GTK / Wayland / Snap
# -----------------------------------------------------------------------------
def sanitize_environment():
    """Remove contaminação de variáveis exportadas por pacotes snap (ex: VS Code Snap)"""
    if "GSETTINGS_SCHEMA_DIR" in os.environ and "snap" in os.environ["GSETTINGS_SCHEMA_DIR"].lower():
        del os.environ["GSETTINGS_SCHEMA_DIR"]

    if "XDG_DATA_DIRS_VSCODE_SNAP_ORIG" in os.environ:
        os.environ["XDG_DATA_DIRS"] = os.environ["XDG_DATA_DIRS_VSCODE_SNAP_ORIG"]
    elif "XDG_DATA_DIRS" in os.environ and "snap" in os.environ["XDG_DATA_DIRS"].lower():
        clean_dirs = [d for d in os.environ["XDG_DATA_DIRS"].split(":") if "snap" not in d.lower()]
        if "/usr/share" not in clean_dirs:
            clean_dirs.append("/usr/share")
        os.environ["XDG_DATA_DIRS"] = ":".join(clean_dirs)

    # Suporte a virtualenvs: busca bibliotecas nativas GTK/Cairo do sistema se não estiverem na venv
    for dist_path in ["/usr/lib/python3/dist-packages", "/usr/local/lib/python3/dist-packages"]:
        if os.path.isdir(dist_path) and dist_path not in sys.path:
            sys.path.append(dist_path)

# Executa sanitização ao importar módulo de configuração
sanitize_environment()

# -----------------------------------------------------------------------------
# Constantes de Diretórios e Arquivos
# -----------------------------------------------------------------------------
CONFIG_DIR = os.path.expanduser("~/.config/surucucu")
CONFIG_FILE = os.path.join(CONFIG_DIR, "hud_config.json")
LEGACY_CONFIG_FILE = os.path.expanduser("~/.config/setup-linux/hud_config.json")

def load_config():
    """Carrega as preferências salvas do usuário (opacidade, janela suspensa, etc.)"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        elif os.path.exists(LEGACY_CONFIG_FILE):
            with open(LEGACY_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"opacity": 82, "pinned": True}

def save_config(cfg):
    """Salva as preferências no arquivo ~/.config/surucucu/hud_config.json"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def get_icon_path():
    """Localiza o ícone oficial do Surucucu no pacote ou no sistema"""
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    candidates = [
        os.path.join(assets_dir, "icon.png"),
        os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps/surucucu.png"),
        os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps/surucucu.svg"),
        os.path.join(assets_dir, "icon.svg"),
    ]
    for icon_path in candidates:
        if os.path.exists(icon_path):
            return icon_path
    return None
