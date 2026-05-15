#!/bin/bash
# deploy.sh — Despliega ibkr-bot en aiutox-pi via SSH
#
# Uso:
#   ./scripts/deploy.sh            # deploy normal
#   ./scripts/deploy.sh --migrate  # deploy + ejecuta alembic upgrade head
#
# Requiere: ssh aiutox-pi configurado en ~/.ssh/config

set -euo pipefail

REMOTE="aiutox-pi"
REMOTE_DIR="/home/frankpach/ibkr-bot"
SERVICE="ibkr-trader"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
SHA=$(git rev-parse --short HEAD)
MIGRATE=false

# Parsear argumentos
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

# 2. Sincronizar código (rsync excluye venv, db, logs, .env*)
echo "--- Sincronizando archivos..."
rsync -az --delete \
  --exclude='.git/' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.db' \
  --exclude='.env*' \
  --exclude='logs/' \
  --exclude='*.egg-info/' \
  --exclude='.claude/' \
  --exclude='docs/' \
  ./ "$REMOTE:$REMOTE_DIR/"

# 3. Instalar dependencias en el venv remoto
echo "--- Instalando dependencias..."
ssh "$REMOTE" "
  cd $REMOTE_DIR
  python3 -m venv venv
  venv/bin/pip install -q --upgrade pip
  venv/bin/pip install -q -r requirements.txt
"

# 4. Correr migraciones si se solicitó
if [ "$MIGRATE" = true ]; then
  echo "--- Ejecutando migraciones Alembic..."
  ssh "$REMOTE" "
    cd $REMOTE_DIR
    venv/bin/alembic upgrade head
  "
fi

# 5. Reiniciar el servicio
echo "--- Reiniciando servicio $SERVICE..."
ssh "$REMOTE" "sudo systemctl restart $SERVICE"

# 6. Esperar y verificar que levantó
echo "--- Verificando estado del servicio..."
sleep 3
ssh "$REMOTE" "
  if systemctl is-active --quiet $SERVICE; then
    echo 'Servicio activo OK'
    systemctl status $SERVICE --no-pager -l | tail -8
  else
    echo 'ERROR: servicio no levantó'
    journalctl -u $SERVICE -n 30 --no-pager
    exit 1
  fi
"

echo ""
echo "=== Deploy completado: $SHA ==="
