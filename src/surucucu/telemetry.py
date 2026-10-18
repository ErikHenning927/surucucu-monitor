"""
Módulo de Telemetria de Hardware (NVIDIA GPU / VRAM / CUDA / PCIe) e Memória do Sistema.
"""

import os
import re
import sys
import psutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any

from surucucu.utils import format_bytes, format_mib
from surucucu.classifier import is_ai_target, is_dev_target, is_service_target

@dataclass
class GpuTelemetry:
    vram_used: float = 0.0
    vram_total: float = 6144.0
    vram_pct: float = 0.0
    gpu_util: float = 0.0
    mem_bus_util: float = 0.0
    temp: int = 0
    power: str = "0"
    rx_pci: int = 0
    tx_pci: int = 0
    gpu_vram_map: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    @property
    def is_throttling(self) -> bool:
        return self.temp >= 78

    @property
    def is_mem_bound(self) -> bool:
        return self.mem_bus_util > 75 and self.gpu_util < 45

def query_gpu_telemetry() -> GpuTelemetry:
    """Coleta telemetria em tempo real da GPU NVIDIA (computação, bus, VRAM, PCIe e per-PID)."""
    tel = GpuTelemetry()

    # 1. Utilização geral de GPU, VRAM, Temperatura e Consumo
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=1
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split("\n")[0].split(",")]
            tel.gpu_util = float(parts[0])
            tel.mem_bus_util = float(parts[1])
            tel.vram_used = float(parts[2])
            tel.vram_total = float(parts[3])
            tel.temp = int(parts[4])
            tel.power = parts[5]
    except Exception:
        pass

    # 2. Telemetria PCIe Throughput (TX/RX em MB/s)
    try:
        res_dmon = subprocess.run(["nvidia-smi", "dmon", "-s", "t", "-c", "1"], capture_output=True, text=True, timeout=1)
        lines = [l.strip() for l in res_dmon.stdout.strip().split('\n') if l.strip() and not l.startswith('#')]
        if lines:
            parts = lines[-1].split()
            if len(parts) >= 3:
                tel.rx_pci = int(parts[1])
                tel.tx_pci = int(parts[2])
    except Exception:
        pass

    # 3. Mapeamento de VRAM por Processo e Tipo (C = Compute/CUDA, G = Graphics)
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
                    tel.gpu_vram_map[current_pid] = {
                        'vram': int(m_mem.group(1)),
                        'type': current_type
                    }
                    current_pid = None
    except Exception:
        pass

    tel.vram_pct = (tel.vram_used / tel.vram_total * 100.0) if tel.vram_total > 0 else 0.0
    return tel

def collect_process_items(filter_mode, search_query, containers, gpu_vram_map):
    """
    Varre os processos psutil e contêineres Docker, calculando consumos,
    tags e filtrando conforme a aba selecionada. Retorna (top_items, total_ai_ram, total_ai_vram).
    """
    items = []
    total_ai_ram = 0.0
    total_ai_vram = 0.0

    # 1. Contêineres Docker
    for c in containers:
        is_ai = is_ai_target(c['name'], "", c['ports'], c.get('image', ''))
        if is_ai:
            total_ai_ram += c['mem_bytes']

        if filter_mode == "ai" and not is_ai:
            continue
        elif filter_mode == "dev" and not is_dev_target(c['name'], "", "", ""):
            continue

        tag = "🤖 AI" if is_ai else "🐳 Docker"
        
        if search_query:
            query_match = (
                search_query in c['name'].lower() or
                search_query in c['ports'].lower() or
                search_query in c['id'].lower() or
                search_query in tag.lower()
            )
            if not query_match:
                continue

        items.append({
            'id_str': f"docker:{c['name']}",
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

            gpu_meta = gpu_vram_map.get(pid, {})
            vram_mib = gpu_meta.get('vram', 0)
            gpu_proc_type = gpu_meta.get('type', '')

            is_gpu_gui = gpu_proc_type == 'G' or name.lower().startswith("gnome") or "xorg" in name.lower() or "wayland" in name.lower()
            if vram_mib > 0 and not is_gpu_gui:
                total_ai_vram += vram_mib * (1024 ** 2)

            is_ai = (is_ai_target(name, cmdline) or gpu_proc_type == 'C') and not is_gpu_gui
            is_dev = is_dev_target(name, cmdline, cwd, info.get('username') or '')

            if is_ai:
                total_ai_ram += rss

            if filter_mode == "ai" and not is_ai:
                continue
            elif filter_mode == "docker":
                continue
            elif filter_mode == "dev" and not is_dev:
                continue
            elif filter_mode == "all" and rss < (20 * 1024 * 1024) and vram_mib == 0:
                continue

            display_name = name
            if len(cmdline_list) > 1 and name.lower() in ["python", "python3", "node", "bash", "sh"]:
                script_part = os.path.basename(cmdline_list[1])
                display_name = f"{name} ({script_part})"

            short_cwd = cwd.replace(os.path.expanduser("~"), "~")
            
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

            if search_query:
                match = (
                    search_query in display_name.lower() or
                    search_query in cmdline.lower() or
                    search_query in short_cwd.lower() or
                    search_query in str(pid) or
                    search_query in tag.lower()
                )
                if not match:
                    continue

            items.append({
                'id_str': f"proc:{pid}",
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
    return items[:60], total_ai_ram, total_ai_vram
