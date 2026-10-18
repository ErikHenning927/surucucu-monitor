#!/usr/bin/env bash
# ==============================================================================
# Iniciar o Surucucu - AI & Dev Observability Cockpit
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export PYTHONPATH="$DIR/src:${PYTHONPATH}"

if [[ "$1" == "--stop" || "$1" == "-k" ]]; then
    surucucu --stop
    exit 0
fi

if [[ "$1" == "--background" || "$1" == "-b" ]]; then
    surucucu --background
else
    exec surucucu "$@"
fi
