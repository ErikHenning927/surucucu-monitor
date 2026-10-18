#!/usr/bin/env python3
"""
🐍 Surucucu - AI & Dev Observability Cockpit
Monitor de Desenvolvimento focado em Inteligência Artificial, Modelos Locais, Docker e Recursos de Hardware.
Otimizado para Ubuntu Linux (GNOME / Wayland) com NVIDIA GPU (VRAM/CUDA).
"""

import os
import sys
import re
import subprocess
import json
import threading
import time
import psutil

# Sanitização de ambiente: remove contaminação de variáveis exportadas por snaps (ex: VS Code Snap)
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
for _dist_path in ["/usr/lib/python3/dist-packages", "/usr/local/lib/python3/dist-packages"]:
    if os.path.isdir(_dist_path) and _dist_path not in sys.path:
        sys.path.append(_dist_path)

try:
    import cairo
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gtk, Gdk, GLib, Pango, GdkPixbuf
except (ImportError, ValueError) as err:
    print(f"\n❌ [Surucucu] Erro ao carregar interface gráfica: {err}")
    print("💡 O Surucucu utiliza o GTK 3 nativo do Linux. Para instalar no Ubuntu/Debian:")
    print("   sudo apt update && sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0\n")
    sys.exit(1)

# -----------------------------------------------------------------------------
# Configurações Persistentes
# -----------------------------------------------------------------------------
CONFIG_DIR = os.path.expanduser("~/.config/surucucu")
CONFIG_FILE = os.path.join(CONFIG_DIR, "hud_config.json")
LEGACY_CONFIG_FILE = os.path.expanduser("~/.config/setup-linux/hud_config.json")

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        elif os.path.exists(LEGACY_CONFIG_FILE):
            with open(LEGACY_CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"opacity": 82, "pinned": True}

def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Estilização Glassmorphism Dinâmica
# -----------------------------------------------------------------------------
def generate_css(opacity_percent):
    alpha = max(0.15, min(1.0, opacity_percent / 100.0))
    header_alpha = min(0.12, alpha * 0.05)
    card_alpha = min(0.16, alpha * 0.08)
    table_alpha = min(0.42, alpha * 0.28)
    entry_alpha = min(0.60, alpha * 0.45)
    border_alpha = max(0.08, min(0.25, alpha * 0.15))

    return f"""
window {{
    background-color: rgba(15, 17, 26, {alpha:.2f});
    color: #f1f5f9;
    font-family: 'Ubuntu', 'Inter', 'Segoe UI', sans-serif;
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, {border_alpha:.2f});
}}

.header-box {{
    background-color: rgba(255, 255, 255, {header_alpha:.3f});
    border-bottom: 1px solid rgba(255, 255, 255, {border_alpha:.2f});
    padding: 10px 14px;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}}

.title-label {{
    font-size: 14px;
    font-weight: bold;
    color: #38bdf8;
}}

.subtitle-label {{
    font-size: 10px;
    color: #94a3b8;
}}

.card {{
    background-color: rgba(255, 255, 255, {card_alpha:.3f});
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, {border_alpha:.2f});
    padding: 10px;
    margin: 3px 10px;
}}

.card-title {{
    font-size: 11px;
    font-weight: bold;
    color: #cbd5e1;
}}

.card-val-big {{
    font-size: 15px;
    font-weight: bold;
    color: #ffffff;
}}

.card-val-sub {{
    font-size: 11px;
    color: #94a3b8;
}}

.tag-alert-danger {{
    color: #f87171;
    font-weight: bold;
}}

.tag-alert-warn {{
    color: #fbbf24;
    font-weight: bold;
}}

.tag-alert-ok {{
    color: #34d399;
    font-weight: bold;
}}

progressbar trough {{
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    min-height: 8px;
    border: 1px solid rgba(255, 255, 255, 0.04);
}}

progressbar progress {{
    background-color: #38bdf8;
    border-radius: 6px;
}}

.meter-warning progress {{
    background-color: #fbbf24;
}}

.meter-danger progress {{
    background-color: #f87171;
}}

button {{
    background-color: rgba(255, 255, 255, 0.08);
    color: #f1f5f9;
    border-radius: 7px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 500;
}}

button:hover {{
    background-color: rgba(255, 255, 255, 0.16);
    border-color: rgba(255, 255, 255, 0.28);
    color: #ffffff;
}}

button.active {{
    background-color: rgba(56, 189, 248, 0.45);
    border: 1px solid #38bdf8;
    color: #ffffff;
    font-weight: bold;
}}

.btn-clean {{
    background-color: rgba(56, 189, 248, 0.22);
    border: 1px solid rgba(56, 189, 248, 0.55);
    color: #7dd3fc;
    font-weight: bold;
}}

.btn-clean:hover {{
    background-color: rgba(56, 189, 248, 0.40);
    border-color: #38bdf8;
    color: #ffffff;
}}

.btn-kill {{
    background-color: rgba(239, 68, 68, 0.20);
    border: 1px solid rgba(248, 113, 113, 0.50);
    color: #fca5a5;
    font-weight: bold;
    padding: 3px 8px;
}}

.btn-kill:hover {{
    background-color: rgba(239, 68, 68, 0.38);
    border-color: #fca5a5;
    color: #ffffff;
}}

.btn-restart {{
    background-color: rgba(168, 85, 247, 0.20);
    border: 1px solid rgba(192, 132, 252, 0.50);
    color: #d8b4fe;
    font-weight: bold;
    padding: 3px 8px;
}}

.btn-restart:hover {{
    background-color: rgba(168, 85, 247, 0.38);
    border-color: #c084fc;
    color: #ffffff;
}}

entry {{
    background-color: rgba(0, 0, 0, {entry_alpha:.2f});
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 7px;
    padding: 4px 8px;
    font-size: 11px;
}}

entry:focus {{
    border-color: #38bdf8;
    background-color: rgba(0, 0, 0, {min(0.70, entry_alpha + 0.1):.2f});
}}

scrolledwindow {{
    background-color: transparent;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
}}

treeview {{
    background-color: rgba(0, 0, 0, {table_alpha:.2f});
    color: #f1f5f9;
    font-size: 11px;
}}

treeview.view:selected,
treeview:selected,
treeview row:selected,
treeview row:selected:focus {{
    background-color: rgba(2, 132, 199, 0.75);
    color: #ffffff;
}}

treeview row:hover {{
    background-color: rgba(255, 255, 255, 0.08);
}}

button:disabled {{
    opacity: 0.45;
}}

treeview header button {{
    background-color: rgba(255, 255, 255, 0.06);
    color: #cbd5e1;
    font-weight: bold;
    font-size: 10px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.10);
    padding: 4px 6px;
}}

.telemetry-badge {{
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    padding: 3px 8px;
}}

.telemetry-label {{
    font-size: 11px;
    color: #cbd5e1;
}}

.sparkline-label {{
    font-family: 'DejaVu Sans Mono', 'Ubuntu Mono', 'Courier New', monospace;
    font-size: 14px;
    font-weight: bold;
}}

scale trough {{
    background-color: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    min-height: 4px;
}}

scale highlight {{
    background-color: #38bdf8;
    border-radius: 4px;
}}

scale slider {{
    background-color: #ffffff;
    border-radius: 50%;
    min-width: 12px;
    min-height: 12px;
    margin: -4px;
}}
"""

