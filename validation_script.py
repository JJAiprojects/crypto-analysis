#!/usr/bin/env python3

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import re

def load_telegram_config():
    """Load Telegram configuration from environment variables or config file"""
    # Try environment variables first
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        print("[INFO] Using Telegram credentials from environment variables")
        return {
            "bot_token": bot_token,
            "chat_id": chat_id,
            "enabled": True
        }
    
    # Fall back to config file
    config_file = "telegram_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            if config.get("enabled") and config.get("bot_token") != "YOUR_BOT_TOKEN":
                print("[INFO] Using Telegram credentials from config file")
                return config
        except Exception as e:
            print(f"[ERROR] Loading telegram config: {e}")
    
    print("[WARN] Telegram notifications not configured - will not send alerts")
    return {"enabled": False, "bot_token": "", "chat_id": ""}

def send_telegram_message(message, disable_web_page_preview=True):
    """Send a message to Telegram"""
    config = load_telegram_config()
    if not config["enabled"]:
        print("[INFO] Telegram notifications not enabled")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
        payload = {
            "chat_id": config["chat_id"],
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview
        }
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print("[INFO] Telegram message sent successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        return False

def is_duplicate_validation_point(validation_points, new_point):
    """Check if a validation point is already in the list"""
    for point in validation_points:
        if (point["coin"] == new_point["coin"]):
            # For take profit targets, check if both TP level number and predicted level match
            if "TP" in point["type"] and "TP" in new_point["type"] and "predicted_level" in point and "predicted_level" in new_point:
                # Extract TP number from type (e.g., "TP1_HIT" -> "1")
                point_tp_num = re.search(r'TP(\d+)', point["type"]).group(1)
                new_point_tp_num = re.search(r'TP(\d+)', new_point["type"]).group(1)
                
                # Consider it duplicate if same TP number AND same level
                if point_tp_num == new_point_tp_num and point["predicted_level"] == new_point["predicted_level"]:
                    return True
            # For entry points, always consider it duplicate if type matches
            elif "ENTRY_POINT_HIT" in point["type"] and "ENTRY_POINT_HIT" in new_point["type"]:
                return True
            # For stop loss, always consider it duplicate if type matches
            elif "STOP_LOSS_HIT" in point["type"] and "STOP_LOSS_HIT" in new_point["type"]:
                return True
    return False

def get_crypto_prices():
    """Get current cryptocurrency prices with multiple fallbacks"""
    # Try multiple API endpoints
    apis = [
        {
            "name": "CoinGecko",
            "url": "https://api.coingecko.com/api/v3/simple/price",
            "params": {"ids": "bitcoin,ethereum", "vs_currencies": "usd"},
            "extract": lambda data: {
                "btc": data.get("bitcoin", {}).get("usd"),
                "eth": data.get("ethereum", {}).get("usd")
            }
        },
        {
            "name": "Binance",
            "url": "https://api.binance.com/api/v3/ticker/price",
            "params": {"symbols": '["BTCUSDT","ETHUSDT"]'},
            "extract": lambda data: {
                "btc": float(next((item["price"] for item in data if item["symbol"] == "BTCUSDT"), None)),
                "eth": float(next((item["price"] for item in data if item["symbol"] == "ETHUSDT"), None))
            }
        },
        {
            "name": "Alternative Price API",
            "url": "https://min-api.cryptocompare.com/data/pricemulti",
            "params": {"fsyms": "BTC,ETH", "tsyms": "USD"},
            "extract": lambda data: {
                "btc": data.get("BTC", {}).get("USD"),
                "eth": data.get("ETH", {}).get("USD")
            }
        }
    ]
    
    errors = []
    
    # Try each API in order
    for api in apis:
        try:
            print(f"[INFO] Trying to get prices from {api['name']}...")
            response = requests.get(api["url"], params=api["params"], timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract prices using the provided extract function
            prices = api["extract"](data)
            
            # Validate that both prices were retrieved
            if prices["btc"] is not None and prices["eth"] is not None:
                print(f"[INFO] Successfully retrieved prices from {api['name']}")
                return prices
            else:
                errors.append(f"{api['name']}: Missing price data")
        except Exception as e:
            errors.append(f"{api['name']}: {str(e)}")
            print(f"[WARN] Failed to get prices from {api['name']}: {e}")
    
    # If all APIs fail, try to use latest saved prices
    try:
        prediction_file = "detailed_predictions.json"
        if os.path.exists(prediction_file):
            with open(prediction_file, "r") as f:
                predictions = json.load(f)
                if predictions and len(predictions) > 0:
                    latest = predictions[-1]
                    if "market_data" in latest:
                        btc_price = latest["market_data"].get("btc_price")
                        eth_price = latest["market_data"].get("eth_price")
                        if btc_price is not None and eth_price is not None:
                            print("[INFO] Using latest saved prices as fallback")
                            return {"btc": btc_price, "eth": eth_price}
    except Exception as e:
        errors.append(f"Fallback: {str(e)}")
    
    # All methods failed
    raise Exception(f"Failed to get cryptocurrency prices from all sources. Errors: {errors}")

def is_fresh_prediction(prediction_time):
    """Check if a prediction is from the most recent cycle (8am/8pm)"""
    now = datetime.now()
    
    # Get the most recent 8am or 8pm timestamp
    current_hour = now.hour
    if 8 <= current_hour < 20:
        # Last prediction window was at 8am today
        last_window = datetime(now.year, now.month, now.day, 8, 0, 0)
    else:
        # If it's before 8am, the last window was 8pm yesterday
        if current_hour < 8:
            yesterday = now - timedelta(days=1)
            last_window = datetime(yesterday.year, yesterday.month, yesterday.day, 20, 0, 0)
        else:
            # If it's after 8pm, the last window was 8pm today
            last_window = datetime(now.year, now.month, now.day, 20, 0, 0)
    
    # Get the previous window too (to account for slight timing differences)
    previous_window = last_window - timedelta(hours=12)
    
    # Check if the prediction is from the most recent window (with a buffer)
    time_diff = now - prediction_time
    
    # Consider it fresh if it's from the current or previous window (within 16 hours)
    return time_diff.total_seconds() < 16 * 3600

def validate_predictions():
    """Check if price has hit predicted levels and update prediction file"""
    print("[DEBUG] Starting validation with Telegram enabled:", os.environ.get("TELEGRAM_BOT_TOKEN") is not None)
    prediction_file = "detailed_predictions.json"
    
    if not os.path.exists(prediction_file):
        print("[INFO] No predictions to validate yet")
        return
    
    # Get current prices with fallbacks
    try:
        prices = get_crypto_prices()
        btc_price = prices["btc"]
        eth_price = prices["eth"]
        
        print(f"[INFO] Current prices - BTC: ${btc_price}, ETH: ${eth_price}")
    except Exception as e:
        print(f"[ERROR] Failed to get current prices: {e}")
        return
    
    # Load predictions
    try:
        with open(prediction_file, "r") as f:
            predictions = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load predictions: {e}")
        return
    
    # Lists to track validation points for notifications
    entry_points_hit = []  # For entry point notifications
    tp_sl_hits = []        # For tracking TP/SL hits (not for notifications, just tracking)
    accuracy_updates = []  # For prediction completion notifications
    
    updated = False
    now = datetime.now()
    
    for i, prediction in enumerate(predictions):
        # Initialize validation_points if not present
        if "validation_points" not in prediction:
            prediction["validation_points"] = []
            
        # Skip already completed predictions
        if prediction.get("final_accuracy") is not None:
            continue
        
        # Get prediction timestamp
        pred_time = datetime.strptime(prediction["timestamp"], "%Y-%m-%d %H:%M:%S")
        pred_id = f"ID-{i+1}"  # Create a simple ID for logging
        
        # Check if prediction is fresh (for notification purposes)
        is_fresh = is_fresh_prediction(pred_time)
        
        # Check if we should validate BTC prediction
        if "predictions" in prediction and "btc_prediction" in prediction["predictions"]:
            btc_pred = prediction["predictions"]["btc_prediction"]
            
            # Extract entry price range
            entry_range = None
            if "entry_price_range" in btc_pred:
                range_str = btc_pred["entry_price_range"]
                # Extract price range using regex
                range_match = re.findall(r'\$([0-9,]+(?:\.[0-9]+)?)', range_str)
                if len(range_match) >= 2:
                    try:
                        # Convert to float, removing commas
                        entry_range = [float(range_match[0].replace(',', '')), 
                                       float(range_match[1].replace(',', ''))]
                    except:
                        pass
            
            # Extract take profit targets
            tp_targets = []
            if "take_profit_targets" in btc_pred:
                tp_str = btc_pred["take_profit_targets"]
                # Extract price values using regex
                tp_match = re.findall(r'TP([0-9]+):\s*\$([0-9,]+(?:\.[0-9]+)?)', tp_str)
                for tp_num, tp_val in tp_match:
                    try:
                        # Convert to float, removing commas
                        tp_targets.append((tp_num, float(tp_val.replace(',', ''))))
                    except:
                        pass
            
            # Extract stop loss
            sl_level = None
            if "stop_loss" in btc_pred:
                sl_str = btc_pred["stop_loss"]
                # Extract price using regex
                sl_match = re.findall(r'\$([0-9,]+(?:\.[0-9]+)?)', sl_str)
                if sl_match:
                    try:
                        # Convert to float, removing commas
                        sl_level = float(sl_match[0].replace(',', ''))
                    except:
                        pass
                        
            # Get direction
            direction = btc_pred.get("direction", "").upper() if btc_pred.get("direction") else ""
            
            # Check if current price is within entry range
            if entry_range and len(entry_range) == 2:
                min_range = min(entry_range)
                max_range = max(entry_range)
                print(f"[DEBUG] Checking BTC entry point ({pred_id}): ${min_range} - ${max_range} against current: ${btc_price}")
                
                if min_range <= btc_price <= max_range:
                    validation_point = {
                        "coin": "BTC",
                        "type": "ENTRY_POINT_HIT",
                        "predicted_range": [min_range, max_range],
                        "actual_price": btc_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "prediction_id": pred_id
                    }
                    
                    # Check for duplicate before adding
                    if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
                        prediction["validation_points"].append(validation_point)
                        updated = True
                        print(f"[INFO] BTC entry point hit ({pred_id}): ${btc_price}")
                        
                        # Only add to notification list if it's a fresh prediction
                        if is_fresh:
                            entry_point = {
                                "coin": "BTC",
                                "price": btc_price,
                                "range": [min_range, max_range],
                                "direction": direction,
                                "prediction_id": pred_id,
                                "timestamp": pred_time.strftime("%Y-%m-%d %H:%M"),
                                "timeframe": btc_pred.get("timeframe", "Unknown")
                            }
                            entry_points_hit.append(entry_point)
            
            # Check take profit targets
            for tp_num, tp in tp_targets:
                # For bullish direction, price needs to go up to hit TP
                # For bearish direction, price needs to go down to hit TP
                if (direction == "BULLISH" and btc_price >= tp) or \
                   (direction == "BEARISH" and btc_price <= tp):
                    validation_point = {
                        "coin": "BTC",
                        "type": f"TP{tp_num}_HIT",
                        "predicted_level": tp,
                        "actual_price": btc_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "prediction_id": pred_id
                    }
                    
                    # Check for duplicate before adding
                    if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
                        prediction["validation_points"].append(validation_point)
                        updated = True
                        print(f"[INFO] BTC TP{tp_num} hit ({pred_id}): ${btc_price}")
                        
                        # Add to TP/SL tracking list (but not for notifications)
                        tp_sl_info = {
                            "coin": "BTC",
                            "type": f"TP{tp_num}",
                            "price": btc_price,
                            "target": tp,
                            "prediction_id": pred_id
                        }
                        tp_sl_hits.append(tp_sl_info)
            
            # Check stop loss
            if sl_level:
                # For bullish direction, price needs to go down to hit SL
                # For bearish direction, price needs to go up to hit SL
                if (direction == "BULLISH" and btc_price <= sl_level) or \
                   (direction == "BEARISH" and btc_price >= sl_level):
                    validation_point = {
                        "coin": "BTC",
                        "type": "STOP_LOSS_HIT",
                        "predicted_level": sl_level,
                        "actual_price": btc_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "prediction_id": pred_id
                    }
                    
                    # Check for duplicate before adding
                    if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
                        prediction["validation_points"].append(validation_point)
                        updated = True
                        print(f"[INFO] BTC stop loss hit ({pred_id}): ${btc_price}")
                        
                        # Add to TP/SL tracking list (but not for notifications)
                        tp_sl_info = {
                            "coin": "BTC",
                            "type": "SL",
                            "price": btc_price,
                            "target": sl_level,
                            "prediction_id": pred_id
                        }
                        tp_sl_hits.append(tp_sl_info)
        
        # Check if we should validate ETH prediction - very similar to BTC validation
        if "predictions" in prediction and "eth_prediction" in prediction["predictions"]:
            eth_pred = prediction["predictions"]["eth_prediction"]
            
            # Extract entry price range
            entry_range = None
            if "entry_price_range" in eth_pred:
                range_str = eth_pred["entry_price_range"]
                range_match = re.findall(r'\$([0-9,]+(?:\.[0-9]+)?)', range_str)
                if len(range_match) >= 2:
                    try:
                        entry_range = [float(range_match[0].replace(',', '')), 
                                       float(range_match[1].replace(',', ''))]
                    except:
                        pass
            
            # Extract take profit targets
            tp_targets = []
            if "take_profit_targets" in eth_pred:
                tp_str = eth_pred["take_profit_targets"]
                tp_match = re.findall(r'TP([0-9]+):\s*\$([0-9,]+(?:\.[0-9]+)?)', tp_str)
                for tp_num, tp_val in tp_match:
                    try:
                        tp_targets.append((tp_num, float(tp_val.replace(',', ''))))
                    except:
                        pass
            
            # Extract stop loss
            sl_level = None
            if "stop_loss" in eth_pred:
                sl_str = eth_pred["stop_loss"]
                sl_match = re.findall(r'\$([0-9,]+(?:\.[0-9]+)?)', sl_str)
                if sl_match:
                    try:
                        sl_level = float(sl_match[0].replace(',', ''))
                    except:
                        pass
                        
            # Get direction
            direction = eth_pred.get("direction", "").upper() if eth_pred.get("direction") else ""
            
            # Check if current price is within entry range
            if entry_range and len(entry_range) == 2:
                min_range = min(entry_range)
                max_range = max(entry_range)
                print(f"[DEBUG] Checking ETH entry point ({pred_id}): ${min_range} - ${max_range} against current: ${eth_price}")
                
                if min_range <= eth_price <= max_range:
                    validation_point = {
                        "coin": "ETH",
                        "type": "ENTRY_POINT_HIT",
                        "predicted_range": [min_range, max_range],
                        "actual_price": eth_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "prediction_id": pred_id
                    }
                    
                    # Check for duplicate before adding
                    if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
                        prediction["validation_points"].append(validation_point)
                        updated = True
                        print(f"[INFO] ETH entry point hit ({pred_id}): ${eth_price}")
                        
                        # Only add to notification list if it's a fresh prediction
                        if is_fresh:
                            entry_point = {
                                "coin": "ETH",
                                "price": eth_price,
                                "range": [min_range, max_range],
                                "direction": direction,
                                "prediction_id": pred_id,
                                "timestamp": pred_time.strftime("%Y-%m-%d %H:%M"),
                                "timeframe": eth_pred.get("timeframe", "Unknown")
                            }
                            entry_points_hit.append(entry_point)
            
            # Check take profit targets
            for tp_num, tp in tp_targets:
                if (direction == "BULLISH" and eth_price >= tp) or \
                   (direction == "BEARISH" and eth_price <= tp):
                    validation_point = {
                        "coin": "ETH",
                        "type": f"TP{tp_num}_HIT",
                        "predicted_level": tp,
                        "actual_price": eth_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "prediction_id": pred_id
                    }
                    
                    # Check for duplicate before adding
                    if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
                        prediction["validation_points"].append(validation_point)
                        updated = True
                        print(f"[INFO] ETH TP{tp_num} hit ({pred_id}): ${eth_price}")
                        
                        # Add to TP/SL tracking list (but not for notifications)
                        tp_sl_info = {
                            "coin": "ETH",
                            "type": f"TP{tp_num}",
                            "price": eth_price,
                            "target": tp,
                            "prediction_id": pred_id
                        }
                        tp_sl_hits.append(tp_sl_info)
            
            # Check stop loss
            if sl_level:
                if (direction == "BULLISH" and eth_price <= sl_level) or \
                   (direction == "BEARISH" and eth_price >= sl_level):
                    validation_point = {
                        "coin": "ETH",
                        "type": "STOP_LOSS_HIT",
                        "predicted_level": sl_level,
                        "actual_price": eth_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "prediction_id": pred_id
                    }
                    
                    # Check for duplicate before adding
                    if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
                        prediction["validation_points"].append(validation_point)
                        updated = True
                        print(f"[INFO] ETH stop loss hit ({pred_id}): ${eth_price}")
                        
                        # Add to TP/SL tracking list (but not for notifications)
                        tp_sl_info = {
                            "coin": "ETH",
                            "type": "SL",
                            "price": eth_price,
                            "target": sl_level,
                            "prediction_id": pred_id
                        }
                        tp_sl_hits.append(tp_sl_info)
        
        # Check if prediction timeframe has expired and calculate final accuracy
        # This examines the "timeframe" field to determine when a prediction expires
        for coin, key in [("BTC", "btc_prediction"), ("ETH", "eth_prediction")]:
            if "predictions" in prediction and key in prediction["predictions"]:
                coin_pred = prediction["predictions"][key]
                if "timeframe" in coin_pred:
                    timeframe_str = coin_pred["timeframe"]
                    # Extract timeframe values using regex
                    time_match = re.findall(r'([0-9]+)\s+(hour|day|hours|days)', timeframe_str.lower())
                    if time_match:
                        try:
                            amount = int(time_match[0][0])
                            unit = time_match[0][1]
                            
                            # Calculate expiration time
                            if unit.startswith('hour'):
                                expiry_time = pred_time.timestamp() + (amount * 3600)
                            elif unit.startswith('day'):
                                expiry_time = pred_time.timestamp() + (amount * 86400)
                            else:
                                expiry_time = None
                            
                            # If prediction has expired, calculate final accuracy
                            if expiry_time and now.timestamp() > expiry_time:
                                # Only calculate if not already done
                                if prediction.get("final_accuracy") is None:
                                    accuracy = calculate_prediction_accuracy(prediction)
                                    prediction["final_accuracy"] = accuracy
                                    updated = True
                                    print(f"[INFO] {coin} prediction ({pred_id}) from {pred_time} has expired. Final accuracy: {accuracy:.2f}%")
                                    
                                    # Add to accuracy updates list
                                    accuracy_info = {
                                        "coin": coin,
                                        "accuracy": accuracy,
                                        "timeframe": timeframe_str,
                                        "prediction_id": pred_id,
                                        "timestamp": pred_time.strftime("%Y-%m-%d %H:%M")
                                    }
                                    accuracy_updates.append(accuracy_info)
                        except Exception as e:
                            print(f"[ERROR] Failed to parse timeframe for {coin} ({pred_id}): {e}")
    
    # Save updated predictions
    if updated:
        try:
            with open(prediction_file, "w") as f:
                json.dump(predictions, f, indent=4)
            print("[INFO] Prediction file updated")
            
            # Send Telegram notifications if any entry points were hit
            if entry_points_hit:
                # Group by coin
                btc_entries = [e for e in entry_points_hit if e["coin"] == "BTC"]
                eth_entries = [e for e in entry_points_hit if e["coin"] == "ETH"]
                
                entry_messages = []
                
                # Add BTC entry points
                if btc_entries:
                    btc_msg_parts = ["🚨 <b>BTC ENTRY POINTS HIT</b>"]
                    for entry in btc_entries:
                        min_range, max_range = entry["range"]
                        btc_msg_parts.append(
                            f"• <b>{entry['direction']}</b> prediction from {entry['timestamp']}\n"
                            f"  Current: ${entry['price']:,.2f}\n"
                            f"  Range: ${min_range:,.2f} - ${max_range:,.2f}\n"
                            f"  Timeframe: {entry['timeframe']}"
                        )
                    entry_messages.append("\n\n".join(btc_msg_parts))
                
                # Add ETH entry points
                if eth_entries:
                    eth_msg_parts = ["🚨 <b>ETH ENTRY POINTS HIT</b>"]
                    for entry in eth_entries:
                        min_range, max_range = entry["range"]
                        eth_msg_parts.append(
                            f"• <b>{entry['direction']}</b> prediction from {entry['timestamp']}\n"
                            f"  Current: ${entry['price']:,.2f}\n"
                            f"  Range: ${min_range:,.2f} - ${max_range:,.2f}\n"
                            f"  Timeframe: {entry['timeframe']}"
                        )
                    entry_messages.append("\n\n".join(eth_msg_parts))
                
                # Send entry point notifications
                if entry_messages:
                    message = "\n\n".join(entry_messages)
                    result = send_telegram_message(message)
                    print(f"[INFO] Entry point notification result: {result}")
            
            # Send accuracy update notifications (at end of timeframe)
            if accuracy_updates:
                accuracy_msg_parts = ["📊 <b>PREDICTION RESULTS</b>"]
                for acc in accuracy_updates:
                    accuracy_msg_parts.append(
                        f"• {acc['coin']} Prediction ({acc['timestamp']})\n"
                        f"  Timeframe: {acc['timeframe']}\n"
                        f"  Final Accuracy: {acc['accuracy']:.2f}%"
                    )
                
                message = "\n\n".join(accuracy_msg_parts)
                result = send_telegram_message(message)
                print(f"[INFO] Accuracy update notification result: {result}")
                
        except Exception as e:
            print(f"[ERROR] Failed to save updated predictions: {e}")

def calculate_prediction_accuracy(prediction):
    """Calculate the accuracy of a prediction based on validation points"""
    # This is a simplified version - can be expanded with more sophisticated logic
    btc_pred = prediction.get("predictions", {}).get("btc_prediction", {})
    eth_pred = prediction.get("predictions", {}).get("eth_prediction", {})
    
    # Get confidence scores (default to 5 if not present)
    btc_confidence = 5
    if "confidence_score" in btc_pred:
        try:
            btc_confidence = int(re.search(r'(\d+)', btc_pred["confidence_score"]).group(1))
        except:
            pass
    
    eth_confidence = 5
    if "confidence_score" in eth_pred:
        try:
            eth_confidence = int(re.search(r'(\d+)', eth_pred["confidence_score"]).group(1))
        except:
            pass
    
    btc_weight = btc_confidence / 10
    eth_weight = eth_confidence / 10
    
    # Count validation points
    validation_points = prediction.get("validation_points", [])
    
    # Setup point counters
    btc_total_points = 0
    btc_hit_points = 0
    eth_total_points = 0
    eth_hit_points = 0
    
    # Assign points for different prediction aspects
    for coin_pred, coin_name, coin_weight in [(btc_pred, "BTC", btc_weight), (eth_pred, "ETH", eth_weight)]:
        if not coin_pred:
            continue
            
        # For direction prediction
        if coin_pred.get("direction"):
            if coin_name == "BTC":
                btc_total_points += 3
            else:
                eth_total_points += 3
                
        # For entry price range
        if coin_pred.get("entry_price_range"):
            if coin_name == "BTC":
                btc_total_points += 2
            else:
                eth_total_points += 2
                
        # For take profit targets
        if coin_pred.get("take_profit_targets"):
            tp_match = re.findall(r'TP[0-9]+:', coin_pred["take_profit_targets"])
            for _ in tp_match:
                if coin_name == "BTC":
                    btc_total_points += 1
                else:
                    eth_total_points += 1
                
        # For stop loss
        if coin_pred.get("stop_loss"):
            if coin_name == "BTC":
                btc_total_points += 1
            else:
                eth_total_points += 1
    
    # Count hits from validation points
    for point in validation_points:
        if point["coin"] == "BTC":
            if "ENTRY_POINT_HIT" in point["type"]:
                btc_hit_points += 2
            elif "TP" in point["type"]:
                btc_hit_points += 1
            # We don't count stop loss as a positive hit
        else:  # ETH
            if "ENTRY_POINT_HIT" in point["type"]:
                eth_hit_points += 2
            elif "TP" in point["type"]:
                eth_hit_points += 1
    
    # Calculate accuracy for each coin
    btc_accuracy = (btc_hit_points / btc_total_points * 100) if btc_total_points > 0 else 0
    eth_accuracy = (eth_hit_points / eth_total_points * 100) if eth_total_points > 0 else 0
    
    # Weight by confidence
    total_weight = btc_weight + eth_weight
    if total_weight > 0:
        weighted_accuracy = (btc_accuracy * btc_weight + eth_accuracy * eth_weight) / total_weight
    else:
        weighted_accuracy = (btc_accuracy + eth_accuracy) / 2
    
    return weighted_accuracy

if __name__ == "__main__":
    print("[INFO] Starting validation script...")
    validate_predictions()
