"""
Discord Position Updates Module

Handles periodic sending of position information to Discord channels.
Includes formatting, scheduling, and error handling for position updates.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any, Optional

from discord import messages as discord_msgs
from core import data_manager # This import is now valid

# Configure logging for this module
logger = logging.getLogger(__name__)

# Global variable to track the running task
_periodic_update_task: Optional[asyncio.Task] = None

def format_position_message(
    positions: List[Dict[str, Any]],
    live_mode: bool,
    es_price: Optional[float] = None,
    high_adj: Optional[float] = None,
    low_adj: Optional[float] = None,
    adj_points: Optional[float] = None
) -> str:
    """
    Format position data into a Discord message for periodic updates.
    
    Args:
        positions: List of position dictionaries from data_manager
        live_mode: True for live mode, False for paper mode
        es_price: Current ES price
        high_adj: High adjusted value
        low_adj: Low adjusted value
        adj_points: Adjustment points
        
    Returns:
        Formatted Discord message string
    """
    mode_text = "Live" if live_mode else "Paper"
    
    # Construct the header for periodic updates
    header_parts = [f"📊 Position Update - {mode_text} Mode"]
    if es_price is not None:
        header_parts.append(f"ES Price: {es_price:.2f}")
    if high_adj is not None and low_adj is not None and adj_points is not None:
        header_parts.append(f"High Adj: {high_adj:.2f} Low Adj: {low_adj:.2f} (+/- {adj_points:.2f} adj)")
    
    header = " | ".join(header_parts) + "\n"
    
    if not positions:
        return f"{header}\nNo active positions."
    
    # Read PnL from open_positions.json
    pnl_data = {}
    try:
        with open('data/open_positions.json', 'r') as f:
            pnl_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not read or parse data/open_positions.json: {e}")

    position_lines = []
    
    # Sort positions alphabetically by symbol for consistent ordering
    sorted_positions = sorted(positions, key=lambda p: p.get('symbol', ''))
    
    for pos in sorted_positions:
        symbol = pos.get('symbol', 'N/A')

        # Determine strike with priority:
        #   1) top-level pos['strike']
        #   2) nested pos['contract']['strike']
        # If parsing fails, fall back to None.
        raw_strike = pos.get("strike") or pos.get("contract", {}).get("strike")
        strike_text: Optional[str] = None
        if raw_strike is not None:
            try:
                strike_val = float(raw_strike)
                # Whole numbers shown without decimals, otherwise two decimals.
                if strike_val.is_integer():
                    strike_text = f"{int(strike_val)}"
                else:
                    strike_text = f"{strike_val:.2f}"
            except Exception:
                # Tolerant parsing: on any error, ignore strike
                strike_text = None

        # Build contract description: "SYMBOL STRIKE" when strike present, otherwise just symbol.
        contract_desc = f"{symbol} {strike_text}" if strike_text else symbol

        # Extract PnL from the JSON data
        pnl = "N/A"
        position_id = pos.get('position_id')
        if pnl_data and 'positions' in pnl_data and position_id:
            for pnl_pos in pnl_data['positions']:
                if pnl_pos.get('position_id') == position_id:
                    pnl = pnl_pos.get('current_pnl', pnl_pos.get('final_pnl', 'N/A'))
                    break

        if isinstance(pnl, (float, int)):
            pnl_text = f"PnL: {pnl:,.2f}"
        else:
            pnl_text = f"PnL: {pnl}"

        # Per-position adjustment info
        pa_high = pos.get('high_adj')
        pa_low = pos.get('low_adj')
        pa_ch = pos.get('close_high')
        pa_cl = pos.get('close_low')
        def fmt(v):
            if v is None:
                return "N/A"
            try:
                return f"{float(v):.2f}"
            except Exception:
                return str(v)
        per_pos_adj = f"[adj: {fmt(pa_low)} / {fmt(pa_high)} | close: {fmt(pa_cl)} / {fmt(pa_ch)}]"

        position_line = f"- {contract_desc}: {pnl_text} (API Premium) {per_pos_adj}"
        position_lines.append(position_line)
    
    # Add timestamp
    est_tz = pytz.timezone('US/Eastern')
    timestamp = datetime.now(est_tz).strftime('%Y-%m-%d %H:%M:%S EST')
    footer = f"\nUpdated: {timestamp}"
    
    # Combine all parts
    message = header + "\n" + "\n\n".join(position_lines) + footer
    
    return message


def send_position_update(
    positions: List[Dict[str, Any]],
    live_mode: bool,
    es_price: Optional[float] = None,
    high_adj: Optional[float] = None,
    low_adj: Optional[float] = None,
    adj_points: Optional[float] = None
) -> bool:
    """
    Send formatted position update to Discord.
    
    Args:
        positions: List of position dictionaries
        live_mode: True for live mode, False for paper mode
        es_price: Current ES price
        high_adj: High adjusted value
        low_adj: Low adjusted value
        adj_points: Adjustment points
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        message = format_position_message(
            positions,
            live_mode,
            es_price=es_price,
            high_adj=high_adj,
            low_adj=low_adj,
            adj_points=adj_points
        )
        strat = 'live-stop-hunter' if live_mode else 'paper-stop-hunter'
        
        discord_msgs.send_msg(message, strat=strat)
        logger.info(f"Sent periodic position update for {'live' if live_mode else 'paper'} mode with {len(positions)} positions")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send position update to Discord: {e}")
        return False

