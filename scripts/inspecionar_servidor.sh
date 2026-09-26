#!/usr/bin/env bash
# Inspeção somente leitura do servidor Linux.
# Não instala, não grava, não reinicia e não altera containers, volumes ou arquivos.
set -u

PORTA_CGE="${1:-8080}"

secao() {
  printf '\n===== %s =====\n' "$1"
}

executar() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "comando ausente: $1"
    return 0
  fi
  shift
  "$@" || echo "comando encerrou com status $?"
}

secao "Distribuição"
if [ -r /etc/os-release ]; then
  cat /etc/os-release
else
  echo "/etc/os-release ilegível"
fi
executar uname uname -a

secao "CPU"
if [ -r /proc/cpuinfo ]; then
  awk -F: '/^model name/ { gsub(/^ +/, "", $2); print $2; exit }' /proc/cpuinfo
  echo -n "núcleos lógicos: "
  grep -c '^processor' /proc/cpuinfo
else
  executar nproc nproc
fi

secao "Memória"
if [ -r /proc/meminfo ]; then
  awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/ { print }' /proc/meminfo
else
  executar free free -h
fi

secao "Disco"
executar df df -hT

secao "Docker"
executar docker docker version
echo
executar docker docker info --format 'Servidor: {{.ServerVersion}} | Driver: {{.Driver}} | Root: {{.DockerRootDir}} | Containers: {{.Containers}} | Em execução: {{.ContainersRunning}}'

secao "Docker Compose"
executar docker docker compose version

secao "Containers"
executar docker docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

secao "Stacks e projetos Compose"
executar docker docker compose ls -a

secao "Portas em escuta"
if command -v ss >/dev/null 2>&1; then
  ss -tuln || echo "ss encerrou com status $?"
else
  echo "comando ausente: ss"
fi

secao "Redes Docker"
executar docker docker network ls

secao "Volumes Docker"
executar docker docker volume ls

secao "Diretórios"
for diretorio in /opt /srv /home /var/lib/docker /root; do
  if [ -d "$diretorio" ]; then
    echo "-- $diretorio"
    find "$diretorio" -mindepth 1 -maxdepth 2 -printf '%y %p\n' 2>/dev/null | sort || echo "listagem parcial de $diretorio"
  else
    echo "ausente: $diretorio"
  fi
done

secao "Porta pretendida da CGE (${PORTA_CGE})"
ocupada=0
if command -v ss >/dev/null 2>&1; then
  if ss -tuln | awk '{ print $5 }' | grep -Eq "(^|:|\\.)${PORTA_CGE}$"; then
    ocupada=1
  fi
fi
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Ports}}' | grep -Eq "(^|[:,])${PORTA_CGE}->"; then
    ocupada=1
  fi
fi
if [ "$ocupada" -eq 1 ]; then
  echo "OCUPADA: a porta ${PORTA_CGE} já está em uso. Escolha outra em NGINX_HTTP_PORT."
else
  echo "LIVRE: nenhuma escuta ou publicação Docker encontrada na porta ${PORTA_CGE}."
fi

echo
echo "Inspeção concluída. Nenhum arquivo, container, rede ou volume foi modificado."
