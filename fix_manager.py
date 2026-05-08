content = open('/home/frankpach/ibkr-bot/app/positions/manager.py').read()

suffix = '        if exit_reason:\n            logger.info(f"Closing trade {trade.id} {trade.symbol} reason={exit_reason} pnl={pnl_pct:.2%} ${pnl_usd:.2f}")\n            close_trade(\n                trade_id=trade.id, exit_price=price, exit_reason=exit_reason,\n                pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 4),\n            )\n'

addition = '            trade.exit_price = price\n            trade.exit_reason = exit_reason\n            trade.pnl_usd = round(pnl_usd, 2)\n            trade.pnl_pct = round(pnl_pct, 4)\n            try:\n                run_postmortem(trade)\n            except Exception as e:\n                logger.error(f"Postmortem error for trade {trade.id}: {e}")\n'

if content.endswith(suffix):
    content = content + addition
    open('/home/frankpach/ibkr-bot/app/positions/manager.py', 'w').write(content)
    print('Updated successfully')
else:
    print('File does not end with expected suffix')
    print(repr(content[-100:]))
