#!/usr/bin/env python3
"""
Wrapper para Surucucu (mantendo compatibilidade com scripts legados)
"""
import sys
import os

# Adiciona src ao path de importação
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from surucucu.monitor import main

if __name__ == "__main__":
    main()
