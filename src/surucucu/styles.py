"""
Geração de folhas de estilo CSS dinâmicas para o HUD Surucucu com efeito Glassmorphism.
"""

def generate_css(opacity_percent):
    """Gera regras CSS para GTK 3 com transparência calculada baseada no slider."""
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
