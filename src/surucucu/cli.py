#!/usr/bin/env python3
"""
CLI entry point for Surucucu Observability Cockpit.
"""

import os
import sys
import argparse
import subprocess
import signal
import psutil
from surucucu import __version__, __app_name__


def find_running_instances():
    """Find PIDs of running surucucu monitor processes."""
    pids = []
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == current_pid:
                continue
            cmdline = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmdline)
            # Ignora comandos utilitários como --status, --version, --stop
            if any(arg in cmdline for arg in ["--status", "--version", "-v", "--stop", "-k", "--help", "-h"]):
                continue

            if "surucucu" in cmd_str or ("monitor.py" in cmd_str and "dev/setup-linux" in cmd_str):
                pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


def stop_instances():
    """Stop running instances."""
    pids = find_running_instances()
    if not pids:
        print("🐍 Surucucu não está em execução.")
        return 0
    
    print(f"🐍 Encerrando {len(pids)} instância(s) do Surucucu (PIDs: {pids})...")
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    print("✓ Surucucu encerrado.")
    return 0


def print_status():
    """Print status of surucucu."""
    pids = find_running_instances()
    if pids:
        print(f"🐍 Surucucu está ATIVO (PID(s): {', '.join(map(str, pids))})")
    else:
        print("⚪ Surucucu está PARADO")


def main():
    parser = argparse.ArgumentParser(
        prog="surucucu",
        description="🐍 Surucucu - Amazonian AI, GPU & System Observability Cockpit for Linux",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-b", "--background", action="store_true", help="Executar o Cockpit HUD em segundo plano"
    )
    parser.add_argument(
        "-k", "--stop", action="store_true", help="Encerrar instâncias do Surucucu em execução"
    )
    parser.add_argument(
        "-r", "--restart", action="store_true", help="Reiniciar o Cockpit HUD"
    )
    parser.add_argument(
        "--status", action="store_true", help="Exibir status de execução do Surucucu"
    )

    args = parser.parse_args()

    if args.stop:
        return stop_instances()

    if args.status:
        print_status()
        return 0

    if args.restart:
        stop_instances()

    # Sanitização de ambiente: remove contaminação de variáveis de snaps (ex: VS Code)
    if "GSETTINGS_SCHEMA_DIR" in os.environ and "snap" in os.environ["GSETTINGS_SCHEMA_DIR"].lower():
        del os.environ["GSETTINGS_SCHEMA_DIR"]
    if "XDG_DATA_DIRS_VSCODE_SNAP_ORIG" in os.environ:
        os.environ["XDG_DATA_DIRS"] = os.environ["XDG_DATA_DIRS_VSCODE_SNAP_ORIG"]
    elif "XDG_DATA_DIRS" in os.environ and "snap" in os.environ["XDG_DATA_DIRS"].lower():
        clean_dirs = [d for d in os.environ["XDG_DATA_DIRS"].split(":") if "snap" not in d.lower()]
        if "/usr/share" not in clean_dirs:
            clean_dirs.append("/usr/share")
        os.environ["XDG_DATA_DIRS"] = ":".join(clean_dirs)

    # Garantir variáveis de display para Wayland / X11
    if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":0"
    if "WAYLAND_DISPLAY" not in os.environ:
        os.environ["WAYLAND_DISPLAY"] = "wayland-0"

    if args.background:
        # Se já estiver rodando, avisar
        existing = find_running_instances()
        if existing and not args.restart:
            print(f"🐍 Surucucu já está em execução (PID: {existing[0]}). Use --restart para reiniciar.")
            return 0

        # Lançar processo desacoplado
        cmd = [sys.executable, "-m", "surucucu"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp,
        )
        print(f"🐍 Surucucu iniciado em segundo plano (PID: {proc.pid}).")
        return 0

    # Execução em primeiro plano
    from surucucu.monitor import main as run_monitor
    run_monitor()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
