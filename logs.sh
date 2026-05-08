#!/bin/bash
# Script para ver logs del bot IBKR con filtros

LOG_FILE=~/ibkr-bot/bot.log

show_help() {
    echo "Uso: ./logs.sh [OPCION]"
    echo ""
    echo "Opciones:"
    echo "  -f, --follow       Ver logs en tiempo real"
    echo "  -t, --telegram     Mostrar solo mensajes de Telegram"
    echo "  -e, --errors       Mostrar solo errores y warnings"
    echo "  -o, --orders       Mostrar solo ordenes y trades"
    echo "  -i, --ibkr         Mostrar solo conexiones IBKR"
    echo "  -s, --scanner      Mostrar solo scanner y senales"
    echo "  -n N               Mostrar ultimas N lineas (default: 50)"
    echo "  -h, --help         Mostrar esta ayuda"
    echo ""
    echo "Ejemplos:"
    echo "  ./logs.sh -f              # Ver todo en tiempo real"
    echo "  ./logs.sh -t -n 20        # Ultimos 20 mensajes de Telegram"
    echo "  ./logs.sh -e -f           # Ver errores en tiempo real"
    echo "  ./logs.sh -o              # Ultimas ordenes"
}

FOLLOW=false
FILTER="all"
LINES=50

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -t|--telegram)
            FILTER="telegram"
            shift
            ;;
        -e|--errors)
            FILTER="errors"
            shift
            ;;
        -o|--orders)
            FILTER="orders"
            shift
            ;;
        -i|--ibkr)
            FILTER="ibkr"
            shift
            ;;
        -s|--scanner)
            FILTER="scanner"
            shift
            ;;
        -n)
            LINES="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Opcion desconocida: $1"
            show_help
            exit 1
            ;;
    esac
done

case $FILTER in
    telegram)
        PATTERN='telegram|sendMessage|getUpdates|notify|Telegram notification'
        ;;
    errors)
        PATTERN='ERROR|WARN|error|exception|Traceback|failed|Failed'
        ;;
    orders)
        PATTERN='place_order|Order placed|Order rejected|Closing trade|close_trade|BUY|SELL|stop_loss|take_profit'
        ;;
    ibkr)
        PATTERN='ib_insync|IB Gateway|Connecting to|Connected|Disconnected|reconnect|accountSummary|portfolio'
        ;;
    scanner)
        PATTERN='scanner|run_scan|Signal|signal|preprocessor|select_top_symbols|STRONG|MEDIUM|WEAK'
        ;;
    *)
        PATTERN='.'
        ;;
esac

echo "=== IBKR Bot Logs [filtro: $FILTER] ==="
echo "Fecha: $(date)"
echo ""

if [ "$FOLLOW" = true ]; then
    tail -f "$LOG_FILE" | grep -iE "$PATTERN"
else
    tail -n "$LINES" "$LOG_FILE" | grep -iE "$PATTERN"
fi
