#!/usr/bin/env bash
# ==============================================================================
# Script de Limpeza do Sistema Linux (Ubuntu / Debian-based)
# Remove caches, arquivos temporários, logs antigos, lixeiras e libera memória.
# ==============================================================================

set -eo pipefail

# Cores para formatação
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BOLD="\033[1m"
NC="\033[0m"

# Identificar usuário real (mesmo executando via sudo)
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6 2>/dev/null || echo "$HOME")

# Funções utilitárias de output
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

log_header() {
    echo -e "\n${BOLD}${BLUE}=== $1 ===${NC}"
}

# Checagem de permissão root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[ERRO]${NC} Este script precisa de privilégios de superusuário para limpar caches do sistema."
        echo "Por favor, execute com: sudo $0 $*"
        exit 1
    fi
}

# Exibir uso de disco e memória
show_system_usage() {
    echo -e "${BOLD}Espaço em disco (/):${NC}"
    df -h / | awk 'NR==1 || NR==2 {print "  " $0}'
    echo -e "${BOLD}Uso de Memória RAM:${NC}"
    free -h | awk 'NR==1 || NR==2 {print "  " $0}'
}

# 1. Limpeza do APT e Gerenciador de Pacotes
clean_apt() {
    log_header "1. Limpando Gerenciador de Pacotes (APT / DPKG)"
    
    log_info "Atualizando lista de dependências órfãs e removendo pacotes não utilizados..."
    apt-get autoremove --purge -y >/dev/null 2>&1 || true
    
    log_info "Limpando arquivos parciais e obsoletos de pacotes baixados (.deb)..."
    apt-get autoclean -y >/dev/null 2>&1 || true
    apt-get clean >/dev/null 2>&1 || true

    log_info "Removendo resíduos de pacotes desinstalados (status 'rc')..."
    REMOVED_RC=$(dpkg -l 2>/dev/null | awk '/^rc/ {print $2}' || true)
    if [[ -n "$REMOVED_RC" ]]; then
        echo "$REMOVED_RC" | xargs dpkg --purge 2>/dev/null || true
        log_success "Pacotes residuais removidos."
    else
        log_info "Nenhum resíduo de pacote encontrado."
    fi

    log_success "APT e DPKG limpos."
}