async def send_trade_event_update(position_data: Dict[str, Any], trade_type: str, live_mode: bool, tws_port: int):
    """
    Sends a Discord message for trade events (new or closed positions).
    
    Args:
        position_data: Dictionary containing details of the position.
        trade_type: "NEW_POSITION" or "CLOSED_POSITION".
        live_mode: True for live mode, False for paper mode.
        tws_port: TWS port to determine the correct Discord channel.
    """
    try:
        symbol = position_data.get('symbol', 'N/A')
        strike = position_data.get('contract', {}).get('strike', 'N/A')
        right = position_data.get('contract', {}).get('right', 'N/A')
        
        message = ""
        if trade_type == "NEW_POSITION":
            price = position_data.get('avgCost', 'N/A')
            if isinstance(price, (float, int)):
                price_text = f"@{price:,.2f}"
            else:
                price_text = f"@{price}"
            message = f"🟢 New Position: {symbol} {strike} {right} {price_text}"
        elif trade_type == "CLOSED_POSITION":
            pnl = position_data.get('realizedPnl', 'N/A') # Assuming realizedPnl for closed positions
            if isinstance(pnl, (float, int)):
                pnl_text = f"PnL: {pnl:,.2f}"
            else:
                pnl_text = f"PnL: {pnl}"
            message = f"🔴 Closed Position: {symbol} {strike} {right} {pnl_text}"
            summary_footer = position_data.get('closed_summary')
            if summary_footer:
                message = f"{message}\n{summary_footer}"
        else:
            logger.warning(f"Unknown trade_type '{trade_type}' for Discord update.")
            return

        strat = 'live-stop-hunter' if tws_port == 7497 else 'paper-stop-hunter'
        
        if message:
            discord_msgs.send_msg(message, strat=strat)
            logger.info(f"Sent Discord trade event update for {trade_type} in {'live' if live_mode else 'paper'} mode.")
        
    except Exception as e:
        logger.error(f"Failed to send trade event update to Discord: {e}")


