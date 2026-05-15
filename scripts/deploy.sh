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
  if [ ! -f venv/bin/python3 ]; then
    echo 'Creando venv...'
    python3 -m venv venv
  fi
  ~/.local/bin/uv pip install -r requirements.txt --python venv/bin/python3 -q
"

# 4. Migraciones si se solicitaron
if [ "$MIGRATE" = true ]; then
  echo "--- Ejecutando migraciones Alembic..."
  ssh "$REMOTE" "
    cd $REMOTE_DIR
    venv/bin/alembic upgrade head
  "
fi

# 5. Reiniciar servicio
echo "--- Reiniciando servicio $SERVICE..."
ssh "$REMOTE" "sudo systemctl restart $SERVICE --no-pager"

# 6. Esperar y verificar
echo "--- Esperando que el servicio levante..."
ssh "$REMOTE" "
  for i in \$(seq 1 24); do
    state=\$(systemctl is-active $SERVICE)
    echo \"  [\$i] \$state\"
    if [ \"\$state\" = 'active' ]; then break; fi
    if [ \"\$state\" = 'failed' ]; then break; fi
    sleep 5
  done
  sudo systemctl status $SERVICE --no-pager
"

echo ""
echo "=== Deploy completado: $SHA ==="
