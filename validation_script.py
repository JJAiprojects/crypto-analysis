#!/usr/bin/env python3

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import re
from ml_enhancer import PredictionEnhancer
from risk_manager import RiskManager
from dotenv import load_dotenv

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

def send_telegram_message(message, is_test=False):
    """Send a message to Telegram with proper bot selection"""
    config = load_config()
    
    # Select appropriate bot token and chat ID
    if is_test and config["test_mode"]["enabled"]:
        bot_token = config["telegram"]["test_bot_token"]
        chat_id = config["telegram"]["test_chat_id"]
        print("[TEST] Using test Telegram bot")
    else:
        bot_token = config["telegram"]["bot_token"]
        chat_id = config["telegram"]["chat_id"]
    
    if not bot_token or not chat_id:
        print("[WARN] Telegram credentials not configured")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
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

def load_config():
    """Load configuration with proper handling of sensitive data"""
    # Load environment variables
    load_dotenv()
    
    default_config = {
        "telegram": {
            "enabled": True,
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
            "test_bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN", ""),
            "test_chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID", "")
        },
        "test_mode": {
            "enabled": False,
            "send_telegram": False,
            "output_prefix": "test_"
        }
    }
    
    # Load non-sensitive config from config.json
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
        except Exception as e:
            print(f"[ERROR] Loading config: {e}")
    return default_config