def format_bytes(bytes_val):
    gb = bytes_val / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.2f} GB"
    mb = bytes_val / (1024 ** 2)
    return f"{mb:.0f} MB"

def format_mib(mib_val):
    if mib_val <= 0:
        return "-"
    if mib_val >= 1024:
        return f"{mib_val / 1024.0:.2f} GB"
    return f"{mib_val:.0f} MB"

def make_sparkline(values, max_val=100.0):
    chars = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    out = []
    for v in values:
        norm = max(0.0, min(1.0, v / max_val if max_val > 0 else 0))
        # Se for repouso (< 2%), desenha linha de base contínua visível
        if norm <= 0.02:
            out.append('<span color="#475569"> </span>')
            continue
        idx = max(0, min(len(chars) - 1, int(norm * (len(chars) - 1))))
        ch = chars[idx]
        if norm >= 0.88:
            color = '#f87171'  # vermelho OOM
        elif norm >= 0.70:
            color = '#fbbf24'  # amarelo alta carga
        else:
            color = '#38bdf8'  # azul ciano neon
        out.append(f'<span color="{color}">{ch}</span>')
    return ''.join(out)

# -----------------------------------------------------------------------------
# Classificação Inteligente de Processos
# -----------------------------------------------------------------------------
AI_KEYWORDS = [
    "ollama", "llama", "vllm", "triton", "torch", "pytorch", "cuda",
    "transformers", "langchain", "langfuse", "langgraph", "chroma", "qdrant",
    "milvus", "weaviate", "pgvector", "gradio", "streamlit", "jupyter",
    "tensorrt", "onnx", "whisper", "diffusers", "autotrain", "deepspeed",
    "fastembed", "safetensors", "huggingface", "tgi", "mistral", "gemma",
    "worker", "agent", "sucuri", "suri", "gateway", "api_gateway", "bot_telegram",
    "litellm", "tempo", "grafana", "prometheus"
]

DEV_KEYWORDS = [
    "node", "npm", "npx", "yarn", "pnpm", "vite", "next", "webpack",
    "python", "python3", "flask", "django", "fastapi", "uvicorn", "gunicorn",
    "cargo", "rustc", "go", "java", "ruby", "php", "deno", "bun", "bot_"
]

SERVICE_KEYWORDS = [
    "systemd", "dockerd", "containerd", "postgres", "mysqld", "mariadb",
    "redis-server", "mongod", "nginx", "apache2", "cupsd", "bluetoothd",
    "avahi-daemon", "sshd", "snapd"
]

def is_ai_target(name, cmdline, ports="", image=""):
    name_l = name.lower()
    # Ignora navegadores e players de desktop comuns
    if any(ign in name_l for ign in ["spotify", "chrome", "chromium", "firefox", "brave", "edge", "discord", "slack", "teams", "gnome", "xorg", "wayland"]):
        return False
    # Limpa flags de navegador que causam falsos positivos (ex: --user-agent-product no Spotify)
    clean_cmd = re.sub(r'--user-agent[^\s]*', '', cmdline, flags=re.IGNORECASE)
    text = f"{name} {clean_cmd} {ports} {image}".lower()
    return any(k in text for k in AI_KEYWORDS)

def is_dev_target(name, cmdline, cwd, username):
    name_l = name.lower()
    cmd_l = cmdline.lower()
    is_user_home = "/home/" in cwd or "/home/" in cmd_l
    has_dev = any(k in name_l or f" {k}" in cmd_l or f"/{k}" in cmd_l for k in DEV_KEYWORDS)
    return (has_dev or is_user_home) and not name_l.startswith("gnome") and "antigravity" not in name_l

def is_service_target(name, cmdline, username):
    name_l = name.lower()
    cmd_l = cmdline.lower()
    return any(k in name_l or k in cmd_l for k in SERVICE_KEYWORDS) or username in ["root", "systemd", "postgres", "redis"]

