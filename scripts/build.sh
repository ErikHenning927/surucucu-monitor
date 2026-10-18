#!/usr/bin/env bash
# Script de build limpo para o Surucucu (Python wheel + tar.gz)
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "🐍 Limpando resíduos de builds anteriores..."
rm -rf build/ dist/*.tmp* src/*.egg-info

echo "📦 Compilando pacotes para dist/..."
if [ -f ".venv/bin/python" ]; then
    .venv/bin/python -m build
else
    python3 -P -m build
fi

echo "🧹 Removendo diretório temporário build/..."
rm -rf build/

echo "✅ Build concluído com sucesso em dist/:"
ls -lh dist/surucucu-*