# 2. Limpeza de Logs do Systemd Journal e /var/log
clean_logs() {
    log_header "2. Limpando Logs do Sistema (Systemd & /var/log)"

    if command -v journalctl &>/dev/null; then
        log_info "Reduzindo histórico do systemd-journal para no máximo 3 dias ou 100MB..."
        journalctl --vacuum-time=3d >/dev/null 2>&1 || true
        journalctl --vacuum-size=100M >/dev/null 2>&1 || true
        log_success "Systemd journal compactado."
    fi

    log_info "Removendo relatórios de travamentos (/var/crash)..."
    rm -rf /var/crash/* 2>/dev/null || true

    log_info "Removendo arquivos de log compactados e antigos (.gz, .1, .old em /var/log)..."
    find /var/log -type f \( -name "*.gz" -o -name "*.1" -o -name "*.old" \) -delete 2>/dev/null || true
    log_success "Logs antigos removidos com segurança."
}

# 3. Limpeza de revisões antigas do Snap
clean_snaps() {
    if ! command -v snap &>/dev/null; then
        return 0
    fi

    log_header "3. Limpando Pacotes Snap (Revisões Antigas Desativadas)"
    
    # O snapd mantém versões anteriores de pacotes já atualizados.
    log_info "Procurando versões obsoletas/desativadas de snaps..."
    local count=0
    LANG=en_US.UTF-8 snap list --all 2>/dev/null | awk '/disabled/{print $1, $3}' | while read -r snapname revision; do
        if [[ -n "$snapname" && -n "$revision" ]]; then
            log_info "Removendo $snapname (revisão $revision)..."
            snap remove "$snapname" --revision="$revision" >/dev/null 2>&1 || true
            count=$((count + 1))
        fi
    done

    # Ajusta o limite de retenção de revisões do snap para 2 (mínimo suportado pelo snapd)
    snap set system refresh.retain=2 2>/dev/null || true

    log_success "Revisões do Snap limpas."
}

# 4. Limpeza do Flatpak (se instalado)
clean_flatpak() {
    if ! command -v flatpak &>/dev/null; then
        return 0
    fi

    log_header "4. Limpando Runtimes Órfãos do Flatpak"
    log_info "Removendo runtimes e dependências do Flatpak não utilizadas..."
    flatpak uninstall --unused -y >/dev/null 2>&1 || true
    log_success "Flatpak limpo."
}

# 5. Limpeza de Caches de Usuário e Lixeira
clean_user_cache() {
    log_header "5. Limpando Caches do Usuário ($REAL_USER)"

    # Lixeira
    local trash_dir="$REAL_HOME/.local/share/Trash"
    if [[ -d "$trash_dir" ]]; then
        log_info "Esvaziando lixeira ($trash_dir)..."
        rm -rf "$trash_dir"/* 2>/dev/null || true
        log_success "Lixeira esvaziada."
    fi

    # Miniaturas de imagens / vídeos
    local thumb_dir="$REAL_HOME/.cache/thumbnails"
    if [[ -d "$thumb_dir" ]]; then
        log_info "Limpando cache de miniaturas (thumbnails)..."
        rm -rf "$thumb_dir"/* 2>/dev/null || true
        log_success "Cache de miniaturas limpo."
    fi

    # Caches de desenvolvimento comuns (se existirem)
    if [[ -d "$REAL_HOME/.cache/pip" ]]; then
        log_info "Limpando cache do pip..."
        rm -rf "$REAL_HOME/.cache/pip"/* 2>/dev/null || true
    fi

    if [[ -d "$REAL_HOME/.npm/_cacache" ]]; then
        log_info "Limpando cache do npm..."
        rm -rf "$REAL_HOME/.npm/_cacache"/* 2>/dev/null || true
    fi

    log_success "Caches de usuário limpos."
}

# 6. Limpeza de Diretórios Temporários
clean_temp() {
    log_header "6. Limpando Arquivos Temporários"

    log_info "Removendo arquivos temporários antigos em /tmp e /var/tmp (> 2 dias)..."
    find /tmp -mindepth 1 -atime +2 -delete 2>/dev/null || true
    find /var/tmp -mindepth 1 -atime +2 -delete 2>/dev/null || true
    log_success "Arquivos temporários limpos."
}

# 7. Limpeza do Docker (opcional / quando disponível)
clean_docker() {
    if ! command -v docker &>/dev/null; then
        return 0
    fi

    # Checa se o daemon do docker está respondendo
    if ! docker info &>/dev/null; then
        return 0
    fi

    log_header "7. Limpando Objetos Não Utilizados do Docker"
    log_info "Removendo contêineres parados, redes não utilizadas e imagens suspensas (dangling)..."
    docker system prune -f >/dev/null 2>&1 || true
    
    if [[ "$CLEAN_DOCKER_BUILD_CACHE" == "true" ]]; then
        log_info "Limpando cache de compilação (build cache) do Docker..."
        docker builder prune -f >/dev/null 2>&1 || true
    fi

    log_success "Docker limpo."
}

# 8. Limpeza de Memória RAM (PageCache, Dentries e Inodes)
clean_ram() {
    log_header "8. Liberando Buffers e Cache de Memória RAM"
    log_info "Sincronizando dados no disco (sync)..."
    sync
    log_info "Liberando PageCache, Dentries e Inodes (drop_caches)..."
    echo 3 > /proc/sys/vm/drop_caches
    log_success "Memória RAM liberada."
}

# Exibição de Ajuda
show_help() {
    echo "Uso: sudo $0 [OPÇÕES]"
    echo ""
    echo "Opções disponíveis:"
    echo "  --all              Executa limpeza completa (padrão)"
    echo "  --no-ram           Não limpa os caches da memória RAM"
    echo "  --docker-builder   Limpa também o build cache do Docker"
    echo "  --help, -h         Exibe esta mensagem de ajuda"
    echo ""
    echo "Exemplo:"
    echo "  sudo $0"
    echo "  sudo $0 --docker-builder"
}

# Processamento de parâmetros
CLEAN_RAM=true
CLEAN_DOCKER_BUILD_CACHE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-ram)
            CLEAN_RAM=false
            shift
            ;;
        --docker-builder)
            CLEAN_DOCKER_BUILD_CACHE=true
            shift
            ;;
        --all)
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}[ERRO]${NC} Opção desconhecida: $1"
            show_help
            exit 1
            ;;
    esac
done

# ==============================================================================
# Execução Principal
# ==============================================================================
main() {
    check_root "$@"

    echo -e "${BOLD}${GREEN}"
    echo "=========================================================="
    echo "     INICIANDO OTIMIZAÇÃO E LIMPEZA DO SISTEMA LINUX      "
    echo "=========================================================="
    echo -e "${NC}"

    echo -e "${BOLD}--- Estado do Sistema ANTES da limpeza ---${NC}"
    show_system_usage

    # Executar etapas
    clean_apt
    clean_logs
    clean_snaps
    clean_flatpak
    clean_user_cache
    clean_temp
    clean_docker

    if [[ "$CLEAN_RAM" == "true" ]]; then
        clean_ram
    fi

    echo -e "\n${BOLD}${GREEN}"
    echo "=========================================================="
    echo "               LIMPEZA CONCLUÍDA COM SUCESSO!             "
    echo "=========================================================="
    echo -e "${NC}"

    echo -e "${BOLD}--- Estado do Sistema DEPOIS da limpeza ---${NC}"
    show_system_usage
    echo ""
}

main "$@"