def validate_predictions():
    """Validate predictions and update accuracy metrics"""
    # Log times in different timezones
    server_time = datetime.now()
    utc_time = datetime.utcnow()
    print(f"[INFO] UTC time: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Server time: {server_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Server timezone: {time.tzname[0]}")
    print(f"[INFO] Expected Vietnam time: {(utc_time + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load config
    config = load_config()
    
    if config["test_mode"]["enabled"]:
        print("[TEST] Running in test mode")
        print("[TEST] Using test Telegram bot")
    
    # Use test file if in test mode
    prediction_file = "detailed_predictions.json"
    if config["test_mode"]["enabled"]:
        prediction_file = config["test_mode"]["output_prefix"] + prediction_file
        print(f"[TEST] Using test prediction file: {prediction_file}")
    
    if not os.path.exists(prediction_file):
        print("[INFO] No predictions to validate yet")
        return
    
    try:
    # Load predictions
        with open(prediction_file, "r") as f:
            predictions = json.load(f)
        
        if not predictions:
            print("[INFO] No predictions to validate")
        return
            
        # Get the most recent prediction for notifications
        latest_prediction = predictions[-1]
        
        # Get current prices
        prices = get_crypto_prices()
        
        # Initialize ML enhancer and risk manager
        ml_enhancer = PredictionEnhancer()
        risk_manager = RiskManager()
        
        # Track notifications to send (only for latest prediction)
        notifications = []
        
        # Process all predictions for tracking
        for pred in predictions:
            if pred.get("validated"):
                continue
                
            pred_date = datetime.strptime(pred["date"], "%Y-%m-%d")
            pred_session = pred.get("session", "unknown")
            
            # Skip if prediction is too recent (less than 1 hour old)
            if (datetime.now() - pred_date).total_seconds() < 3600:
                continue
                
            # Validate direction predictions
            if "predictions" in pred:
                ai_pred = pred["predictions"].get("ai_prediction", {})
                ml_pred = pred["predictions"].get("ml_predictions", {})
                
                # Validate AI predictions
                if "btc_prediction" in ai_pred:
                    btc_pred = ai_pred["btc_prediction"]
                    btc_direction = btc_pred.get("direction", "").lower()
                    btc_entry = extract_price_range(btc_pred.get("entry_price_range", ""))
                    btc_tp = extract_take_profits(btc_pred.get("take_profit_targets", ""))
                    btc_sl = extract_price(btc_pred.get("stop_loss", ""))
                    
                    # Add validation points for all predictions
                    add_validation_point(pred, "BTC", "ENTRY_POINT_HIT", btc_entry, prices["btc"])
                    for i, tp in enumerate(btc_tp, 1):
                        add_validation_point(pred, "BTC", f"TP{i}_HIT", tp, prices["btc"])
                    add_validation_point(pred, "BTC", "STOP_LOSS_HIT", btc_sl, prices["btc"])
                    
                    # Only track notifications for the latest prediction
                    if pred == latest_prediction:
                        if add_validation_point(pred, "BTC", "ENTRY_POINT_HIT", btc_entry, prices["btc"]):
                            notifications.append({
                                "type": "entry_point",
                                "coin": "BTC",
                                "price": prices["btc"],
                                "range": btc_entry,
                                "direction": btc_direction,
                                "prediction_date": pred_date.strftime("%Y-%m-%d %H:%M")
                            })
                        
                        for i, tp in enumerate(btc_tp, 1):
                            if add_validation_point(pred, "BTC", f"TP{i}_HIT", tp, prices["btc"]):
                                notifications.append({
                                    "type": "take_profit",
                            "coin": "BTC",
                                    "price": prices["btc"],
                            "target": tp,
                                    "level": i,
                                    "prediction_date": pred_date.strftime("%Y-%m-%d %H:%M")
                                })
                        
                        if add_validation_point(pred, "BTC", "STOP_LOSS_HIT", btc_sl, prices["btc"]):
                            notifications.append({
                                "type": "stop_loss",
                            "coin": "BTC",
                                "price": prices["btc"],
                                "target": btc_sl,
                                "prediction_date": pred_date.strftime("%Y-%m-%d %H:%M")
                            })
                
                # Do the same for ETH predictions
                if "eth_prediction" in ai_pred:
                    eth_pred = ai_pred["eth_prediction"]
                    eth_direction = eth_pred.get("direction", "").lower()
                    eth_entry = extract_price_range(eth_pred.get("entry_price_range", ""))
                    eth_tp = extract_take_profits(eth_pred.get("take_profit_targets", ""))
                    eth_sl = extract_price(eth_pred.get("stop_loss", ""))
                    
                    # Add validation points for all predictions
                    add_validation_point(pred, "ETH", "ENTRY_POINT_HIT", eth_entry, prices["eth"])
                    for i, tp in enumerate(eth_tp, 1):
                        add_validation_point(pred, "ETH", f"TP{i}_HIT", tp, prices["eth"])
                    add_validation_point(pred, "ETH", "STOP_LOSS_HIT", eth_sl, prices["eth"])
                    
                    # Only track notifications for the latest prediction
                    if pred == latest_prediction:
                        if add_validation_point(pred, "ETH", "ENTRY_POINT_HIT", eth_entry, prices["eth"]):
                            notifications.append({
                                "type": "entry_point",
                                "coin": "ETH",
                                "price": prices["eth"],
                                "range": eth_entry,
                                "direction": eth_direction,
                                "prediction_date": pred_date.strftime("%Y-%m-%d %H:%M")
                            })
                        
                        for i, tp in enumerate(eth_tp, 1):
                            if add_validation_point(pred, "ETH", f"TP{i}_HIT", tp, prices["eth"]):
                                notifications.append({
                                    "type": "take_profit",
                            "coin": "ETH",
                                    "price": prices["eth"],
                            "target": tp,
                                    "level": i,
                                    "prediction_date": pred_date.strftime("%Y-%m-%d %H:%M")
                                })
                        
                        if add_validation_point(pred, "ETH", "STOP_LOSS_HIT", eth_sl, prices["eth"]):
                            notifications.append({
                                "type": "stop_loss",
                            "coin": "ETH",
                                "price": prices["eth"],
                                "target": eth_sl,
                                "prediction_date": pred_date.strftime("%Y-%m-%d %H:%M")
                            })
            
            # Mark prediction as validated
            pred["validated"] = True
            pred["validation_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save updated predictions
            with open(prediction_file, "w") as f:
                json.dump(predictions, f, indent=4)
        
        # Calculate and save overall accuracy metrics
        accuracy_metrics = calculate_prediction_accuracy(predictions)
        
        # Send notifications only for the latest prediction
        if notifications:
            for notification in notifications:
                message = format_notification_message(notification)
                send_telegram_message(message, is_test=config["test_mode"]["enabled"])
        
        # Send accuracy summary if it's 7:45 PM local time
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        if current_hour == 19 and current_minute >= 45:  # 7:45 PM
            message = format_accuracy_summary(accuracy_metrics)
            send_telegram_message(message, is_test=config["test_mode"]["enabled"])
        
        print("[INFO] Predictions validated successfully")
        
    except Exception as e:
        print(f"[ERROR] Failed to validate predictions: {e}")

def format_notification_message(notification):
    """Format a notification message for Telegram"""
    if notification["type"] == "entry_point":
        min_price, max_price = notification["range"]
        return (
            f"🎯 <b>ENTRY POINT REACHED</b>\n\n"
            f"Coin: {notification['coin']}\n"
            f"Current Price: ${notification['price']:,.2f}\n"
            f"Entry Range: ${min_price:,.2f} - ${max_price:,.2f}\n"
            f"Direction: {notification['direction'].upper()}\n"
            f"Prediction Date: {notification['prediction_date']}\n\n"
            f"<i>Price has entered the recommended entry zone. Consider your position based on the original prediction.</i>"
        )
    elif notification["type"] == "take_profit":
        return (
            f"💰 <b>TAKE PROFIT TARGET HIT</b>\n\n"
            f"Coin: {notification['coin']}\n"
            f"Current Price: ${notification['price']:,.2f}\n"
            f"TP{notification['level']}: ${notification['target']:,.2f}\n"
            f"Prediction Date: {notification['prediction_date']}\n\n"
            f"<i>Price has reached take profit target {notification['level']}. Consider taking profits or moving stop loss to break even.</i>"
        )
    elif notification["type"] == "stop_loss":
        return (
            f"⚠️ <b>STOP LOSS TRIGGERED</b>\n\n"
            f"Coin: {notification['coin']}\n"
            f"Current Price: ${notification['price']:,.2f}\n"
            f"Stop Loss: ${notification['target']:,.2f}\n"
            f"Prediction Date: {notification['prediction_date']}\n\n"
            f"<i>Price has hit the stop loss level. Trade has been closed at a loss.</i>"
        )
    elif notification["type"] in ["risk_stop_loss", "risk_take_profit"]:
        type_str = "RISK STOP LOSS" if notification["type"] == "risk_stop_loss" else "RISK TAKE PROFIT"
        return (
            f"🎯 <b>{type_str} HIT</b>\n\n"
            f"Coin: {notification['coin']}\n"
            f"Current Price: ${notification['price']:,.2f}\n"
            f"Target: ${notification['target']:,.2f}\n"
            f"Prediction Date: {notification['prediction_date']}\n\n"
            f"<i>Price has reached the risk management target. Review your position.</i>"
        )

def format_accuracy_summary(metrics):
    """Format accuracy metrics summary for Telegram"""
    # Calculate overall accuracy
    total_accuracy = (
        metrics['direction_accuracy'] * 0.4 +  # 40% weight for direction
        metrics['tp_hit_rate'] * 0.4 +         # 40% weight for take profits
        metrics['ml_accuracy'] * 0.2           # 20% weight for ML model
    ) * 100

    return (
        f"📊 <b>PREDICTION CYCLE SUMMARY</b>\n\n"
        f"Overall Accuracy: {total_accuracy:.1f}%\n\n"
        f"<b>Breakdown:</b>\n"
        f"• Direction Accuracy: {metrics['direction_accuracy']*100:.1f}%\n"
        f"  - How often we correctly predicted price direction\n\n"
        f"• Take Profit Hit Rate: {metrics['tp_hit_rate']*100:.1f}%\n"
        f"  - How often price reached our profit targets\n\n"
        f"• Stop Loss Hit Rate: {metrics['sl_hit_rate']*100:.1f}%\n"
        f"  - How often price hit our stop losses\n\n"
        f"• ML Model Accuracy: {metrics['ml_accuracy']*100:.1f}%\n"
        f"  - How often our ML model's predictions were correct\n\n"
        f"• Risk-Reward Ratio: {metrics['risk_reward_ratio']:.2f}\n"
        f"  - Ratio of successful trades to losing trades\n\n"
        f"<i>Based on {metrics['validated_predictions']} validated predictions</i>"
    )

def extract_price_range(price_str):
    """Extract price range from string"""
    if not price_str:
        return None
    try:
        # Extract two prices from range (e.g., "$1000 - $2000")
        matches = re.findall(r'\$?(\d+(?:,\d+)*(?:\.\d+)?)', price_str)
        if len(matches) >= 2:
            return (float(matches[0].replace(',', '')), float(matches[1].replace(',', '')))
    except Exception:
        pass
    return None

def extract_take_profits(price_str):
    """Extract take profit targets from string"""
    if not price_str:
        return []
    try:
        # Extract prices from TP format (e.g., "TP1: $1000, TP2: $2000")
        matches = re.findall(r'TP\d+:\s*\$?(\d+(?:,\d+)*(?:\.\d+)?)', price_str)
        return [float(match.replace(',', '')) for match in matches]
    except Exception:
        return []

def extract_price(price_str):
    """Extract single price from string"""
    if not price_str:
        return None
    try:
        match = re.search(r'\$?(\d+(?:,\d+)*(?:\.\d+)?)', price_str)
        if match:
            return float(match.group(1).replace(',', ''))
    except Exception:
        pass
    return None

def add_validation_point(prediction, coin, point_type, target_price, current_price):
    """Add a validation point if price target was hit"""
    if not target_price or not current_price:
        return False
    
    # For price ranges, check if current price is within range
    if isinstance(target_price, tuple):
        min_price, max_price = target_price
        if min_price <= current_price <= max_price:
            prediction["validation_points"].append({
                "coin": coin,
                "type": point_type,
                "target_price": target_price,
                "current_price": current_price,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return True
    # For single price points, check if price crossed the target
    else:
        if point_type.startswith("TP"):
            if current_price >= target_price:
                prediction["validation_points"].append({
                    "coin": coin,
                    "type": point_type,
                    "target_price": target_price,
                    "current_price": current_price,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                return True
        elif point_type == "STOP_LOSS_HIT":
            if current_price <= target_price:
                prediction["validation_points"].append({
                    "coin": coin,
                    "type": point_type,
                    "target_price": target_price,
                    "current_price": current_price,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                return True
    
    return False

def calculate_prediction_accuracy(predictions):
    """Calculate and save overall prediction accuracy metrics"""
    accuracy_metrics = {
        "total_predictions": len(predictions),
        "validated_predictions": 0,
        "direction_accuracy": 0,
        "tp_hit_rate": 0,
        "sl_hit_rate": 0,
        "risk_reward_ratio": 0,
        "ml_accuracy": 0
    }
    
    total_direction = 0
    correct_direction = 0
    total_tp = 0
    hit_tp = 0
    total_sl = 0
    hit_sl = 0
    total_ml = 0
    correct_ml = 0
    
    for pred in predictions:
        if not pred.get("validated"):
            continue
            
        accuracy_metrics["validated_predictions"] += 1
        
        # Calculate direction accuracy
        if "predictions" in pred:
            ai_pred = pred["predictions"].get("ai_prediction", {})
            if "btc_prediction" in ai_pred:
                btc_pred = ai_pred["btc_prediction"]
                direction = btc_pred.get("direction", "").lower()
                if direction in ["bullish", "bearish", "sideways"]:
                    total_direction += 1
                    # Check if direction was correct based on validation points
                    if any(p["type"].startswith("TP") for p in pred.get("validation_points", [])):
                        correct_direction += 1
        
        # Calculate TP/SL hit rates
        validation_points = pred.get("validation_points", [])
        for point in validation_points:
            if point["type"].startswith("TP"):
                total_tp += 1
                if point["type"].endswith("_HIT"):
                    hit_tp += 1
            elif point["type"] == "STOP_LOSS_HIT":
                total_sl += 1
                if point["type"] == "STOP_LOSS_HIT":
                    hit_sl += 1
        
        # Calculate ML accuracy
        if "predictions" in pred and "ml_predictions" in pred["predictions"]:
            ml_pred = pred["predictions"]["ml_predictions"]
            if "direction" in ml_pred:
                total_ml += 1
                ml_direction = ml_pred["direction"]["prediction"]
                # Check if ML direction was correct
                if any(p["type"].startswith("TP") for p in validation_points):
                    correct_ml += 1
    
    # Calculate final metrics
    if total_direction > 0:
        accuracy_metrics["direction_accuracy"] = correct_direction / total_direction
    if total_tp > 0:
        accuracy_metrics["tp_hit_rate"] = hit_tp / total_tp
    if total_sl > 0:
        accuracy_metrics["sl_hit_rate"] = hit_sl / total_sl
    if total_ml > 0:
        accuracy_metrics["ml_accuracy"] = correct_ml / total_ml
    
    # Calculate risk-reward ratio
    if hit_tp > 0 and hit_sl > 0:
        accuracy_metrics["risk_reward_ratio"] = hit_tp / hit_sl
    
    # Save accuracy metrics
    with open("prediction_accuracy.json", "w") as f:
        json.dump(accuracy_metrics, f, indent=4)
    
    return accuracy_metrics

if __name__ == "__main__":
    # Check for test mode argument
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        config = load_config()
        config["test_mode"]["enabled"] = True
        print("[TEST] Test mode enabled")
    validate_predictions()
