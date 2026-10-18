"""
Thread de observabilidade contínua para monitoramento e telemetria de Contêineres Docker.
"""

import re
import time
import threading
import subprocess

class DockerMonitorWorker:
    """Worker em thread separada para capturar métricas de docker stats e docker ps."""

    def __init__(self):
        self.lock = threading.Lock()
        self.containers = {}       # {name: {id, name, cpu, mem, mem_bytes, ports, status, image}}
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _parse_mem(self, mem_str):
        """Converte strings de memória como '1.2GiB / 16GiB' em bytes."""
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
                        c_id = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', p[0]).strip()
                        c_name = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', p[1]).strip()
                        c_cpu = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', p[2]).strip()
                        c_mem = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', p[3]).strip()
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
        """Retorna uma cópia thread-safe da lista de contêineres detectados."""
        with self.lock:
            return list(self.containers.values())
