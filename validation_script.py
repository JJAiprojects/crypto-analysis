#!/usr/bin/env python3

import requests
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import os
import re
from ml_enhancer import PredictionEnhancer
from risk_manager import RiskManager
from professional_analysis import ProfessionalTraderAnalysis
from telegram_utils import send_telegram_message
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

def is_duplicate_validation_point(validation_points, new_point):
    """Check if a validation point is already in the list"""
    for point in validation_points:
        if (point["coin"] == new_point["coin"] and 
            point["type"] == new_point["type"] and
            point.get("predicted_level") == new_point.get("predicted_level")):
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
            "params": {},
            "extract": lambda data: {
                "btc": next((float(item["price"]) for item in data if item["symbol"] == "BTCUSDT"), None),
                "eth": next((float(item["price"]) for item in data if item["symbol"] == "ETHUSDT"), None)
            }
        }
    ]
    
    errors = []
    
    # Try each API in order
    for api in apis:
        try:
            print(f"[INFO] Trying to get prices from {api['name']}...")
            if api["name"] == "Binance":
                # For Binance, get both symbols in one call
                response = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=10)
            else:
                response = requests.get(api["url"], params=api["params"], timeout=10)
            
            response.raise_for_status()
            data = response.json()
            
            # Extract prices using the provided extract function
            prices = api["extract"](data)
            
            # Validate that both prices were retrieved
            if prices["btc"] is not None and prices["eth"] is not None:
                print(f"[INFO] Successfully retrieved prices from {api['name']}")
                print(f"[INFO] Current prices: BTC=${prices['btc']:,.2f}, ETH=${prices['eth']:,.2f}")
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
            "test": {
                "bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN", ""),
                "chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID", "")
            }
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
    """Enhanced validation with ML learning and professional analysis integration"""
    # Log times in different timezones
    server_time = datetime.now()
    utc_time = datetime.now(timezone.utc)
    print(f"[INFO] UTC time: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Server time: {server_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Expected Vietnam time: {(utc_time + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load config
    config = load_config()
    
    if config["test_mode"]["enabled"]:
        print("[TEST] Running validation in test mode")
    
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
    
        # Initialize components
        ml_enhancer = PredictionEnhancer()
        risk_manager = RiskManager()
        professional_trader = ProfessionalTraderAnalysis()
        
        # Get current prices
        prices = get_crypto_prices()
        
        # Track notifications and improvements
        notifications = []
        ml_training_data = []
        
        # Get the latest prediction for detailed tracking
        latest_prediction = predictions[-1] if predictions else None
        
        # Process all unvalidated predictions
        for pred in predictions:
            pred_timestamp = datetime.strptime(pred["timestamp"], "%Y-%m-%d %H:%M:%S")
            
            # Skip very recent predictions (less than 1 hour old)
            if (datetime.now() - pred_timestamp).total_seconds() < 3600:
                continue
            
            # Initialize validation points if not exists
            if "validation_points" not in pred:
                pred["validation_points"] = []
            
            # Extract professional analysis predictions
            ai_pred = pred.get("predictions", {}).get("ai_prediction", "")
            pro_analysis = pred.get("predictions", {}).get("professional_analysis", {})
            ml_pred = pred.get("predictions", {}).get("ml_predictions", {})
            
            # Enhanced target extraction for professional format
            if pro_analysis and "price_targets" in pro_analysis:
                btc_targets = {
                    "current": pro_analysis["price_targets"].get("current"),
                    "target_1": pro_analysis["price_targets"].get("target_1"),
                    "target_2": pro_analysis["price_targets"].get("target_2"),
                    "stop_loss": pro_analysis["price_targets"].get("stop_loss"),
                    "scenario": pro_analysis.get("primary_scenario", "NEUTRAL")
                }
                
                # Validate BTC targets
                validate_professional_targets(pred, "BTC", btc_targets, prices["btc"], latest_prediction == pred, notifications)
            
            # Also validate any AI predictions (fallback/additional)
            targets = extract_professional_targets(ai_pred)
            for coin in ["BTC", "ETH"]:
                if targets[coin]:
                    price = prices[coin.lower()]
                    validate_legacy_targets(pred, coin, targets[coin], price, latest_prediction == pred, notifications)
            
            # Collect ML training data
            if not pred.get("ml_processed", False):
                training_point = {
                    "prediction_data": pred,
                    "actual_btc_price": prices["btc"],
                    "actual_eth_price": prices["eth"],
                    "validation_points": pred["validation_points"],
                    "timestamp": datetime.now().isoformat()
                }
                ml_training_data.append(training_point)
                pred["ml_processed"] = True
            
            # Mark as validated
            if not pred.get("hourly_validated"):
                pred["hourly_validated"] = True
                pred["last_validation"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Save updated predictions
        with open(prediction_file, "w") as f:
            json.dump(predictions, f, indent=4)
        
        # Train ML models with new data
        if ml_training_data:
            print(f"[INFO] Training ML models with {len(ml_training_data)} new data points")
            try:
                ml_enhancer.incremental_learning(ml_training_data)
                print("[INFO] ML incremental learning completed")
            except Exception as e:
                print(f"[ERROR] ML training failed: {e}")
        
        # Send notifications for latest prediction
        if notifications:
            print(f"[INFO] Sending {len(notifications)} validation notifications")
            for notification in notifications[-3:]:  # Limit to last 3 notifications
                message = format_notification_message(notification)
                send_telegram_message(message, is_test=config["test_mode"]["enabled"])
        
        # Check if it's time for accuracy report (7:45 PM and 7:45 AM)
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        
        # Send accuracy report at 7:45 PM (19:45) for 8 AM predictions
        # Send accuracy report at 7:45 AM (07:45) for 8 PM predictions from previous day
        if (current_hour == 19 and 45 <= current_minute <= 59) or (current_hour == 7 and 45 <= current_minute <= 59):
            if current_hour == 19:
                report_type = "8 AM predictions"
            else:
                report_type = "8 PM predictions (previous day)"
            
            print(f"[INFO] Generating daily accuracy report for {report_type}")
            accuracy_metrics = calculate_enhanced_accuracy(predictions)
            accuracy_message = format_accuracy_summary(accuracy_metrics)
            send_telegram_message(accuracy_message, is_test=config["test_mode"]["enabled"])
            
            # Also send improvement suggestions to AI
            improvement_data = generate_improvement_suggestions(accuracy_metrics, predictions)
            save_improvement_data(improvement_data)
        
        # Weekly Deep Learning Analysis - Every Sunday at 8 PM
        current_weekday = datetime.now().weekday()  # 6 = Sunday
        if current_weekday == 6 and current_hour == 20 and 0 <= current_minute <= 15:
            print("[INFO] Generating weekly deep learning analysis...")
            weekly_insights = generate_deep_learning_insights(predictions, "weekly")
            save_deep_learning_insights(weekly_insights)
            
            # Send comprehensive weekly report
            weekly_report = format_deep_insights_summary(weekly_insights)
            send_telegram_message(weekly_report, is_test=config["test_mode"]["enabled"])
            print("[INFO] Weekly deep learning analysis completed")
        
        # Monthly Deep Learning Analysis - Every 1st of month at 8 PM
        current_day = datetime.now().day
        if current_day == 1 and current_hour == 20 and 0 <= current_minute <= 15:
            print("[INFO] Generating monthly deep learning analysis...")
            monthly_insights = generate_deep_learning_insights(predictions, "monthly")
            save_deep_learning_insights(monthly_insights)
            
            # Send comprehensive monthly report
            monthly_report = format_deep_insights_summary(monthly_insights)
            send_telegram_message(monthly_report, is_test=config["test_mode"]["enabled"])
            print("[INFO] Monthly deep learning analysis completed")
            
            # Also trigger ML model retraining with insights
            try:
                ml_enhancer.learn_from_insights(monthly_insights)
                print("[INFO] ML models updated with monthly insights")
            except Exception as e:
                print(f"[ERROR] Failed to update ML models with insights: {e}")
        
        print("[INFO] Enhanced prediction validation completed successfully")
        
    except Exception as e:
        print(f"[ERROR] Failed to validate predictions: {e}")
        import traceback
        traceback.print_exc()

def validate_professional_targets(prediction, coin, targets, current_price, is_latest, notifications):
    """Validate professional analysis targets"""
    if not targets or not current_price:
        return
    
    scenario = targets.get("scenario", "NEUTRAL")
    
    # Check target 1
    if targets.get("target_1") and validate_target_hit(current_price, targets["target_1"], "TARGET_1", scenario):
        validation_point = {
            "coin": coin,
            "type": "PROFESSIONAL_TARGET_1",
            "predicted_level": targets["target_1"],
            "actual_price": current_price,
            "scenario": scenario,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
            prediction.setdefault("validation_points", []).append(validation_point)
            
            if is_latest:
                notifications.append({
                    "type": "professional_target",
                    "coin": coin,
                    "target_level": 1,
                    "predicted_price": targets["target_1"],
                    "actual_price": current_price,
                    "scenario": scenario
                })
    
    # Check target 2
    if targets.get("target_2") and validate_target_hit(current_price, targets["target_2"], "TARGET_2", scenario):
        validation_point = {
            "coin": coin,
            "type": "PROFESSIONAL_TARGET_2", 
            "predicted_level": targets["target_2"],
            "actual_price": current_price,
            "scenario": scenario,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
            prediction.setdefault("validation_points", []).append(validation_point)
            
            if is_latest:
                notifications.append({
                    "type": "professional_target",
                    "coin": coin,
                    "target_level": 2,
                    "predicted_price": targets["target_2"],
                    "actual_price": current_price,
                    "scenario": scenario
                })
            
    # Check stop loss
    if targets.get("stop_loss") and validate_target_hit(current_price, targets["stop_loss"], "STOP_LOSS", scenario):
        validation_point = {
            "coin": coin,
            "type": "PROFESSIONAL_STOP_LOSS",
            "predicted_level": targets["stop_loss"],
            "actual_price": current_price,
            "scenario": scenario,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
            prediction.setdefault("validation_points", []).append(validation_point)
            
            if is_latest:
                notifications.append({
                    "type": "professional_stop_loss",
                    "coin": coin,
                    "predicted_price": targets["stop_loss"],
                    "actual_price": current_price,
                    "scenario": scenario
                })

def validate_legacy_targets(prediction, coin, targets, current_price, is_latest, notifications):
    """Validate legacy AI prediction format targets"""
    # Implementation for backward compatibility with older prediction formats
    pass

def calculate_enhanced_accuracy(predictions):
    """Calculate enhanced accuracy metrics for professional analysis with comprehensive trading metrics"""
    metrics = {
        "total_predictions": len(predictions),
        "validated_predictions": 0,
        "professional_accuracy": 0,
        "confidence_accuracy": 0,
        "scenario_accuracy": 0,
        "target_hit_rate": 0,
        "stop_loss_rate": 0,
        "average_confidence": 0,
        "ml_improvement": 0,
        # Enhanced trader-style metrics
        "win_rate_overall": 0,
        "win_rate_long": 0,
        "win_rate_short": 0,
        "average_rr_ratio": 0,
        "r_expectancy": 0,
        "best_timeframe": "unknown",
        "best_setup_type": "unknown",
        "volatility_performance": {},
        "sentiment_performance": {},
        "confluence_performance": {},
        "worst_mistakes": [],
        "prediction_patterns": {}
    }
    
    recent_predictions = [p for p in predictions if datetime.strptime(p["timestamp"], "%Y-%m-%d %H:%M:%S") > datetime.now() - timedelta(days=30)]
    
    if not recent_predictions:
        return metrics
    
    # Track detailed metrics for each prediction
    long_trades = []
    short_trades = []
    all_trades = []
    timeframe_performance = {}
    setup_performance = {}
    volatility_bins = {"low": [], "medium": [], "high": []}
    sentiment_bins = {"fear": [], "neutral": [], "greed": []}
    
    for pred in recent_predictions:
        if not pred.get("validation_points"):
            continue
            
        metrics["validated_predictions"] += 1
        
        # Extract trade details
        trade_data = extract_trade_metrics(pred)
        if not trade_data:
            continue
            
        all_trades.append(trade_data)
        
        # Categorize by direction
        if trade_data["direction"] in ["LONG", "BUY", "STRONG BUY"]:
            long_trades.append(trade_data)
        elif trade_data["direction"] in ["SHORT", "SELL", "STRONG SELL"]:
            short_trades.append(trade_data)
        
        # Group by timeframe (hour of prediction)
        hour = datetime.strptime(pred["timestamp"], "%Y-%m-%d %H:%M:%S").hour
        timeframe_key = f"{hour:02d}:00"
        if timeframe_key not in timeframe_performance:
            timeframe_performance[timeframe_key] = []
        timeframe_performance[timeframe_key].append(trade_data)
        
        # Group by setup type (confluence signals)
        setup_type = identify_setup_type(pred)
        if setup_type not in setup_performance:
            setup_performance[setup_type] = []
        setup_performance[setup_type].append(trade_data)
        
        # Group by volatility
        volatility = trade_data.get("volatility", "medium")
        if volatility in volatility_bins:
            volatility_bins[volatility].append(trade_data)
        
        # Group by sentiment
        fear_greed = trade_data.get("fear_greed", 50)
        if fear_greed < 40:
            sentiment_bins["fear"].append(trade_data)
        elif fear_greed > 60:
            sentiment_bins["greed"].append(trade_data)
        else:
            sentiment_bins["neutral"].append(trade_data)
    
    # Calculate overall metrics
    if all_trades:
        winning_trades = [t for t in all_trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
        metrics["win_rate_overall"] = len(winning_trades) / len(all_trades)
        
        # Calculate R-expectancy
        total_r = sum(t["r_multiple"] for t in all_trades)
        metrics["r_expectancy"] = total_r / len(all_trades)
        
        # Average RR ratio
        rr_ratios = [t["rr_ratio"] for t in all_trades if t["rr_ratio"] > 0]
        metrics["average_rr_ratio"] = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0
    
    # Calculate directional win rates
    if long_trades:
        long_wins = [t for t in long_trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
        metrics["win_rate_long"] = len(long_wins) / len(long_trades)
    
    if short_trades:
        short_wins = [t for t in short_trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
        metrics["win_rate_short"] = len(short_wins) / len(short_trades)
    
    # Find best performing timeframe
    best_timeframe_rate = 0
    for timeframe, trades in timeframe_performance.items():
        if len(trades) >= 3:  # Minimum sample size
            wins = [t for t in trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
            win_rate = len(wins) / len(trades)
            if win_rate > best_timeframe_rate:
                best_timeframe_rate = win_rate
                metrics["best_timeframe"] = f"{timeframe} ({win_rate:.1%})"
    
    # Find best performing setup
    best_setup_rate = 0
    for setup, trades in setup_performance.items():
        if len(trades) >= 3:
            wins = [t for t in trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
            win_rate = len(wins) / len(trades)
            if win_rate > best_setup_rate:
                best_setup_rate = win_rate
                metrics["best_setup_type"] = f"{setup} ({win_rate:.1%})"
    
    # Analyze volatility performance
    for vol_level, trades in volatility_bins.items():
        if trades:
            wins = [t for t in trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
            metrics["volatility_performance"][vol_level] = {
                "win_rate": len(wins) / len(trades),
                "avg_duration": sum(t["duration_hours"] for t in trades) / len(trades),
                "trade_count": len(trades)
            }
    
    # Analyze sentiment performance
    for sentiment, trades in sentiment_bins.items():
        if trades:
            wins = [t for t in trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
            metrics["sentiment_performance"][sentiment] = {
                "win_rate": len(wins) / len(trades),
                "avg_rr": sum(t["rr_ratio"] for t in trades) / len(trades),
                "trade_count": len(trades)
            }
    
    # Identify worst mistakes (recurring patterns)
    mistake_patterns = identify_mistake_patterns(all_trades)
    metrics["worst_mistakes"] = mistake_patterns[:5]  # Top 5 mistakes
    
    # Store prediction patterns for future analysis
    metrics["prediction_patterns"] = {
        "total_trades": len(all_trades),
        "timeframe_distribution": {k: len(v) for k, v in timeframe_performance.items()},
        "setup_distribution": {k: len(v) for k, v in setup_performance.items()},
        "avg_confidence_winners": sum(t["confidence"] for t in all_trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]) / max(1, len([t for t in all_trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]])),
        "avg_confidence_losers": sum(t["confidence"] for t in all_trades if t["outcome"] == "SL_HIT") / max(1, len([t for t in all_trades if t["outcome"] == "SL_HIT"]))
    }
    
    return metrics

def extract_trade_metrics(prediction):
    """Extract comprehensive trade metrics from a prediction for advanced analysis"""
    try:
        # Get prediction details
        pro_analysis = prediction.get("predictions", {}).get("professional_analysis", {})
        if not pro_analysis:
            return None
        
        price_targets = pro_analysis.get("price_targets", {})
        market_data = prediction.get("market_data", {})
        
        # Determine outcome from validation points
        validation_points = prediction.get("validation_points", [])
        outcome = "PENDING"
        actual_exit_price = None
        duration_hours = 0
        
        for vp in validation_points:
            if vp["type"] in ["PROFESSIONAL_TARGET_1", "PROFESSIONAL_TARGET_2"]:
                outcome = "TP_HIT"
                actual_exit_price = vp["actual_price"]
                break
            elif vp["type"] == "PROFESSIONAL_STOP_LOSS":
                outcome = "SL_HIT"
                actual_exit_price = vp["actual_price"]
                break
        
        if outcome == "PENDING":
            return None  # Skip pending trades for analysis
        
        # Calculate metrics
        entry_price = price_targets.get("current", 0)
        tp_price = price_targets.get("target_1", 0)
        sl_price = price_targets.get("stop_loss", 0)
        
        # Calculate R-multiple (how many R risked vs gained)
        risk = abs(entry_price - sl_price)
        if outcome == "TP_HIT":
            reward = abs(actual_exit_price - entry_price)
            r_multiple = reward / risk if risk > 0 else 0
        else:  # SL_HIT
            r_multiple = -1  # Lost 1R
        
        # Calculate RR ratio
        potential_reward = abs(tp_price - entry_price)
        rr_ratio = potential_reward / risk if risk > 0 else 0
        
        # Extract market conditions
        btc_rsi = market_data.get("btc_rsi", 50)
        fear_greed = market_data.get("fear_greed", 50)
        if isinstance(fear_greed, dict):
            fear_greed = fear_greed.get("index", 50)
        
        # Determine volatility level based on ATR or price movement
        volatility = "medium"  # Default
        btc_price = market_data.get("btc_price", 0)
        if btc_price:
            # Simple volatility estimation
            if abs(tp_price - entry_price) / entry_price > 0.05:
                volatility = "high"
            elif abs(tp_price - entry_price) / entry_price < 0.02:
                volatility = "low"
        
        return {
            "timestamp": prediction["timestamp"],
            "direction": pro_analysis.get("primary_scenario", "NEUTRAL"),
            "entry_price": entry_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "actual_exit_price": actual_exit_price,
            "outcome": outcome,
            "r_multiple": r_multiple,
            "rr_ratio": rr_ratio,
            "duration_hours": duration_hours,
            "confidence": pro_analysis.get("confidence_level", 50),
            "rsi": btc_rsi,
            "fear_greed": fear_greed,
            "volatility": volatility,
            "bullish_probability": pro_analysis.get("bullish_probability", 50),
            "bearish_probability": pro_analysis.get("bearish_probability", 50),
            "strongest_signal": pro_analysis.get("key_factors", {}).get("strongest_signal", ["unknown", 0])[0]
        }
    except Exception as e:
        print(f"[ERROR] Extracting trade metrics: {e}")
        return None

def identify_setup_type(prediction):
    """Identify the type of setup/confluence signals used"""
    try:
        pro_analysis = prediction.get("predictions", {}).get("professional_analysis", {})
        if not pro_analysis:
            return "basic"
        
        strongest_signal = pro_analysis.get("key_factors", {}).get("strongest_signal", ["unknown", 0])[0]
        scenario = pro_analysis.get("primary_scenario", "neutral")
        confidence = pro_analysis.get("confidence_level", "low")
        
        # Create setup type based on confluence
        component_scores = pro_analysis.get("component_scores", {})
        high_scoring_components = [k for k, v in component_scores.items() if v > 7.0]
        
        if len(high_scoring_components) >= 3:
            setup_type = "high_confluence"
        elif len(high_scoring_components) >= 2:
            setup_type = "medium_confluence"
        else:
            setup_type = "single_signal"
        
        # Add strongest signal to setup type
        setup_type += f"_{strongest_signal}"
        
        return setup_type
    except Exception:
        return "unknown"

def identify_mistake_patterns(trades):
    """Identify recurring mistake patterns that hurt performance"""
    mistakes = []
    
    if not trades:
        return mistakes
    
    # Analyze overconfidence
    overconfident_losses = [t for t in trades if t["confidence"] > 80 and t["outcome"] == "SL_HIT"]
    if len(overconfident_losses) / len(trades) > 0.3:
        mistakes.append({
            "type": "overconfidence",
            "description": f"High confidence trades ({len(overconfident_losses)}) hitting SL",
            "frequency": len(overconfident_losses),
            "impact": "Overestimating certainty in uncertain markets"
        })
    
    # Analyze poor RR trades
    poor_rr_trades = [t for t in trades if t["rr_ratio"] < 1.5 and t["outcome"] == "SL_HIT"]
    if len(poor_rr_trades) / len(trades) > 0.2:
        mistakes.append({
            "type": "poor_risk_reward",
            "description": f"Taking trades with RR < 1.5 that failed ({len(poor_rr_trades)})",
            "frequency": len(poor_rr_trades),
            "impact": "Not maintaining proper risk-reward ratios"
        })
    
    # Analyze sentiment timing
    greed_losses = [t for t in trades if t["fear_greed"] > 70 and t["direction"] in ["LONG", "BUY"] and t["outcome"] == "SL_HIT"]
    if len(greed_losses) > 3:
        mistakes.append({
            "type": "greed_timing",
            "description": f"Buying during extreme greed ({len(greed_losses)} failures)",
            "frequency": len(greed_losses),
            "impact": "Poor market timing - buying tops"
        })
    
    # Analyze RSI extremes
    rsi_overbought_losses = [t for t in trades if t["rsi"] > 70 and t["direction"] in ["LONG", "BUY"] and t["outcome"] == "SL_HIT"]
    if len(rsi_overbought_losses) > 2:
        mistakes.append({
            "type": "rsi_overbought",
            "description": f"Longing while RSI > 70 ({len(rsi_overbought_losses)} failures)",
            "frequency": len(rsi_overbought_losses),
            "impact": "Ignoring overbought conditions"
        })
    
    return sorted(mistakes, key=lambda x: x["frequency"], reverse=True)

def generate_improvement_suggestions(accuracy_metrics, predictions):
    """Generate suggestions for AI improvement based on validation results"""
    suggestions = {
        "timestamp": datetime.now().isoformat(),
        "accuracy_summary": accuracy_metrics,
        "improvement_areas": [],
        "successful_patterns": [],
        "recommendations": []
    }
    
    # Analyze accuracy and generate suggestions
    if accuracy_metrics["professional_accuracy"] < 0.6:
        suggestions["improvement_areas"].append("Professional target accuracy below 60%")
        suggestions["recommendations"].append("Adjust professional analysis weightings")
    
    if accuracy_metrics["target_hit_rate"] < 0.4:
        suggestions["improvement_areas"].append("Target hit rate too low")
        suggestions["recommendations"].append("Revise target distance calculations")
    
    if accuracy_metrics["average_confidence"] > 80 and accuracy_metrics["professional_accuracy"] < 0.7:
        suggestions["improvement_areas"].append("Overconfidence detected")
        suggestions["recommendations"].append("Calibrate confidence scoring system")
    
    return suggestions

def save_improvement_data(improvement_data):
    """Save improvement suggestions for AI learning"""
    improvement_file = "ai_improvement_log.json"
    
    improvements = []
    if os.path.exists(improvement_file):
        try:
            with open(improvement_file, "r") as f:
                improvements = json.load(f)
        except Exception:
            improvements = []
    
    improvements.append(improvement_data)
    
    # Keep only last 30 days of improvements
    cutoff = datetime.now() - timedelta(days=30)
    improvements = [imp for imp in improvements 
                   if datetime.fromisoformat(imp["timestamp"]) > cutoff]
    
    with open(improvement_file, "w") as f:
        json.dump(improvements, f, indent=4)

def format_notification_message(notification):
    """Format a notification message for Telegram"""
    if notification["type"] == "professional_target":
        return (
            f"🎯 <b>PROFESSIONAL TARGET HIT</b>\n\n"
            f"Coin: {notification['coin']}\n"
            f"Target Level: {notification['target_level']}\n"
            f"Predicted: ${notification['predicted_price']:,.2f}\n"
            f"Actual: ${notification['actual_price']:,.2f}\n"
            f"Scenario: {notification['scenario']}\n\n"
            f"<i>Professional analysis target reached successfully!</i>"
        )
    elif notification["type"] == "professional_stop_loss":
        return (
            f"⚠️ <b>PROFESSIONAL STOP LOSS HIT</b>\n\n"
            f"Coin: {notification['coin']}\n"
            f"Predicted: ${notification['predicted_price']:,.2f}\n"
            f"Actual: ${notification['actual_price']:,.2f}\n"
            f"Scenario: {notification['scenario']}\n\n"
            f"<i>Professional stop loss triggered. Position closed.</i>"
        )
    else:
        return f"📊 Validation update: {notification['type']} for {notification['coin']}"

def format_accuracy_summary(metrics):
    """Format enhanced accuracy metrics summary for Telegram - Professional Trader Style"""
    overall_score = (
        metrics.get('win_rate_overall', 0) * 0.4 +
        max(0, metrics.get('r_expectancy', 0)) * 0.3 +
        min(1, metrics.get('average_rr_ratio', 0) / 2) * 0.3
    ) * 100

    # Format the comprehensive report
    report = f"📊 <b>PROFESSIONAL TRADING PERFORMANCE</b>\n"
    report += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    report += f"{'═' * 35}\n\n"
    
    # Overall Performance
    report += f"🏆 <b>OVERALL SCORE: {overall_score:.1f}%</b>\n\n"
    
    # Core Metrics
    report += f"<b>📈 CORE PERFORMANCE</b>\n"
    report += f"• Win Rate: {metrics.get('win_rate_overall', 0):.1%}\n"
    report += f"• R-Expectancy: {metrics.get('r_expectancy', 0):.2f}R\n"
    report += f"• Avg RR Ratio: {metrics.get('average_rr_ratio', 0):.1f}:1\n"
    report += f"• Total Trades: {metrics.get('validated_predictions', 0)}\n\n"
    
    # Directional Performance
    report += f"<b>📊 DIRECTIONAL ANALYSIS</b>\n"
    long_rate = metrics.get('win_rate_long', 0)
    short_rate = metrics.get('win_rate_short', 0)
    
    if long_rate > 0 or short_rate > 0:
        report += f"• Long Trades: {long_rate:.1%}\n"
        report += f"• Short Trades: {short_rate:.1%}\n"
        
        # Bias analysis
        if long_rate > short_rate + 0.1:
            bias = "🟢 Long Bias"
        elif short_rate > long_rate + 0.1:
            bias = "🔴 Short Bias"
        else:
            bias = "⚪ Balanced"
        report += f"• Direction Bias: {bias}\n\n"
    else:
        report += f"• Not enough directional data yet\n\n"
    
    # Best Setups & Timing
    report += f"<b>⭐ BEST PERFORMING</b>\n"
    report += f"• Best Time: {metrics.get('best_timeframe', 'Analyzing...')}\n"
    report += f"• Best Setup: {metrics.get('best_setup_type', 'Analyzing...')}\n\n"
    
    # Market Conditions Performance
    vol_perf = metrics.get('volatility_performance', {})
    if vol_perf:
        report += f"<b>🌊 VOLATILITY PERFORMANCE</b>\n"
        for vol_level, stats in vol_perf.items():
            if stats['trade_count'] >= 2:
                report += f"• {vol_level.title()}: {stats['win_rate']:.1%} ({stats['trade_count']} trades)\n"
        report += "\n"
    
    # Sentiment Performance
    sent_perf = metrics.get('sentiment_performance', {})
    if sent_perf:
        report += f"<b>😨😐😍 SENTIMENT PERFORMANCE</b>\n"
        for sentiment, stats in sent_perf.items():
            if stats['trade_count'] >= 2:
                emoji = "😨" if sentiment == "fear" else "😍" if sentiment == "greed" else "😐"
                report += f"• {emoji} {sentiment.title()}: {stats['win_rate']:.1%} (RR: {stats['avg_rr']:.1f})\n"
        report += "\n"
    
    # Worst Mistakes
    mistakes = metrics.get('worst_mistakes', [])
    if mistakes:
        report += f"<b>⚠️ TOP MISTAKES TO AVOID</b>\n"
        for i, mistake in enumerate(mistakes[:3], 1):
            report += f"{i}. {mistake['description']}\n"
        report += "\n"
    
    # Pattern Recognition
    patterns = metrics.get('prediction_patterns', {})
    if patterns:
        avg_conf_winners = patterns.get('avg_confidence_winners', 0)
        avg_conf_losers = patterns.get('avg_confidence_losers', 0)
        
        if avg_conf_winners > 0 and avg_conf_losers > 0:
            confidence_edge = avg_conf_winners - avg_conf_losers
            report += f"<b>🧠 PATTERN INSIGHTS</b>\n"
            report += f"• Winner Confidence: {avg_conf_winners:.0f}%\n"
            report += f"• Loser Confidence: {avg_conf_losers:.0f}%\n"
            
            if confidence_edge > 10:
                report += f"• ✅ Good confidence calibration (+{confidence_edge:.0f})\n"
            elif confidence_edge < -5:
                report += f"• ❌ Overconfident on losers ({confidence_edge:.0f})\n"
            else:
                report += f"• ⚪ Neutral confidence pattern\n"
            report += "\n"
    
    # Key Insights
    report += f"<b>💡 KEY INSIGHTS</b>\n"
    
    # R-Expectancy insight
    r_exp = metrics.get('r_expectancy', 0)
    if r_exp > 0.5:
        report += f"• 🟢 Positive expectancy - profitable system\n"
    elif r_exp > 0:
        report += f"• 🟡 Marginally profitable - room for improvement\n"
    else:
        report += f"• 🔴 Negative expectancy - system needs adjustment\n"
    
    # Win rate vs RR insight
    win_rate = metrics.get('win_rate_overall', 0)
    avg_rr = metrics.get('average_rr_ratio', 0)
    if win_rate > 0 and avg_rr > 0:
        breakeven_wr = 1 / (1 + avg_rr)
        if win_rate > breakeven_wr:
            edge = (win_rate - breakeven_wr) * 100
            report += f"• 📈 {edge:.1f}% edge over breakeven\n"
        else:
            deficit = (breakeven_wr - win_rate) * 100
            report += f"• 📉 {deficit:.1f}% below breakeven needs\n"
    
    report += f"\n<i>🚀 System learning and evolving continuously!</i>"
    
    return report

def validate_target_hit(current_price, target_price, target_type, scenario="NEUTRAL"):
    """Check if a target was hit based on scenario and target type"""
    if not current_price or not target_price:
        return False
    
    # For professional analysis targets
    if target_type.startswith("TARGET"):
        if scenario.upper() in ["BUY", "STRONG BUY", "BULLISH"]:
            # Bullish scenario: targets should be above current price
            return current_price >= target_price
        elif scenario.upper() in ["SELL", "STRONG SELL", "BEARISH"]:
            # Bearish scenario: targets should be below current price
            return current_price <= target_price
        else:
            # Neutral: check both directions
            return abs(current_price - target_price) / target_price < 0.02  # Within 2%
    
    elif target_type == "STOP_LOSS":
        if scenario.upper() in ["BUY", "STRONG BUY", "BULLISH"]:
            # Bullish scenario: stop loss below entry
            return current_price <= target_price
        elif scenario.upper() in ["SELL", "STRONG SELL", "BEARISH"]:
            # Bearish scenario: stop loss above entry
            return current_price >= target_price
        else:
            # Check if stop loss was hit (either direction)
            return abs(current_price - target_price) / target_price < 0.01  # Within 1%
    
    return False

def extract_professional_targets(prediction_data):
    """Extract professional analysis targets from the enhanced prediction format"""
    targets = {"BTC": {}, "ETH": {}}
    
    try:
        # Check if it's a professional analysis prediction
        if isinstance(prediction_data, dict):
            # Try to find professional analysis targets
            pro_analysis = prediction_data.get("professional_analysis", {})
            if pro_analysis and "price_targets" in pro_analysis:
                price_targets = pro_analysis["price_targets"]
                targets["BTC"] = {
                    "current": price_targets.get("current"),
                    "target_1": price_targets.get("target_1"),
                    "target_2": price_targets.get("target_2"),
                    "stop_loss": price_targets.get("stop_loss"),
                    "scenario": pro_analysis.get("primary_scenario", "NEUTRAL")
                }
            
            # Also check AI prediction format (fallback)
            if "btc_prediction" in prediction_data:
                btc_pred = prediction_data["btc_prediction"]
                targets["BTC"].update({
                    "entry_range": extract_price_range(btc_pred.get("entry_price_range", "")),
                    "take_profits": extract_take_profits(btc_pred.get("take_profit_targets", "")),
                    "stop_loss": extract_price(btc_pred.get("stop_loss", "")),
                    "direction": btc_pred.get("direction", "")
                })
            
            if "eth_prediction" in prediction_data:
                eth_pred = prediction_data["eth_prediction"]
                targets["ETH"].update({
                    "entry_range": extract_price_range(eth_pred.get("entry_price_range", "")),
                    "take_profits": extract_take_profits(eth_pred.get("take_profit_targets", "")),
                    "stop_loss": extract_price(eth_pred.get("stop_loss", "")),
                    "direction": eth_pred.get("direction", "")
                })
                
    except Exception as e:
        print(f"[ERROR] Extracting professional targets: {e}")
    
    return targets

def extract_price_range(price_str):
    """Extract price range from string"""
    if not price_str:
        return None
    try:
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

def generate_deep_learning_insights(predictions, timeframe="weekly"):
    """Generate comprehensive learning insights for AI improvement - Professional Trader Style"""
    
    # Filter predictions based on timeframe
    if timeframe == "weekly":
        cutoff = datetime.now() - timedelta(days=7)
        period_name = "Weekly"
    elif timeframe == "monthly":
        cutoff = datetime.now() - timedelta(days=30)
        period_name = "Monthly"
    else:
        cutoff = datetime.now() - timedelta(days=7)
        period_name = "Weekly"
    
    recent_predictions = [p for p in predictions 
                         if datetime.strptime(p["timestamp"], "%Y-%m-%d %H:%M:%S") > cutoff]
    
    if not recent_predictions:
        return {"error": "No recent predictions for analysis"}
    
    # Extract all trades for analysis
    all_trades = []
    for pred in recent_predictions:
        trade_data = extract_trade_metrics(pred)
        if trade_data:
            all_trades.append(trade_data)
    
    if not all_trades:
        return {"error": "No completed trades for analysis"}
    
    insights = {
        "period": period_name,
        "analysis_date": datetime.now().isoformat(),
        "total_trades": len(all_trades),
        "core_performance": {},
        "setup_analysis": {},
        "timing_analysis": {},
        "market_condition_analysis": {},
        "psychological_patterns": {},
        "improvement_recommendations": [],
        "strength_areas": [],
        "edge_identification": {},
        "risk_management_review": {},
        "confluence_scoring": {}
    }
    
    # Core Performance Analysis
    winning_trades = [t for t in all_trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
    losing_trades = [t for t in all_trades if t["outcome"] == "SL_HIT"]
    
    insights["core_performance"] = {
        "win_rate": len(winning_trades) / len(all_trades),
        "total_r_gained": sum(t["r_multiple"] for t in all_trades),
        "r_expectancy": sum(t["r_multiple"] for t in all_trades) / len(all_trades),
        "average_winner": sum(t["r_multiple"] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
        "average_loser": sum(t["r_multiple"] for t in losing_trades) / len(losing_trades) if losing_trades else 0,
        "largest_winner": max([t["r_multiple"] for t in winning_trades], default=0),
        "largest_loser": min([t["r_multiple"] for t in losing_trades], default=0),
        "profit_factor": abs(sum(t["r_multiple"] for t in winning_trades) / sum(t["r_multiple"] for t in losing_trades)) if losing_trades else float('inf')
    }
    
    # Setup Type Analysis - What combinations work best?
    setup_performance = {}
    for trade in all_trades:
        pred = next((p for p in recent_predictions if p["timestamp"] == trade["timestamp"]), None)
        if pred:
            setup_type = identify_setup_type(pred)
            if setup_type not in setup_performance:
                setup_performance[setup_type] = {"trades": [], "wins": 0, "total_r": 0}
            
            setup_performance[setup_type]["trades"].append(trade)
            setup_performance[setup_type]["total_r"] += trade["r_multiple"]
            if trade["outcome"] in ["TP_HIT", "PARTIAL_WIN"]:
                setup_performance[setup_type]["wins"] += 1
    
    # Rank setups by performance
    for setup, stats in setup_performance.items():
        trade_count = len(stats["trades"])
        if trade_count >= 2:  # Minimum sample size
            stats["win_rate"] = stats["wins"] / trade_count
            stats["avg_r"] = stats["total_r"] / trade_count
            stats["expectancy_score"] = stats["win_rate"] * stats["avg_r"]
    
    insights["setup_analysis"] = {
        setup: {
            "win_rate": stats["win_rate"],
            "avg_r_per_trade": stats["avg_r"],
            "total_trades": len(stats["trades"]),
            "expectancy_score": stats["expectancy_score"]
        }
        for setup, stats in setup_performance.items()
        if len(stats["trades"]) >= 2
    }
    
    # Timing Analysis - When do we perform best?
    hour_performance = {}
    for trade in all_trades:
        hour = datetime.strptime(trade["timestamp"], "%Y-%m-%d %H:%M:%S").hour
        if hour not in hour_performance:
            hour_performance[hour] = {"trades": [], "wins": 0, "total_r": 0}
        
        hour_performance[hour]["trades"].append(trade)
        hour_performance[hour]["total_r"] += trade["r_multiple"]
        if trade["outcome"] in ["TP_HIT", "PARTIAL_WIN"]:
            hour_performance[hour]["wins"] += 1
    
    # Calculate timing performance
    for hour, stats in hour_performance.items():
        trade_count = len(stats["trades"])
        if trade_count >= 2:
            stats["win_rate"] = stats["wins"] / trade_count
            stats["avg_r"] = stats["total_r"] / trade_count
    
    insights["timing_analysis"] = {
        f"{hour:02d}:00": {
            "win_rate": stats["win_rate"],
            "avg_r_per_trade": stats["avg_r"],
            "total_trades": len(stats["trades"])
        }
        for hour, stats in hour_performance.items()
        if len(stats["trades"]) >= 2
    }
    
    # Market Condition Analysis
    volatility_performance = {"low": [], "medium": [], "high": []}
    sentiment_performance = {"fear": [], "neutral": [], "greed": []}
    
    for trade in all_trades:
        volatility_performance[trade["volatility"]].append(trade)
        
        if trade["fear_greed"] < 40:
            sentiment_performance["fear"].append(trade)
        elif trade["fear_greed"] > 60:
            sentiment_performance["greed"].append(trade)
        else:
            sentiment_performance["neutral"].append(trade)
    
    # Analyze market conditions
    insights["market_condition_analysis"] = {
        "volatility": {},
        "sentiment": {}
    }
    
    for vol_level, trades in volatility_performance.items():
        if trades:
            wins = [t for t in trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
            insights["market_condition_analysis"]["volatility"][vol_level] = {
                "win_rate": len(wins) / len(trades),
                "avg_r": sum(t["r_multiple"] for t in trades) / len(trades),
                "trade_count": len(trades)
            }
    
    for sentiment, trades in sentiment_performance.items():
        if trades:
            wins = [t for t in trades if t["outcome"] in ["TP_HIT", "PARTIAL_WIN"]]
            insights["market_condition_analysis"]["sentiment"][sentiment] = {
                "win_rate": len(wins) / len(trades),
                "avg_r": sum(t["r_multiple"] for t in trades) / len(trades),
                "trade_count": len(trades)
            }
    
    # Psychological Pattern Analysis
    confidence_vs_outcome = {"high_conf_winners": [], "high_conf_losers": [], "low_conf_winners": [], "low_conf_losers": []}
    
    for trade in all_trades:
        if trade["confidence"] > 70:
            if trade["outcome"] in ["TP_HIT", "PARTIAL_WIN"]:
                confidence_vs_outcome["high_conf_winners"].append(trade)
            else:
                confidence_vs_outcome["high_conf_losers"].append(trade)
        else:
            if trade["outcome"] in ["TP_HIT", "PARTIAL_WIN"]:
                confidence_vs_outcome["low_conf_winners"].append(trade)
            else:
                confidence_vs_outcome["low_conf_losers"].append(trade)
    
    insights["psychological_patterns"] = {
        "overconfidence_bias": len(confidence_vs_outcome["high_conf_losers"]) / max(1, len(confidence_vs_outcome["high_conf_winners"]) + len(confidence_vs_outcome["high_conf_losers"])),
        "underconfidence_bias": len(confidence_vs_outcome["low_conf_winners"]) / max(1, len(confidence_vs_outcome["low_conf_winners"]) + len(confidence_vs_outcome["low_conf_losers"])),
        "confidence_calibration": (len(confidence_vs_outcome["high_conf_winners"]) - len(confidence_vs_outcome["high_conf_losers"])) / max(1, len(all_trades))
    }
    
    # Generate Improvement Recommendations
    recommendations = []
    
    # Win rate analysis
    win_rate = insights["core_performance"]["win_rate"]
    if win_rate < 0.4:
        recommendations.append({
            "priority": "HIGH",
            "area": "Entry Quality",
            "issue": f"Win rate only {win_rate:.1%} - need better entry timing",
            "suggestion": "Focus on higher confluence setups and wait for better entries"
        })
    elif win_rate > 0.7:
        recommendations.append({
            "priority": "MEDIUM",
            "area": "Risk Management", 
            "issue": f"Win rate {win_rate:.1%} is very high - might be taking too little risk",
            "suggestion": "Consider increasing position sizes or expanding target distances"
        })
    
    # R-expectancy analysis
    r_exp = insights["core_performance"]["r_expectancy"]
    if r_exp < 0:
        recommendations.append({
            "priority": "CRITICAL",
            "area": "System Overhaul",
            "issue": f"Negative expectancy {r_exp:.2f}R - losing money",
            "suggestion": "Stop trading and analyze what's not working. Focus on best setups only."
        })
    elif r_exp < 0.2:
        recommendations.append({
            "priority": "HIGH", 
            "area": "Risk-Reward",
            "issue": f"Low expectancy {r_exp:.2f}R - barely profitable",
            "suggestion": "Improve RR ratios and/or win rate. Consider tighter stop losses or wider targets."
        })
    
    # Setup performance analysis
    if insights["setup_analysis"]:
        best_setup = max(insights["setup_analysis"].items(), key=lambda x: x[1]["expectancy_score"])
        worst_setup = min(insights["setup_analysis"].items(), key=lambda x: x[1]["expectancy_score"])
        
        if best_setup[1]["expectancy_score"] > 0.3:
            recommendations.append({
                "priority": "MEDIUM",
                "area": "Setup Focus",
                "issue": f"Best setup '{best_setup[0]}' has {best_setup[1]['expectancy_score']:.2f} expectancy",
                "suggestion": f"Focus more on {best_setup[0]} setups - they're working well"
            })
        
        if worst_setup[1]["expectancy_score"] < 0:
            recommendations.append({
                "priority": "HIGH",
                "area": "Setup Filtering", 
                "issue": f"Worst setup '{worst_setup[0]}' losing money",
                "suggestion": f"Avoid {worst_setup[0]} setups until pattern improves"
            })
    
    # Market condition recommendations
    vol_analysis = insights["market_condition_analysis"]["volatility"]
    if vol_analysis:
        best_vol = max(vol_analysis.items(), key=lambda x: x[1]["win_rate"])
        if best_vol[1]["win_rate"] > 0.6:
            recommendations.append({
                "priority": "MEDIUM",
                "area": "Market Selection",
                "issue": f"Perform best in {best_vol[0]} volatility ({best_vol[1]['win_rate']:.1%} win rate)",
                "suggestion": f"Increase position sizes during {best_vol[0]} volatility periods"
            })
    
    insights["improvement_recommendations"] = sorted(recommendations, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[x["priority"]])
    
    # Identify Strength Areas
    strengths = []
    
    if win_rate > 0.6:
        strengths.append(f"High win rate ({win_rate:.1%}) - good at picking direction")
    
    if r_exp > 0.3:
        strengths.append(f"Strong expectancy ({r_exp:.2f}R) - profitable system")
    
    profit_factor = insights["core_performance"]["profit_factor"]
    if profit_factor > 2:
        strengths.append(f"Excellent profit factor ({profit_factor:.1f}) - winners much larger than losers")
    
    # Timing strengths
    if insights["timing_analysis"]:
        best_time = max(insights["timing_analysis"].items(), key=lambda x: x[1]["win_rate"])
        if best_time[1]["win_rate"] > 0.7:
            strengths.append(f"Strong performance at {best_time[0]} ({best_time[1]['win_rate']:.1%} win rate)")
    
    insights["strength_areas"] = strengths
    
    return insights

def save_deep_learning_insights(insights):
    """Save deep learning insights for AI evolution"""
    insights_file = "deep_learning_insights.json"
    
    all_insights = []
    if os.path.exists(insights_file):
        try:
            with open(insights_file, "r") as f:
                all_insights = json.load(f)
        except Exception:
            all_insights = []
    
    all_insights.append(insights)
    
    # Keep only last 3 months of insights
    cutoff = datetime.now() - timedelta(days=90)
    all_insights = [insight for insight in all_insights 
                   if datetime.fromisoformat(insight["analysis_date"]) > cutoff]
    
    with open(insights_file, "w") as f:
        json.dump(all_insights, f, indent=4)
    
    print(f"[INFO] Deep learning insights saved - {len(all_insights)} total analyses stored")

def format_deep_insights_summary(insights):
    """Format deep insights for Telegram - Professional Review Style"""
    if "error" in insights:
        return f"📊 Deep Analysis: {insights['error']}"
    
    report = f"🧠 <b>{insights['period'].upper()} DEEP LEARNING ANALYSIS</b>\n"
    report += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
    report += f"{'═' * 40}\n\n"
    
    core = insights["core_performance"]
    
    # Executive Summary
    report += f"<b>📈 EXECUTIVE SUMMARY</b>\n"
    report += f"• Total Trades: {insights['total_trades']}\n"
    report += f"• Win Rate: {core['win_rate']:.1%}\n"
    report += f"• R-Expectancy: {core['r_expectancy']:.2f}R\n"
    report += f"• Profit Factor: {core['profit_factor']:.1f}\n"
    report += f"• Total R Gained: {core['total_r_gained']:+.1f}R\n\n"
    
    # Top Performing Setups
    if insights["setup_analysis"]:
        report += f"<b>⭐ BEST PERFORMING SETUPS</b>\n"
        sorted_setups = sorted(insights["setup_analysis"].items(), 
                              key=lambda x: x[1]["expectancy_score"], reverse=True)
        
        for i, (setup, stats) in enumerate(sorted_setups[:3], 1):
            setup_name = setup.replace('_', ' ').title()
            report += f"{i}. {setup_name}\n"
            report += f"   • Win Rate: {stats['win_rate']:.1%}\n"
            report += f"   • Avg R: {stats['avg_r_per_trade']:+.2f}R\n"
            report += f"   • Trades: {stats['total_trades']}\n\n"
    
    # Best Timing
    if insights["timing_analysis"]:
        report += f"<b>⏰ OPTIMAL TIMING</b>\n"
        sorted_times = sorted(insights["timing_analysis"].items(),
                             key=lambda x: x[1]["win_rate"], reverse=True)
        
        for i, (time, stats) in enumerate(sorted_times[:3], 1):
            report += f"{i}. {time} - {stats['win_rate']:.1%} ({stats['total_trades']} trades)\n"
        report += "\n"
    
    # Market Conditions
    vol_perf = insights["market_condition_analysis"]["volatility"]
    if vol_perf:
        report += f"<b>🌊 VOLATILITY EDGE</b>\n"
        for vol_level, stats in vol_perf.items():
            if stats['trade_count'] >= 2:
                report += f"• {vol_level.title()}: {stats['win_rate']:.1%} ({stats['avg_r']:+.2f}R avg)\n"
        report += "\n"
    
    # Critical Improvements
    if insights["improvement_recommendations"]:
        report += f"<b>🚨 CRITICAL IMPROVEMENTS</b>\n"
        critical_recs = [r for r in insights["improvement_recommendations"] 
                        if r["priority"] in ["CRITICAL", "HIGH"]]
        
        for i, rec in enumerate(critical_recs[:3], 1):
            report += f"{i}. {rec['area']}: {rec['suggestion']}\n"
        report += "\n"
    
    # Key Strengths
    if insights["strength_areas"]:
        report += f"<b>💪 KEY STRENGTHS</b>\n"
        for i, strength in enumerate(insights["strength_areas"][:3], 1):
            report += f"{i}. {strength}\n"
        report += "\n"
    
    # Psychological Insights
    psych = insights["psychological_patterns"]
    if psych:
        report += f"<b>🧠 PSYCHOLOGICAL INSIGHTS</b>\n"
        if psych["overconfidence_bias"] > 0.3:
            report += f"• ⚠️ Overconfidence detected ({psych['overconfidence_bias']:.1%})\n"
        
        if psych["confidence_calibration"] > 0.1:
            report += f"• ✅ Good confidence calibration\n"
        elif psych["confidence_calibration"] < -0.1:
            report += f"• ❌ Poor confidence calibration\n"
        report += "\n"
    
    report += f"<i>🚀 Evolution in progress - becoming more profitable!</i>"
    
    return report

if __name__ == "__main__":
    # Check for test mode argument
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        config = load_config()
        config["test_mode"]["enabled"] = True
        print("[TEST] Test mode enabled for validation")
        validate_predictions()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test-deep-analysis":
        # Test deep learning analysis functionality
        config = load_config()
        config["test_mode"]["enabled"] = True
        print("[TEST] Testing deep learning analysis...")
        
        # Load predictions for analysis
        prediction_file = "detailed_predictions.json"
        if config["test_mode"]["enabled"]:
            prediction_file = config["test_mode"]["output_prefix"] + prediction_file
        
        if os.path.exists(prediction_file):
            with open(prediction_file, "r") as f:
                predictions = json.load(f)
            
            if predictions:
                print(f"[TEST] Analyzing {len(predictions)} predictions...")
                
                # Generate weekly insights
                weekly_insights = generate_deep_learning_insights(predictions, "weekly")
                if "error" not in weekly_insights:
                    print("[TEST] Weekly analysis successful!")
                    save_deep_learning_insights(weekly_insights)
                    
                    # Format and display summary
                    summary = format_deep_insights_summary(weekly_insights)
                    print("\n" + "="*50)
                    print("WEEKLY DEEP LEARNING ANALYSIS PREVIEW:")
                    print("="*50)
                    # Remove HTML tags for console display
                    import re
                    clean_summary = re.sub(r'<[^>]+>', '', summary)
                    print(clean_summary)
                    print("="*50)
                    
                    # Test ML learning integration
                    try:
                        ml_enhancer = PredictionEnhancer()
                        ml_enhancer.learn_from_insights(weekly_insights)
                        print("[TEST] ML learning integration successful!")
                    except Exception as e:
                        print(f"[TEST] ML learning integration failed: {e}")
                else:
                    print(f"[TEST] Analysis failed: {weekly_insights['error']}")
            else:
                print("[TEST] No predictions found for analysis")
        else:
            print(f"[TEST] No prediction file found: {prediction_file}")
    else:
        validate_predictions()