# -----------------------------------------------------------------------------
# Worker Thread de Monitoramento Docker em Tempo Real
# -----------------------------------------------------------------------------
class DockerMonitorWorker:
    def __init__(self):
        self.lock = threading.Lock()
        self.containers = {}       # {name: {id, name, cpu, mem, mem_bytes, ports, status}}
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _parse_mem(self, mem_str):
        try:
            used_part = mem_str.split('/')[0].strip()
            val = float(re.findall(r"[\d\.]+", used_part)[0])
            if "gib" in used_part.lower():
                return val * (1024 ** 3)
            elif "mib" in used_part.lower():
                return val * (1024 ** 2)
            elif "kib" in used_part.lower():
                return val * 1024
            return val
        except Exception:
            return 0.0

    def _run(self):
        while self.running:
            ps_meta = {}
            try:
                res_ps = subprocess.run(
                    ["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}"],
                    capture_output=True, text=True, timeout=2
                )
                if res_ps.returncode == 0:
                    for line in res_ps.stdout.strip().split("\n"):
                        if line.strip():
                            p = line.split("\t")
                            if len(p) >= 3:
                                c_id, c_name, c_status = p[0], p[1], p[2]
                                c_ports = p[3] if len(p) >= 4 else ""
                                c_image = p[4] if len(p) >= 5 else ""
                                clean_ports = []
                                for port in c_ports.split(","):
                                    m = re.search(r":(\d+)->", port)
                                    if m:
                                        clean_ports.append(f":{m.group(1)}")
                                ports_str = " ".join(clean_ports) if clean_ports else (c_ports[:20] if c_ports else "-")
                                ps_meta[c_name] = {
                                    'id': c_id,
                                    'status': c_status,
                                    'ports': ports_str,
                                    'image': c_image
                                }
            except Exception:
                pass

            try:
                proc = subprocess.Popen(
                    ["docker", "stats", "--format", "{{.ID}}\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
                )
                
                start_t = time.time()
                while time.time() - start_t < 6:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    p = line.strip().split("\t")
                    if len(p) >= 5:
                        c_id, c_name, c_cpu, c_mem, c_pct = p[0], p[1], p[2], p[3], p[4]
                        meta = ps_meta.get(c_name, {'status': 'Up', 'ports': '-'})
                        mem_b = self._parse_mem(c_mem)
                        with self.lock:
                            self.containers[c_name] = {
                                'id': c_id,
                                'name': c_name,
                                'cpu': c_cpu,
                                'cpu_val': float(c_cpu.replace("%", "").strip() or 0.0),
                                'mem_str': c_mem.split("/")[0].strip(),
                                'mem_bytes': mem_b,
                                'status': meta.get('status', 'Up'),
                                'ports': meta.get('ports', '-'),
                                'image': meta.get('image', '')
                            }
                proc.terminate()
            except Exception:
                time.sleep(2)

    def get_containers(self):
        with self.lock:
            return list(self.containers.values())

# -----------------------------------------------------------------------------
# Janela Principal do Monitor
# -----------------------------------------------------------------------------
class SystemMonitorWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="🐍 Surucucu — Observability Cockpit")
        self.set_default_size(560, 740)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Carregar preferências salvas
        self.user_cfg = load_config()
        self.opacity_val = self.user_cfg.get("opacity", 82)
        self.is_pinned = self.user_cfg.get("pinned", True)

        # Histórico de VRAM dos últimos 30 segundos (para Sparklines)
        self.vram_history = [0.0] * 24

        # Definir ícone personalizado
        self.setup_icon()

        # Visual RGBA para efeito Glassmorphism
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
        
        self.set_keep_above(self.is_pinned)
        
        # Filtros de visualização: 'ai', 'docker', 'dev', 'all'
        self.filter_mode = "ai"
        self.search_query = ""
        self.is_compact = False
        
        # Iniciar monitor de contêineres Docker
        self.docker_worker = DockerMonitorWorker()
        self.gpu_vram_map = {}  # {pid: {'vram': mib, 'type': 'C'/'G'}}

        # Estado da linha selecionada (para não perder seleção nos refreshes de 1.2s)
        self.selected_item_id = None
        self.selected_item_name = None
        self.selected_is_docker = False

        self.apply_css(self.opacity_val)
        self.setup_ui()
        
        # Timer de atualização periódica (1.2 segundos para responsividade ágil de dev)
        GLib.timeout_add(1200, self.update_metrics)
        self.update_metrics()

    def apply_css(self, opacity=None):
        if opacity is not None:
            self.opacity_val = int(opacity)
        
        screen = Gdk.Screen.get_default()
        if not hasattr(self, 'css_provider'):
            self.css_provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_screen(
                screen, self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        
        css_content = generate_css(self.opacity_val)
        self.css_provider.load_from_data(css_content.encode("utf-8"))

    def get_icon_path(self):
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

    def setup_icon(self):
        self.set_wmclass("surucucu", "Surucucu")
        self.set_role("surucucu")
        icon_path = self.get_icon_path()
        if icon_path:
            try:
                self.set_icon_from_file(icon_path)
                Gtk.Window.set_default_icon_from_file(icon_path)
            except Exception:
                pass
        self.set_icon_name("surucucu")
        Gtk.Window.set_default_icon_name("surucucu")

    def setup_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(self.main_box)

        # ---------------- HEADER BAR ----------------
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.get_style_context().add_class("header-box")
        
        # Logo visual da marca no cabeçalho
        icon_path = self.get_icon_path()
        if icon_path:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 28, 28, True)
                brand_img = Gtk.Image.new_from_pixbuf(pixbuf)
                brand_img.set_margin_start(2)
                brand_img.set_margin_end(2)
                header.pack_start(brand_img, False, False, 0)
            except Exception:
                pass

        titles_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        lbl_title = Gtk.Label(label="SURUCUCU")
        lbl_title.set_xalign(0)
        lbl_title.get_style_context().add_class("title-label")
        
        self.lbl_subtitle = Gtk.Label(label="Cockpit de Observabilidade de IA • Docker • VRAM • Sistema")
        self.lbl_subtitle.set_xalign(0)
        self.lbl_subtitle.get_style_context().add_class("subtitle-label")
        
        titles_box.pack_start(lbl_title, False, False, 0)
        titles_box.pack_start(self.lbl_subtitle, False, False, 0)
        header.pack_start(titles_box, True, True, 0)

        # Controle Deslizante de Transparência Glass
        glass_ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        glass_ctrl.set_tooltip_text("Ajustar transparência do efeito Glass")
        lbl_glass_icon = Gtk.Label(label="🪟")
        glass_ctrl.pack_start(lbl_glass_icon, False, False, 0)

        self.scale_opacity = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 15, 100, 1)
        self.scale_opacity.set_value(self.opacity_val)
        self.scale_opacity.set_size_request(70, -1)
        self.scale_opacity.set_draw_value(False)
        self.scale_opacity.connect("value-changed", self.on_opacity_slider_changed)
        glass_ctrl.pack_start(self.scale_opacity, False, False, 0)

        self.lbl_opacity_txt = Gtk.Label(label=f"{self.opacity_val}%")
        self.lbl_opacity_txt.get_style_context().add_class("card-val-sub")
        self.lbl_opacity_txt.set_size_request(32, -1)
        glass_ctrl.pack_start(self.lbl_opacity_txt, False, False, 0)

        header.pack_start(glass_ctrl, False, False, 2)

        # Botão Compactar
        self.btn_compact = Gtk.Button(label="↕ Mini")
        self.btn_compact.set_tooltip_text("Alternar modo mini/completo")
        self.btn_compact.connect("clicked", self.toggle_compact)
        header.pack_start(self.btn_compact, False, False, 0)

        # Botão Pin (Always on top)
        self.btn_pin = Gtk.Button(label="📌 Fixado" if self.is_pinned else "📌 Livre")
        if self.is_pinned:
            self.btn_pin.get_style_context().add_class("active")
        self.btn_pin.set_tooltip_text("Manter janela sempre suspensa")
        self.btn_pin.connect("clicked", self.toggle_pin)
        header.pack_start(self.btn_pin, False, False, 0)

        # Botão Limpar RAM
        btn_clean = Gtk.Button(label="🧹 Limpar")
        btn_clean.get_style_context().add_class("btn-clean")
        btn_clean.set_tooltip_text("Liberar PageCache e Buffers de RAM")
        btn_clean.connect("clicked", self.on_clean_ram_clicked)
        header.pack_start(btn_clean, False, False, 0)

        self.main_box.pack_start(header, False, False, 0)

        # ---------------- CARDS DE HARDWARE & IA ----------------
        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.cards_box.set_margin_top(4)
        self.cards_box.set_margin_bottom(4)
        self.main_box.pack_start(self.cards_box, False, False, 0)

        # CARD 1: GPU & VRAM ENGINE (Foco em IA e Risco OOM)
        gpu_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        # CARD 1: GPU & VRAM ENGINE (Foco em IA e Risco OOM)
        gpu_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        gpu_card.get_style_context().add_class("card")

        gpu_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl_gpu_title = Gtk.Label(label="🎮 GPU & VRAM ENGINE (RTX 3050 - 6GB)")
        lbl_gpu_title.get_style_context().add_class("card-title")
        self.lbl_vram_status = Gtk.Label(label="--")
        self.lbl_vram_status.get_style_context().add_class("card-val-big")
        gpu_head.pack_start(lbl_gpu_title, False, False, 0)
        gpu_head.pack_end(self.lbl_vram_status, False, False, 0)
        gpu_card.pack_start(gpu_head, False, False, 0)

        self.bar_vram = Gtk.ProgressBar()
        self.bar_vram.set_show_text(False)
        gpu_card.pack_start(self.bar_vram, False, False, 2)

        # Histórico Sparkline com Linha de Base Visível
        spark_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_spark_title = Gtk.Label(label="📈 VRAM Trend (30s):")
        lbl_spark_title.get_style_context().add_class("card-val-sub")
        self.lbl_vram_sparkline = Gtk.Label()
        self.lbl_vram_sparkline.set_use_markup(True)
        self.lbl_vram_sparkline.get_style_context().add_class("sparkline-label")
        self.lbl_vram_sparkline.set_markup("<span color='#475569'>                        </span>")
        self.lbl_oom_alert = Gtk.Label(label="🟢 VRAM Segura")
        self.lbl_oom_alert.get_style_context().add_class("tag-alert-ok")
        spark_box.pack_start(lbl_spark_title, False, False, 0)
        spark_box.pack_start(self.lbl_vram_sparkline, False, False, 0)
        spark_box.pack_end(self.lbl_oom_alert, False, False, 0)
        gpu_card.pack_start(spark_box, False, False, 1)

        # Grade de Telemetria Avançada (Badges Estilizadas)
        telemetry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Badge CUDA
        b_cuda = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_cuda.get_style_context().add_class("telemetry-badge")
        self.lbl_tel_cuda = Gtk.Label()
        self.lbl_tel_cuda.set_use_markup(True)
        self.lbl_tel_cuda.set_markup("⚡ <b>CUDA:</b> 0%")
        b_cuda.pack_start(self.lbl_tel_cuda, True, True, 0)
        telemetry_box.pack_start(b_cuda, True, True, 0)

        # Badge Memory Bus
        b_bus = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_bus.get_style_context().add_class("telemetry-badge")
        self.lbl_tel_bus = Gtk.Label()
        self.lbl_tel_bus.set_use_markup(True)
        self.lbl_tel_bus.set_markup("🔄 <b>Bus:</b> 0%")
        b_bus.pack_start(self.lbl_tel_bus, True, True, 0)
        telemetry_box.pack_start(b_bus, True, True, 0)

        # Badge PCIe Throughput
        b_pcie = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_pcie.get_style_context().add_class("telemetry-badge")
        self.lbl_tel_pcie = Gtk.Label()
        self.lbl_tel_pcie.set_use_markup(True)
        self.lbl_tel_pcie.set_markup("🚀 <b>PCIe:</b> ↑0M ↓0M")
        b_pcie.pack_start(self.lbl_tel_pcie, True, True, 0)
        telemetry_box.pack_start(b_pcie, True, True, 0)

        # Badge Temp / Watts
        b_hw = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_hw.get_style_context().add_class("telemetry-badge")
        self.lbl_tel_hw = Gtk.Label()
        self.lbl_tel_hw.set_use_markup(True)
        self.lbl_tel_hw.set_markup("🌡️ <b>--°C</b> • <b>--W</b>")
        b_hw.pack_start(self.lbl_tel_hw, True, True, 0)
        telemetry_box.pack_start(b_hw, True, True, 0)

        gpu_card.pack_start(telemetry_box, False, False, 2)
        self.cards_box.pack_start(gpu_card, False, False, 0)

        # CARD 2: RAM DO SISTEMA & SWAP (Offload de Modelos)
        ram_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        ram_card.get_style_context().add_class("card")
        
        ram_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl_ram_title = Gtk.Label(label="🧠 MEMÓRIA RAM & SWAP")
        lbl_ram_title.get_style_context().add_class("card-title")
        self.lbl_ram_values = Gtk.Label(label="-- / --")
        self.lbl_ram_values.get_style_context().add_class("card-val-big")
        ram_head.pack_start(lbl_ram_title, False, False, 0)
        ram_head.pack_end(self.lbl_ram_values, False, False, 0)
        ram_card.pack_start(ram_head, False, False, 0)

        self.bar_ram = Gtk.ProgressBar()
        self.bar_ram.set_show_text(False)
        ram_card.pack_start(self.bar_ram, False, False, 2)

        ram_details = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.lbl_ram_details = Gtk.Label(label="Livre: -- | Cache: --")
        self.lbl_ram_details.get_style_context().add_class("card-val-sub")
        self.lbl_swap = Gtk.Label(label="SWAP: --")
        self.lbl_swap.get_style_context().add_class("card-val-sub")
        ram_details.pack_start(self.lbl_ram_details, False, False, 0)
        ram_details.pack_end(self.lbl_swap, False, False, 0)
        ram_card.pack_start(ram_details, False, False, 0)

        self.cards_box.pack_start(ram_card, False, False, 0)

        # CARD 3: RESUMO DE IA & DOCKER FOOTPRINT (Badges de Alta Visibilidade)
        stack_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        stack_card.get_style_context().add_class("card")
        
        # Badge 1: Containers
        b_cnt = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_cnt.get_style_context().add_class("telemetry-badge")
        self.lbl_ai_cnt = Gtk.Label()
        self.lbl_ai_cnt.set_use_markup(True)
        self.lbl_ai_cnt.set_markup("🐳 <b>0 Containers</b>")
        b_cnt.pack_start(self.lbl_ai_cnt, True, True, 0)
        stack_card.pack_start(b_cnt, True, True, 0)

        # Badge 2: RAM IA
        b_ram = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_ram.get_style_context().add_class("telemetry-badge")
        self.lbl_ai_ram = Gtk.Label()
        self.lbl_ai_ram.set_use_markup(True)
        self.lbl_ai_ram.set_markup("🧠 <b>RAM IA:</b> 0 MB")
        b_ram.pack_start(self.lbl_ai_ram, True, True, 0)
        stack_card.pack_start(b_ram, True, True, 0)

        # Badge 3: VRAM IA
        b_vram = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_vram.get_style_context().add_class("telemetry-badge")
        self.lbl_ai_vram = Gtk.Label()
        self.lbl_ai_vram.set_use_markup(True)
        self.lbl_ai_vram.set_markup("🎮 <b>VRAM IA:</b> 0 MB")
        b_vram.pack_start(self.lbl_ai_vram, True, True, 0)
        stack_card.pack_start(b_vram, True, True, 0)

        self.cards_box.pack_start(stack_card, False, False, 0)

        # ---------------- SEÇÃO DE PROCESSOS & CONTAINERS ----------------
        self.proc_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.proc_section.set_margin_start(10)
        self.proc_section.set_margin_end(10)
        self.proc_section.set_margin_bottom(8)

        # Barra de Filtros Rápidos
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        self.btn_filter_ai = Gtk.Button(label="🤖 Stack de IA")
        self.btn_filter_ai.get_style_context().add_class("active")
        self.btn_filter_ai.connect("clicked", lambda b: self.set_filter("ai"))
        toolbar.pack_start(self.btn_filter_ai, False, False, 0)

        self.btn_filter_docker = Gtk.Button(label="🐳 Docker")
        self.btn_filter_docker.connect("clicked", lambda b: self.set_filter("docker"))
        toolbar.pack_start(self.btn_filter_docker, False, False, 0)

        self.btn_filter_dev = Gtk.Button(label="🚀 Scripts & Dev")
        self.btn_filter_dev.connect("clicked", lambda b: self.set_filter("dev"))
        toolbar.pack_start(self.btn_filter_dev, False, False, 0)

        self.btn_filter_all = Gtk.Button(label="📈 Top RAM")
        self.btn_filter_all.connect("clicked", lambda b: self.set_filter("all"))
        toolbar.pack_start(self.btn_filter_all, False, False, 0)

        # Campo de Busca
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("🔍 Filtrar container, modelo, porta ou PID...")
        self.search_entry.connect("changed", self.on_search_changed)
        toolbar.pack_end(self.search_entry, True, True, 0)

        self.proc_section.pack_start(toolbar, False, False, 0)

        # Tabela de Observabilidade
        # Colunas:
        # 0: PID/ID (str), 1: Tag (str), 2: Nome (str), 3: Detalhe/Portas (str),
        # 4: VRAM_val (float), 5: VRAM_str (str), 6: RAM_val (float), 7: RAM_str (str), 8: CPU_val (float), 9: CPU_str (str), 10: is_docker (bool)
        self.proc_store = Gtk.ListStore(str, str, str, str, float, str, float, str, float, str, bool)
        self.treeview = Gtk.TreeView(model=self.proc_store)

        # Coluna Tipo/Tag
        col_tag = Gtk.TreeViewColumn("Tipo", Gtk.CellRendererText(), text=1)
        col_tag.set_min_width(55)
        self.treeview.append_column(col_tag)

        # Coluna Nome / Container
        col_name = Gtk.TreeViewColumn("Container / Modelo / Processo", Gtk.CellRendererText(), text=2)
        col_name.set_sort_column_id(2)
        col_name.set_expand(True)
        self.treeview.append_column(col_name)

        # Coluna Portas / Projeto
        col_ports = Gtk.TreeViewColumn("Portas / Projeto", Gtk.CellRendererText(), text=3)
        col_ports.set_min_width(110)
        self.treeview.append_column(col_ports)

        # Coluna VRAM (GPU) - Destaque crucial para IA
        col_vram = Gtk.TreeViewColumn("VRAM (GPU)", Gtk.CellRendererText(), text=5)
        col_vram.set_sort_column_id(4)
        col_vram.set_min_width(75)
        self.treeview.append_column(col_vram)

        # Coluna RAM (Sistema)
        col_ram = Gtk.TreeViewColumn("RAM", Gtk.CellRendererText(), text=7)
        col_ram.set_sort_column_id(6)
        col_ram.set_min_width(65)
        self.treeview.append_column(col_ram)

        # Coluna CPU
        col_cpu = Gtk.TreeViewColumn("CPU", Gtk.CellRendererText(), text=9)
        col_cpu.set_sort_column_id(8)
        col_cpu.set_min_width(50)
        self.treeview.append_column(col_cpu)

        # Configurar seleção do TreeView
        self.selection = self.treeview.get_selection()
        self.selection.set_mode(Gtk.SelectionMode.SINGLE)
        self.selection.connect("changed", self.on_selection_changed)
        self.treeview.connect("row-activated", self.on_row_activated)

        # Scroll
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scroller.add(self.treeview)
        scroller.set_vexpand(True)
        self.proc_section.pack_start(scroller, True, True, 0)

        # Rodapé de Ações
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.lbl_proc_count = Gtk.Label(label="Carregando observabilidade...")
        self.lbl_proc_count.get_style_context().add_class("card-val-sub")
        action_bar.pack_start(self.lbl_proc_count, False, False, 0)

        # Botão Reiniciar Container (para Docker)
        self.btn_restart = Gtk.Button(label="🔄 Reiniciar Container")
        self.btn_restart.get_style_context().add_class("btn-restart")
        self.btn_restart.set_tooltip_text("Selecione um container na tabela acima para reiniciar")
        self.btn_restart.connect("clicked", self.on_restart_container_clicked)
        action_bar.pack_end(self.btn_restart, False, False, 0)

        # Botão Parar / Encerrar
        self.btn_kill = Gtk.Button(label="⏹️ Parar / Finalizar")
        self.btn_kill.get_style_context().add_class("btn-kill")
        self.btn_kill.set_tooltip_text("Selecione um container ou processo para finalizar")
        self.btn_kill.connect("clicked", self.on_kill_selected_clicked)
        action_bar.pack_end(self.btn_kill, False, False, 0)

        self.proc_section.pack_start(action_bar, False, False, 0)
        self.main_box.pack_start(self.proc_section, True, True, 0)

    # ---------------- CONTROLES & HANDLERS ----------------
    def on_selection_changed(self, selection):
        model, tree_iter = selection.get_selected()
        if tree_iter:
            self.selected_item_id = model.get_value(tree_iter, 0)
            self.selected_item_name = model.get_value(tree_iter, 2)
            self.selected_is_docker = model.get_value(tree_iter, 10)
        self.update_action_buttons()

    def update_action_buttons(self):
        if self.selected_item_id and self.selected_item_name:
            short_name = (self.selected_item_name[:15] + "..") if len(self.selected_item_name) > 17 else self.selected_item_name
            if self.selected_is_docker:
                self.btn_restart.set_sensitive(True)
                self.btn_restart.set_label(f"🔄 Reiniciar '{short_name}'")
                self.btn_kill.set_sensitive(True)
                self.btn_kill.set_label(f"⏹️ Parar '{short_name}'")
            else:
                self.btn_restart.set_sensitive(False)
                self.btn_restart.set_label("🔄 Reiniciar Container")
                self.btn_kill.set_sensitive(True)
                self.btn_kill.set_label(f"⏹️ Finalizar PID {self.selected_item_id}")
        else:
            self.btn_restart.set_sensitive(True)
            self.btn_restart.set_label("🔄 Reiniciar Container")
            self.btn_kill.set_sensitive(True)
            self.btn_kill.set_label("⏹️ Parar / Finalizar")

    def on_row_activated(self, treeview, path, column):
        model = treeview.get_model()
        tree_iter = model.get_iter(path)
        if tree_iter:
            is_docker = model.get_value(tree_iter, 10)
            if is_docker:
                self.on_restart_container_clicked(None)
            else:
                self.on_kill_selected_clicked(None)

    def on_opacity_slider_changed(self, scale):
        val = int(scale.get_value())
        self.lbl_opacity_txt.set_text(f"{val}%")
        self.apply_css(opacity=val)
        self.save_user_settings()

    def save_user_settings(self):
        self.user_cfg["opacity"] = self.opacity_val
        self.user_cfg["pinned"] = self.is_pinned
        save_config(self.user_cfg)

    def toggle_pin(self, widget):
        self.is_pinned = not self.is_pinned
        self.set_keep_above(self.is_pinned)
        if self.is_pinned:
            self.btn_pin.set_label("📌 Fixado")
            self.btn_pin.get_style_context().add_class("active")
        else:
            self.btn_pin.set_label("📌 Livre")
            self.btn_pin.get_style_context().remove_class("active")
        self.save_user_settings()

    def toggle_compact(self, widget):
        self.is_compact = not self.is_compact
        if self.is_compact:
            self.proc_section.hide()
            self.btn_compact.set_label("↕ Expandir")
            self.resize(420, 210)
        else:
            self.proc_section.show()
            self.btn_compact.set_label("↕ Mini")
            self.resize(560, 720)

    def set_filter(self, mode):
        self.filter_mode = mode
        self.btn_filter_ai.get_style_context().remove_class("active")
        self.btn_filter_docker.get_style_context().remove_class("active")
        self.btn_filter_dev.get_style_context().remove_class("active")
        self.btn_filter_all.get_style_context().remove_class("active")

        if mode == "ai":
            self.btn_filter_ai.get_style_context().add_class("active")
        elif mode == "docker":
            self.btn_filter_docker.get_style_context().add_class("active")
        elif mode == "dev":
            self.btn_filter_dev.get_style_context().add_class("active")
        else:
            self.btn_filter_all.get_style_context().add_class("active")
        
        self.update_processes()

    def on_search_changed(self, entry):
        self.search_query = entry.get_text().strip().lower()
        self.update_processes()

    # ---------------- MÉTRICAS EM TEMPO REAL ----------------
    def update_metrics(self):
        try:
            # 1. RAM e SWAP
            vm = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            ram_used_str = format_bytes(vm.used)
            ram_total_str = format_bytes(vm.total)
            ram_pct = vm.percent
            self.lbl_ram_values.set_text(f"{ram_used_str} / {ram_total_str} ({ram_pct:.0f}%)")
            self.bar_ram.set_fraction(ram_pct / 100.0)
            
            ctx_ram = self.bar_ram.get_style_context()
            ctx_ram.remove_class("meter-warning")
            ctx_ram.remove_class("meter-danger")
            if ram_pct >= 85:
                ctx_ram.add_class("meter-danger")
            elif ram_pct >= 65:
                ctx_ram.add_class("meter-warning")

            cache_val = getattr(vm, 'cached', 0) + getattr(vm, 'buffers', 0)
            self.lbl_ram_details.set_text(f"Livre: {format_bytes(vm.available)} | Cache: {format_bytes(cache_val)}")
            self.lbl_swap.set_text(f"SWAP: {format_bytes(swap.used)} / {format_bytes(swap.total)} ({swap.percent:.0f}%)")

            # 2. GPU & VRAM (Detecção e Alerta OOM)
            self.update_gpu_metrics()

            # 3. Processos e Containers
            if not self.is_compact:
                self.update_processes()

        except Exception as e:
            print(f"Erro ao atualizar métricas: {e}", file=sys.stderr)

        return True

    def update_gpu_metrics(self):
        vram_used = 0.0
        vram_total = 6144.0
        gpu_util = 0.0
        mem_bus_util = 0.0
        temp = 0
        power = "0"

        # 1. Consulta geral de GPU com Utilização de Computação CUDA e Memory Bus
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=1
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split("\n")[0].split(",")]
                gpu_util = float(parts[0])
                mem_bus_util = float(parts[1])
                vram_used = float(parts[2])
                vram_total = float(parts[3])
                temp = int(parts[4])
                power = parts[5]
        except Exception:
            pass

        # 2. Telemetria PCIe Throughput (TX/RX em MB/s)
        rx_pci, tx_pci = 0, 0
        try:
            res_dmon = subprocess.run(["nvidia-smi", "dmon", "-s", "t", "-c", "1"], capture_output=True, text=True, timeout=1)
            lines = [l.strip() for l in res_dmon.stdout.strip().split('\n') if l.strip() and not l.startswith('#')]
            if lines:
                parts = lines[-1].split()
                if len(parts) >= 3:
                    rx_pci, tx_pci = int(parts[1]), int(parts[2])
        except Exception:
            pass

        # 3. Mapeamento de VRAM por Processo e Tipo (C = Compute/CUDA, G = Graphics)
        self.gpu_vram_map = {}
        try:
            res_pids = subprocess.run(["nvidia-smi", "-q", "-d", "PIDS"], capture_output=True, text=True, timeout=1)
            if res_pids.returncode == 0:
                current_pid = None
                current_type = "G"
                for line in res_pids.stdout.split("\n"):
                    line = line.strip()
                    m_pid = re.match(r"Process ID\s*:\s*(\d+)", line)
                    if m_pid:
                        current_pid = int(m_pid.group(1))
                        current_type = "G"
                        continue
                    m_type = re.match(r"Type\s*:\s*([CG])", line)
                    if m_type:
                        current_type = m_type.group(1)
                        continue
                    m_mem = re.match(r"Used GPU Memory\s*:\s*(\d+)\s*MiB", line)
                    if m_mem and current_pid:
                        self.gpu_vram_map[current_pid] = {
                            'vram': int(m_mem.group(1)),
                            'type': current_type
                        }
                        current_pid = None
        except Exception:
            pass

        vram_pct = (vram_used / vram_total * 100.0) if vram_total > 0 else 0.0
        self.lbl_vram_status.set_text(f"VRAM: {vram_used:.0f} MB / {vram_total:.0f} MB ({vram_pct:.0f}%)")
        self.bar_vram.set_fraction(min(1.0, vram_pct / 100.0))

        # Atualizar Sparkline de Histórico dos últimos 30s
        self.vram_history.append(vram_pct)
        if len(self.vram_history) > 24:
            self.vram_history.pop(0)
        self.lbl_vram_sparkline.set_markup(make_sparkline(self.vram_history))

        # Alerta de OOM e Cores de Risco
        ctx = self.bar_vram.get_style_context()
        ctx.remove_class("meter-warning")
        ctx.remove_class("meter-danger")
        ctx_alert = self.lbl_oom_alert.get_style_context()
        ctx_alert.remove_class("tag-alert-ok")
        ctx_alert.remove_class("tag-alert-warn")
        ctx_alert.remove_class("tag-alert-danger")

        if vram_pct >= 88.0:
            ctx.add_class("meter-danger")
            ctx_alert.add_class("tag-alert-danger")
            self.lbl_oom_alert.set_text("⚠️ RISCO CRÍTICO DE OOM")
        elif vram_pct >= 70.0:
            ctx.add_class("meter-warning")
            ctx_alert.add_class("tag-alert-warn")
            self.lbl_oom_alert.set_text("🟡 VRAM em Carga Alta")
        else:
            ctx_alert.add_class("tag-alert-ok")
            self.lbl_oom_alert.set_text("🟢 VRAM Segura")

        # Alerta de Throttling Térmico e Saturação de Barramento
        throttling_txt = " 🔥" if temp >= 78 else ""
        mem_bound_txt = " ⚠️" if (mem_bus_util > 75 and gpu_util < 45) else ""
        
        # Atualizar Badges Individuais de Telemetria com Cores e Destaque
        self.lbl_tel_cuda.set_markup(f"⚡ <b>CUDA:</b> <span color='#38bdf8'>{gpu_util:.0f}%</span>")
        self.lbl_tel_bus.set_markup(f"🔄 <b>Bus:</b> <span color='#38bdf8'>{mem_bus_util:.0f}%</span>{mem_bound_txt}")
        self.lbl_tel_pcie.set_markup(f"🚀 <b>PCIe:</b> ↑<span color='#38bdf8'>{tx_pci}M</span> ↓<span color='#38bdf8'>{rx_pci}M</span>")
        self.lbl_tel_hw.set_markup(f"🌡️ <b>{temp}°C</b>{throttling_txt} • <b>{power}W</b>")

    def update_processes(self):
        containers = self.docker_worker.get_containers()
        items = []

        # 1. Contêineres Docker
        total_docker_ram = 0.0
        total_ai_ram = 0.0
        total_ai_vram = 0.0

        for c in containers:
            total_docker_ram += c['mem_bytes']
            is_ai = is_ai_target(c['name'], "", c['ports'], c.get('image', ''))
            if is_ai:
                total_ai_ram += c['mem_bytes']

            # Filtros
            if self.filter_mode == "ai" and not is_ai:
                continue
            elif self.filter_mode == "dev" and not is_dev_target(c['name'], "", "", ""):
                continue

            tag = "🤖 AI" if is_ai else "🐳 Docker"
            
            # Checar filtro de texto
            if self.search_query:
                query_match = (
                    self.search_query in c['name'].lower() or
                    self.search_query in c['ports'].lower() or
                    self.search_query in c['id'].lower() or
                    self.search_query in tag.lower()
                )
                if not query_match:
                    continue

            items.append({
                'id_str': c['id'][:10],
                'tag': tag,
                'name': c['name'],
                'detail': f"Portas {c['ports']}" if c['ports'] != '-' else c['status'],
                'vram_val': 0.0,
                'vram_str': "-",
                'ram_val': c['mem_bytes'],
                'ram_str': c['mem_str'],
                'cpu_val': c['cpu_val'],
                'cpu_str': c['cpu'],
                'is_docker': True
            })

        # 2. Processos Locais e Modelos (psutil)
        attrs = ['pid', 'name', 'cmdline', 'memory_info', 'cpu_percent', 'cwd', 'username']
        for p in psutil.process_iter(attrs):
            try:
                info = p.info
                pid = info['pid']
                name = info['name'] or ''
                cmdline_list = info.get('cmdline') or []
                cmdline = " ".join(cmdline_list)
                cwd = info.get('cwd') or '-'
                rss = (info['memory_info'].rss if info['memory_info'] else 0)
                cpu = info.get('cpu_percent') or 0.0

                gpu_meta = self.gpu_vram_map.get(pid, {})
                vram_mib = gpu_meta.get('vram', 0)
                gpu_proc_type = gpu_meta.get('type', '')

                is_gpu_gui = gpu_proc_type == 'G' or name.lower().startswith("gnome") or "xorg" in name.lower() or "wayland" in name.lower()
                if vram_mib > 0 and not is_gpu_gui:
                    total_ai_vram += vram_mib * (1024 ** 2)

                is_ai = (is_ai_target(name, cmdline) or gpu_proc_type == 'C') and not is_gpu_gui
                is_dev = is_dev_target(name, cmdline, cwd, info.get('username') or '')
                is_svc = is_service_target(name, cmdline, info.get('username') or '')

                if is_ai:
                    total_ai_ram += rss

                # Aplicação do modo de filtro
                if self.filter_mode == "ai" and not is_ai:
                    continue
                elif self.filter_mode == "docker":
                    continue  # Somente contêineres na aba docker
                elif self.filter_mode == "dev" and not is_dev:
                    continue
                elif self.filter_mode == "all" and rss < (20 * 1024 * 1024) and vram_mib == 0:
                    continue  # Ignora processos insignificantes

                # Nome e detalhes limpos
                display_name = name
                if len(cmdline_list) > 1 and name.lower() in ["python", "python3", "node", "bash", "sh"]:
                    script_part = os.path.basename(cmdline_list[1])
                    display_name = f"{name} ({script_part})"

                short_cwd = cwd.replace(os.path.expanduser("~"), "~")
                
                # Tag refinada: se for CUDA Compute, destaca explicitamente!
                if gpu_proc_type == 'C':
                    tag = "🤖 [CUDA C]"
                elif gpu_proc_type == 'G':
                    tag = "🎨 [GPU G]"
                elif is_ai:
                    tag = "🤖 AI"
                elif is_dev:
                    tag = "🚀 Dev"
                else:
                    tag = "⚙️ Svc"

                if self.search_query:
                    match = (
                        self.search_query in display_name.lower() or
                        self.search_query in cmdline.lower() or
                        self.search_query in short_cwd.lower() or
                        self.search_query in str(pid) or
                        self.search_query in tag.lower()
                    )
                    if not match:
                        continue

                items.append({
                    'id_str': str(pid),
                    'tag': tag,
                    'name': display_name,
                    'detail': short_cwd if short_cwd != '-' else (cmdline[:45] + '...'),
                    'vram_val': float(vram_mib),
                    'vram_str': format_mib(vram_mib),
                    'ram_val': float(rss),
                    'ram_str': format_bytes(rss),
                    'cpu_val': cpu,
                    'cpu_str': f"{cpu:.1f}%",
                    'is_docker': False
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Ordenação prioritária: quem consome VRAM primeiro, depois maior RAM
        items.sort(key=lambda x: (x['vram_val'], x['ram_val']), reverse=True)
        top_items = items[:60]

        # Salva o ID selecionado antes da atualização para não perder a seleção nos refreshes
        selection = self.treeview.get_selection()
        model, current_iter = selection.get_selected()
        if current_iter:
            self.selected_item_id = model.get_value(current_iter, 0)
            self.selected_item_name = model.get_value(current_iter, 2)
            self.selected_is_docker = model.get_value(current_iter, 10)

        self.proc_store.clear()
        selected_iter_to_restore = None
        for it in top_items:
            row_iter = self.proc_store.append([
                it['id_str'],
                it['tag'],
                it['name'],
                it['detail'],
                it['vram_val'],
                it['vram_str'],
                it['ram_val'],
                it['ram_str'],
                it['cpu_val'],
                it['cpu_str'],
                it['is_docker']
            ])
            if self.selected_item_id and it['id_str'] == self.selected_item_id:
                selected_iter_to_restore = row_iter

        if selected_iter_to_restore:
            selection.select_iter(selected_iter_to_restore)
        self.update_action_buttons()

        # Atualizar Card Resumo da Stack de IA & Docker (Badges Individuais)
        total_cnt = len(containers)
        self.lbl_ai_cnt.set_markup(f"🐳 <b>{total_cnt} Containers</b>")
        self.lbl_ai_ram.set_markup(f"🧠 <b>RAM IA:</b> <span color='#34d399'>{format_bytes(total_ai_ram)}</span>")
        self.lbl_ai_vram.set_markup(f"🎮 <b>VRAM IA:</b> <span color='#38bdf8'>{format_bytes(total_ai_vram)}</span>")
        self.lbl_proc_count.set_text(f"Exibindo {len(top_items)} itens ({self.filter_mode.upper()})")

    # ---------------- AÇÕES DE PARADA & REINICIALIZAÇÃO ----------------
    def on_clean_ram_clicked(self, widget):
        cmd = "sync; echo 3 > /proc/sys/vm/drop_caches"
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Liberar Memória RAM agora?"
        )
        dialog.format_secondary_text("Sincroniza os discos e limpa caches e buffers do Linux.")
        resp = dialog.run()
        dialog.destroy()
        if resp == Gtk.ResponseType.YES:
            subprocess.Popen(["pkexec", "sh", "-c", cmd])
            self.update_metrics()

    def on_restart_container_clicked(self, widget):
        selection = self.treeview.get_selection()
        model, tree_iter = selection.get_selected()

        is_docker = self.selected_is_docker
        c_name = self.selected_item_name

        if tree_iter:
            is_docker = model.get_value(tree_iter, 10)
            c_name = model.get_value(tree_iter, 2)

        if not c_name or not self.selected_item_id:
            dlg = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Nenhum item selecionado"
            )
            dlg.format_secondary_text("Clique em um container na tabela acima para selecioná-lo antes de reiniciar.")
            dlg.run()
            dlg.destroy()
            return

        if not is_docker:
            dlg = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Ação disponível apenas para Containers Docker"
            )
            dlg.format_secondary_text(f"'{c_name}' é um processo do sistema, não um container Docker.")
            dlg.run()
            dlg.destroy()
            return

        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Reiniciar container '{c_name}'?"
        )
        dialog.format_secondary_text("O container será reiniciado via 'docker restart'.")
        resp = dialog.run()
        dialog.destroy()
        if resp == Gtk.ResponseType.YES:
            subprocess.Popen(["docker", "restart", c_name])

    def on_kill_selected_clicked(self, widget):
        selection = self.treeview.get_selection()
        model, tree_iter = selection.get_selected()

        item_id = self.selected_item_id
        item_name = self.selected_item_name
        is_docker = self.selected_is_docker

        if tree_iter:
            item_id = model.get_value(tree_iter, 0)
            item_name = model.get_value(tree_iter, 2)
            is_docker = model.get_value(tree_iter, 10)

        if not item_name or not item_id:
            dlg = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Nenhum item selecionado"
            )
            dlg.format_secondary_text("Clique em um container ou processo na tabela acima para selecioná-lo antes de finalizar.")
            dlg.run()
            dlg.destroy()
            return

        action_msg = f"parar o container Docker '{item_name}'" if is_docker else f"encerrar o processo '{item_name}' (PID {item_id})"
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Deseja realmente {action_msg}?"
        )
        resp = dialog.run()
        dialog.destroy()

        if resp == Gtk.ResponseType.YES:
            if is_docker:
                subprocess.Popen(["docker", "stop", item_name])
            else:
                try:
                    proc = psutil.Process(int(item_id))
                    proc.terminate()
                except Exception:
                    subprocess.Popen(["pkexec", "kill", "-9", str(item_id)])
            self.update_processes()

def main():
    GLib.set_prgname("surucucu")
    GLib.set_application_name("Surucucu")

    win = SystemMonitorWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    win.present()
    win.set_keep_above(True)
    Gtk.main()

if __name__ == "__main__":
    main()
