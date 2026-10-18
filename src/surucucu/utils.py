"""
Funções utilitárias de formatação de dados e renderização de Sparklines.
"""

def format_bytes(bytes_val):
    """Converte bytes para representação legível em MB ou GB."""
    gb = bytes_val / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.2f} GB"
    mb = bytes_val / (1024 ** 2)
    return f"{mb:.0f} MB"

def format_mib(mib_val):
    """Converte MiB para representação legível em MB ou GB."""
    if mib_val <= 0:
        return "-"
    if mib_val >= 1024:
        return f"{mib_val / 1024.0:.2f} GB"
    return f"{mib_val:.0f} MB"

def make_sparkline(values, max_val=100.0):
    """Gera sequência em caracteres Unicode e Pango markup para sparkline de VRAM."""
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