async def periodic_update_task(ib_conn, config, live_mode: bool, shutdown_event: asyncio.Event):
    """
    Main async task that runs periodic position updates aligned to specific times.
    
    Args:
        ib_conn: TWS connection object
        config: Configuration object, contains DISCORD_UPDATE_INTERVAL_MINUTES
        live_mode: True for live mode, False for paper mode
        shutdown_event: Event to signal shutdown
    """
    logger.info(f"Starting periodic Discord position updates for {'live' if live_mode else 'paper'} mode")
    
    last_sent_periodic_update_time: Optional[datetime] = None

    # Send initial update immediately if positions exist
    try:
        if config.SEND_PERIODIC_UPDATES_ENABLED:
            # Fetch fresh position data for initial update from data_manager
            # The data_manager.fetch_and_update_positions(ib_conn) is a placeholder
            # and positions should be updated by StraddleStrategy.
            # So, we will just get the positions from data_manager.
            
            # Wait for market data tickers to arrive
            logger.debug("Waiting for initial market data tickers to arrive...")
            await asyncio.sleep(3)
            
            # Get updated positions with fresh market data
            updated_positions = data_manager.get_positions()
            if updated_positions:
                # Fetch ES price and adjustment values from data_manager
                es_price = data_manager.get_es_price()
                adj_values = data_manager.get_adjustment_values()
                high_adj = adj_values.get('high_adj')
                low_adj = adj_values.get('low_adj')
                adj_points = adj_values.get('adj_points')
                send_position_update(updated_positions, live_mode, es_price, high_adj, low_adj, adj_points)
                logger.info("Sent initial position update on startup with fresh market data")
    except Exception as e:
        logger.error(f"Error sending initial position update: {e}")
    
    while not shutdown_event.is_set():
        try:
            # Check if periodic updates are enabled
            if not config.SEND_PERIODIC_UPDATES_ENABLED:
                logger.debug("Periodic updates disabled, checking again in 60 seconds")
                await asyncio.sleep(60)
                continue
            
            # DISCORD_UPDATE_INTERVAL_MINUTES is sourced from the config object.
            interval_minutes = config.DISCORD_UPDATE_INTERVAL_MINUTES
            
            now = datetime.now(pytz.utc)

            # Calculate the next exact update time.
            # This ensures updates occur at exact intervals (e.g., 16:00, 16:30 for a 30-minute interval).
            if interval_minutes > 0:
                intervals_passed = now.minute // interval_minutes
                next_interval_minute_mark = (intervals_passed + 1) * interval_minutes
                top_of_hour = now.replace(minute=0, second=0, microsecond=0)
                next_exact_update_time = top_of_hour + timedelta(minutes=next_interval_minute_mark)
            else:
                # Avoid division by zero and continuous loops if interval is 0 or less.
                logger.warning("DISCORD_UPDATE_INTERVAL_MINUTES is 0 or negative, periodic updates will not run.")
                await asyncio.sleep(300) # Sleep for 5 minutes before checking again
                continue

            seconds_until_next = max(0, (next_exact_update_time - now).total_seconds())
            
            logger.debug(f"Next Discord update at {next_exact_update_time.isoformat()} (in {seconds_until_next:.2f} seconds)")
            
            # Wait until the next aligned time or shutdown.
            # The condition for sending is implicitly met when the timeout is reached.
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=seconds_until_next)
                # If we get here, shutdown was signaled
                break
            except asyncio.TimeoutError:
                # Time for the next update
                pass
            
            # Send the update if still enabled and we have positions
            if config.SEND_PERIODIC_UPDATES_ENABLED:
                # Fetch fresh position data from TWS before sending update
                try:
                    logger.debug("Fetching fresh position data from TWS for Discord update")
                    # The periodic_update_task should get positions from data_manager,
                    # which is updated by StraddleStrategy.
                    
                    # Wait a moment for market data tickers to arrive and update positions
                    logger.debug("Waiting for market data tickers to arrive...")
                    await asyncio.sleep(3)
                    
                    # Get the updated positions from memory (which should now have fresh market data)
                    updated_positions = data_manager.get_positions()
                    
                    if updated_positions:
                        # Log market data for debugging
                        for pos in updated_positions:
                            symbol = pos.get('symbol', 'N/A')
                            mid = pos.get('market_data', {}).get('mid', 'N/A')
                            bid = pos.get('market_data', {}).get('bid', 'N/A')
                            ask = pos.get('market_data', {}).get('ask', 'N/A')
                            logger.debug(f"Position {symbol}: Bid={bid}, Ask={ask}, Mid={mid}")
                        
                        # Fetch ES price and adjustment values from data_manager
                        es_price = data_manager.get_es_price()
                        adj_values = data_manager.get_adjustment_values()
                        high_adj = adj_values.get('high_adj')
                        low_adj = adj_values.get('low_adj')
                        adj_points = adj_values.get('adj_points')
                        success = send_position_update(updated_positions, live_mode, es_price, high_adj, low_adj, adj_points)
                        if success:
                            # After an update is sent, update last_sent_periodic_update_time
                            last_sent_periodic_update_time = next_exact_update_time
                            logger.info(f"Sent scheduled position update with fresh market data ({len(updated_positions)} positions). Last update time set to {last_sent_periodic_update_time.isoformat()}")
                        else:
                            logger.warning("Failed to send scheduled position update")
                    else:
                        logger.debug("No positions to update, skipping Discord message")
                except Exception as e:
                    logger.error(f"Error fetching fresh position data for Discord update: {e}")
                    # Fallback to cached data
                    positions = data_manager.get_positions()
                    if positions:
                        logger.warning("Using cached position data for Discord update due to fetch error")
                        # Log cached data for debugging
                        for pos in positions:
                            symbol = pos.get('symbol', 'N/A')
                            mid = pos.get('market_data', {}).get('mid', 'N/A')
                            logger.debug(f"Cached position {symbol}: Mid={mid}")
                        # Fetch ES price and adjustment values from data_manager
                        es_price = data_manager.get_es_price()
                        adj_values = data_manager.get_adjustment_values()
                        high_adj = adj_values.get('high_adj')
                        low_adj = adj_values.get('low_adj')
                        adj_points = adj_values.get('adj_points')
                        send_position_update(positions, live_mode, es_price, high_adj, low_adj, adj_points)
                
        except asyncio.CancelledError:
            logger.info("Periodic update task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in periodic update task: {e}")
            # Wait a bit before retrying to avoid rapid error loops
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
                break
            except asyncio.TimeoutError:
                continue
    
    logger.info("Periodic Discord position updates stopped")

