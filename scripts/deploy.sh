#!/bin/bash
# deploy.sh — Despliega ibkr-bot en aiutox-pi via SSH (git pull + restart)
#
# Uso:
#   ./scripts/deploy.sh            # deploy normal
#   ./scripts/deploy.sh --migrate  # deploy + ejecuta alembic upgrade head
#
# Requiere: ssh aiutox-pi configurado en ~/.ssh/config

set -euo pipefail

REMOTE="aiutox-pi"
REMOTE_DIR="/home/frankpach/ibkr-bot"
VENV="$REMOTE_DIR/.venv"
SERVICE="ibkr-api.service"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
SHA=$(git rev-parse --short HEAD)
MIGRATE=false

for arg in "$@"; do
  case $arg in
    --migrate) MIGRATE=true ;;
    *) echo "Argumento desconocido: $arg"; exit 1 ;;
  esac
done

echo "=== Deploy ibkr-bot ==="
echo "Branch : $BRANCH"
echo "SHA    : $SHA"
echo "Remote : $REMOTE:$REMOTE_DIR"
echo "Migrate: $MIGRATE"
echo ""

# 1. Verificar conectividad
echo "--- Verificando conexión SSH..."
ssh -q "$REMOTE" "echo 'SSH OK'"

# 2. Git pull en el Pi
echo "--- Actualizando código..."
ssh "$REMOTE" "
  cd $REMOTE_DIR
  git fetch origin
  git checkout $BRANCH
  git reset --hard origin/$BRANCH
"

# 3. Crear venv si no existe e instalar dependencias
echo "--- Instalando dependencias..."
ssh "$REMOTE" "
  cd $REMOTE_DIR
  if [ ! -f $VENV/bin/python3 ]; then
    echo 'Creando venv...'
    python3 -m venv $VENV
  fi
  VIRTUAL_ENV=$VENV ~/.local/bin/uv pip install -r requirements.txt -q
"

# 4. Migraciones si se solicitaron
if [ "$MIGRATE" = true ]; then
  echo "--- Ejecutando migraciones Alembic..."
  ssh "$REMOTE" "cd $REMOTE_DIR && $VENV/bin/alembic upgrade head"
fi

# 5. Instalar/actualizar el unit file desde el repo
echo "--- Instalando unit file $SERVICE..."
ssh "$REMOTE" "
  sudo cp $REMOTE_DIR/systemd/$SERVICE /etc/systemd/system/$SERVICE
  sudo systemctl daemon-reload
"

# 6. Parar limpiamente y matar huérfanos antes de reiniciar
echo "--- Deteniendo servicio y limpiando procesos huérfanos..."
ssh "$REMOTE" "
  sudo systemctl stop $SERVICE 2>/dev/null || true
  sleep 3
  # Matar cualquier proceso python de ibkr-bot que haya quedado huérfano
  PIDS=\$(pgrep -f '$REMOTE_DIR/run.py' 2>/dev/null || true)
  if [ -n \"\$PIDS\" ]; then
    echo \"  Matando huérfanos: \$PIDS\"
    sudo kill -9 \$PIDS 2>/dev/null || true
    sleep 2
  fi
  # Verificar que el puerto quedó libre
  if sudo ss -tlnp | grep -q ':8088'; then
    echo '  WARN: puerto 8088 aún ocupado, forzando...'
    sudo fuser -k 8088/tcp 2>/dev/null || true
    sleep 2
  fi
  echo '  Puerto 8088 libre: OK'
"

# 7. Reiniciar servicio
echo "--- Iniciando servicio $SERVICE..."
ssh "$REMOTE" "sudo systemctl start $SERVICE"

# 8. Esperar y verificar
echo "--- Esperando que el servicio levante..."
ssh "$REMOTE" "
  for i in \$(seq 1 24); do
    state=\$(systemctl is-active $SERVICE)
    echo \"  [\$i] \$state\"
    if [ \"\$state\" = 'active' ]; then break; fi
    if [ \"\$state\" = 'failed' ]; then
      sudo journalctl -u $SERVICE -n 20 --no-pager
      exit 1
    fi
    sleep 5
  done
  sudo systemctl status $SERVICE --no-pager
"

echo ""
echo "=== Deploy completado: $SHA ==="
