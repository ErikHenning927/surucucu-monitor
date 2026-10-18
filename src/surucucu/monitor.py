#!/usr/bin/env python3
"""
🐍 Surucucu - AI & Dev Observability Cockpit
Monitor de Desenvolvimento focado em Inteligência Artificial, Modelos Locais, Docker e Recursos de Hardware.
Otimizado para Ubuntu Linux (GNOME / Wayland) com NVIDIA GPU (VRAM/CUDA).
"""

import sys
import psutil
import subprocess

from surucucu.config import (
    load_config,
    save_config,
    get_icon_path,
    CONFIG_DIR,
    CONFIG_FILE,
    LEGACY_CONFIG_FILE
)
from surucucu.styles import generate_css
from surucucu.utils import format_bytes, format_mib, make_sparkline
from surucucu.classifier import (
    is_ai_target,
    is_dev_target,
    is_service_target,
    AI_KEYWORDS,
    DEV_KEYWORDS,
    SERVICE_KEYWORDS
)
from surucucu.docker_worker import DockerMonitorWorker
from surucucu.telemetry import (
    GpuTelemetry,
    query_gpu_telemetry,
    collect_process_items
)

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

        # Definir ícone personalizado e classe WM
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
        self.gpu_telemetry = GpuTelemetry()

        # Estado da linha selecionada (para persistência no ciclo de 1.2s)
        self.selected_item_id = None
        self.selected_item_name = None
        self.selected_is_docker = False

        self.apply_css(self.opacity_val)
        self.setup_ui()
        
        # Timer de atualização periódica (1.2 segundos para agilidade de dev)
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

    def setup_icon(self):
        self.set_wmclass("surucucu", "Surucucu")
        self.set_role("surucucu")
        icon_path = get_icon_path()
        if icon_path:
            try:
                self.set_icon_from_file(icon_path)
                Gtk.Window.set_default_icon_from_file(icon_path)
            except Exception:
                pass
        self.set_icon_name("surucucu")
        Gtk.Window.set_default_icon_name("surucucu")

    # ---------------- ESTRUTURAÇÃO DA UI (MODULAR) ----------------
    def setup_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(self.main_box)

        # 1. Header Bar
        self._build_header()

        # 2. Cards de Hardware & IA
        self._build_hardware_cards()

        # 3. Seção da Tabela de Processos e Contêineres
        self._build_process_section()

    def _build_header(self):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.get_style_context().add_class("header-box")
        
        # Logo visual da marca no cabeçalho
        icon_path = get_icon_path()
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

    def _build_hardware_cards(self):
        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.cards_box.set_margin_top(4)
        self.cards_box.set_margin_bottom(4)
        self.main_box.pack_start(self.cards_box, False, False, 0)

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

    def _build_process_section(self):
        self.proc_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.proc_section.set_margin_start(10)
        self.proc_section.set_margin_end(10)
        self.proc_section.set_margin_bottom(6)

        # Barra de Filtros e Busca
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.btn_filter_ai = Gtk.Button(label="🤖 IA & Modelos")
        self.btn_filter_ai.get_style_context().add_class("active")
        self.btn_filter_ai.connect("clicked", lambda b: self.set_filter("ai"))
        toolbar.pack_start(self.btn_filter_ai, False, False, 0)

        self.btn_filter_docker = Gtk.Button(label="🐳 Containers")
        self.btn_filter_docker.connect("clicked", lambda b: self.set_filter("docker"))
        toolbar.pack_start(self.btn_filter_docker, False, False, 0)

        self.btn_filter_dev = Gtk.Button(label="🚀 Dev & Scripts")
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
        self.selection_handler_id = self.selection.connect("changed", self.on_selection_changed)
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
        else:
            self.selected_item_id = None
            self.selected_item_name = None
            self.selected_is_docker = False
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
                raw_pid = self.selected_item_id.replace("proc:", "")
                self.btn_kill.set_label(f"⏹️ Finalizar PID {raw_pid}")
        else:
            self.btn_restart.set_sensitive(False)
            self.btn_restart.set_label("🔄 Reiniciar Container")
            self.btn_kill.set_sensitive(False)
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
        
        # Resetar seleção ao alternar de aba/filtro
        self.selected_item_id = None
        self.selected_item_name = None
        self.selected_is_docker = False
        self.selection.unselect_all()
        self.update_processes()

    def on_search_changed(self, entry):
        self.search_query = entry.get_text().strip().lower()
        self.update_processes()

    # ---------------- MÉTRICAS EM TEMPO REAL ----------------
    def update_metrics(self):
        try:
            # 1. RAM e SWAP do Sistema
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
        tel = query_gpu_telemetry()
        self.gpu_telemetry = tel

        self.lbl_vram_status.set_text(f"VRAM: {tel.vram_used:.0f} MB / {tel.vram_total:.0f} MB ({tel.vram_pct:.0f}%)")
        self.bar_vram.set_fraction(min(1.0, tel.vram_pct / 100.0))

        # Atualizar Sparkline de Histórico dos últimos 30s
        self.vram_history.append(tel.vram_pct)
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

        if tel.vram_pct >= 88.0:
            ctx.add_class("meter-danger")
            ctx_alert.add_class("tag-alert-danger")
            self.lbl_oom_alert.set_text("⚠️ RISCO CRÍTICO DE OOM")
        elif tel.vram_pct >= 70.0:
            ctx.add_class("meter-warning")
            ctx_alert.add_class("tag-alert-warn")
            self.lbl_oom_alert.set_text("🟡 VRAM em Carga Alta")
        else:
            ctx_alert.add_class("tag-alert-ok")
            self.lbl_oom_alert.set_text("🟢 VRAM Segura")

        # Alerta de Throttling Térmico e Saturação de Barramento
        throttling_txt = " 🔥" if tel.is_throttling else ""
        mem_bound_txt = " ⚠️" if tel.is_mem_bound else ""
        
        # Atualizar Badges Individuais de Telemetria com Cores e Destaque
        self.lbl_tel_cuda.set_markup(f"⚡ <b>CUDA:</b> <span color='#38bdf8'>{tel.gpu_util:.0f}%</span>")
        self.lbl_tel_bus.set_markup(f"🔄 <b>Bus:</b> <span color='#38bdf8'>{tel.mem_bus_util:.0f}%</span>{mem_bound_txt}")
        self.lbl_tel_pcie.set_markup(f"🚀 <b>PCIe:</b> ↑<span color='#38bdf8'>{tel.tx_pci}M</span> ↓<span color='#38bdf8'>{tel.rx_pci}M</span>")
        self.lbl_tel_hw.set_markup(f"🌡️ <b>{tel.temp}°C</b>{throttling_txt} • <b>{tel.power}W</b>")

    def update_processes(self):
        containers = self.docker_worker.get_containers()
        top_items, total_ai_ram, total_ai_vram = collect_process_items(
            self.filter_mode,
            self.search_query,
            containers,
            self.gpu_telemetry.gpu_vram_map
        )

        # Salva o ID selecionado antes da atualização para não perder a seleção nos refreshes
        selection = self.treeview.get_selection()
        model, current_iter = selection.get_selected()
        if current_iter:
            self.selected_item_id = model.get_value(current_iter, 0)
            self.selected_item_name = model.get_value(current_iter, 2)
            self.selected_is_docker = model.get_value(current_iter, 10)

        # Bloqueia temporariamente o handler do sinal 'changed' para evitar que GTK
        # selecione o último item ao limpar e recriar as linhas da tabela
        if hasattr(self, 'selection_handler_id') and self.selection_handler_id:
            self.selection.handler_block(self.selection_handler_id)

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
            self.selection.select_iter(selected_iter_to_restore)
        else:
            self.selected_item_id = None
            self.selected_item_name = None
            self.selected_is_docker = False

        if hasattr(self, 'selection_handler_id') and self.selection_handler_id:
            self.selection.handler_unblock(self.selection_handler_id)

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

        raw_pid = str(item_id).replace("proc:", "").replace("docker:", "")
        action_msg = f"parar o container Docker '{item_name}'" if is_docker else f"encerrar o processo '{item_name}' (PID {raw_pid})"
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
                    proc = psutil.Process(int(raw_pid))
                    proc.terminate()
                except Exception:
                    subprocess.Popen(["pkexec", "kill", "-9", str(raw_pid)])
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
