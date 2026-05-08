#!/bin/bash
# start_gateway.sh — Arranca IB Gateway headless via IBC + Xvfb
# Llamado por ibkr-gateway.service o manualmente

set -e

# Cargar variables de entorno
if [ -f /home/frankpach/ibkr-bot/.env ]; then
    export $(grep -v '^#' /home/frankpach/ibkr-bot/.env | grep -v '^$' | xargs)
fi

# Verificar credenciales
if [ -z "$IB_USERNAME" ] || [ -z "$IB_PASSWORD" ]; then
    echo "ERROR: IB_USERNAME o IB_PASSWORD no configurados en .env"
    exit 1
fi

IBC_DIR="/home/frankpach/ibc"
GATEWAY_DIR="/home/frankpach/Jts/ibgateway/1046"
JAVA_PATH="/usr/bin/java"
DISPLAY_NUM=:99

# Reemplazar variables en config
sed -e "s|\${IB_USERNAME}|$IB_USERNAME|g" \
    -e "s|\${IB_PASSWORD}|$IB_PASSWORD|g" \
    -e "s|\${IB_TRADING_MODE}|${IB_TRADING_MODE:-paper}|g" \
    "$IBC_DIR/config.ini" > /tmp/ibc_runtime.ini

# Iniciar Xvfb si no está corriendo
if ! pgrep -x Xvfb > /dev/null; then
    echo "Iniciando Xvfb en display $DISPLAY_NUM..."
    Xvfb $DISPLAY_NUM -screen 0 1024x768x24 &
    sleep 2
fi

export DISPLAY=$DISPLAY_NUM

echo "Iniciando IB Gateway via IBC..."
cd "$IBC_DIR"

java -cp "$IBC_DIR/IBC.jar:$GATEWAY_DIR/jars/*" \
    ibcalpha.ibc.IbcGateway \
    /tmp/ibc_runtime.ini \
    "$GATEWAY_DIR" \
    "$JAVA_PATH" \
    "" \
    "${IB_TRADING_MODE:-paper}" &

IBC_PID=$!
echo "IBC PID: $IBC_PID"

# Esperar a que el puerto 4002 esté disponible (max 2 minutos)
echo "Esperando conexión en puerto 4002..."
for i in $(seq 1 24); do
    if nc -z 127.0.0.1 4002 2>/dev/null; then
        echo "IB Gateway listo en puerto 4002"
        exit 0
    fi
    sleep 5
done

echo "ERROR: IB Gateway no respondió en 2 minutos"
exit 1