async def start_periodic_updates(ib_conn, config, live_mode: bool, shutdown_event: asyncio.Event):
    """
    Start the periodic updates task.
    
    Args:
        ib_conn: TWS connection object
        config: Configuration object
        live_mode: True for live mode, False for paper mode
        shutdown_event: Event to signal shutdown
    """
    global _periodic_update_task
    
    if _periodic_update_task and not _periodic_update_task.done():
        logger.warning("Periodic update task already running")
        return
    
    logger.info("Starting Discord periodic updates task")
    await periodic_update_task(ib_conn, config, live_mode, shutdown_event)

async def stop_periodic_updates():
    """
    Stop the periodic updates task gracefully.
    """
    global _periodic_update_task
    
    if _periodic_update_task and not _periodic_update_task.done():
        logger.info("Stopping periodic Discord updates...")
        _periodic_update_task.cancel()
        try:
            await _periodic_update_task
        except asyncio.CancelledError:
            logger.info("Periodic updates stopped successfully")
        _periodic_update_task = None
    else:
        logger.debug("No periodic update task to stop")

def get_update_status(config: Any) -> Dict[str, Any]:
    """
    Get the current status of periodic updates.

    Args:
        config: The configuration object.
    
    Returns:
        Dictionary with status information
    """
    global _periodic_update_task
    
    return {
        'task_running': _periodic_update_task is not None and not _periodic_update_task.done(),
        'updates_enabled': config.SEND_PERIODIC_UPDATES_ENABLED,
        'task_done': _periodic_update_task.done() if _periodic_update_task else None,
        'task_cancelled': _periodic_update_task.cancelled() if _periodic_update_task else None
    }

# Test function for development
async def test_position_update(live_mode: bool = False):
    """
    Test function to send a sample position update.
    For development and testing purposes.
    """
    # Create sample position data
    sample_positions = [
        {
            'symbol': 'ES',
            'contract': {'strike': 'N/A', 'right': 'N/A'},
            'avgCost': 212525.0,  # Will be divided by 50 for ES
            'market_data': {'mid': 4255.25},
            'stop_order': {'price': 4240.00}
        },
        {
            'symbol': 'SPY',
            'contract': {'strike': 450, 'right': 'CALL'},
            'avgCost': 5.25,
            'market_data': {'mid': 5.45},
            'stop_order': {'price': 4.80}
        }
    ]
    
    logger.info("Sending test position update...")
    success = send_position_update(sample_positions, live_mode)
    return success

if __name__ == "__main__":
    # Test the module
    import asyncio
    
    async def main():
        print("Testing Discord position updates module...")
        success = await test_position_update(False)  # Test with paper mode
        print(f"Test result: {'Success' if success else 'Failed'}")
    
    asyncio.run(main())
