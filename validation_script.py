#!/usr/bin/env python3

import requests
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import os
import re
import sys
from ml_enhancer import PredictionEnhancer
from risk_manager import RiskManager
from professional_analysis import ProfessionalTraderAnalysis
from dotenv import load_dotenv

# Import database manager
try:
    from database_manager import DatabaseManager
    db_manager = DatabaseManager()
    DATABASE_AVAILABLE = True
    print("[INFO] Database manager loaded successfully")
except ImportError:
    print("[WARN] Database manager not available, using JSON files only")
    DATABASE_AVAILABLE = False

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
    # Load telegram config directly instead of general config
    telegram_config = load_telegram_config()
    
    if not telegram_config["enabled"]:
        print("[WARN] Telegram not configured - skipping message")
        return False
    
    bot_token = telegram_config["bot_token"]
    chat_id = telegram_config["chat_id"]
    
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
        response = requests.post(url, data=payload, timeout=10)
        
        # Handle parsing errors by falling back to plain text
        if response.status_code == 400 and "can't parse entities" in response.text.lower():
            print("[WARN] HTML parsing failed, sending as plain text")
            payload["parse_mode"] = None
            # Remove HTML tags for plain text
            plain_message = re.sub(r'<[^>]+>', '', message)
            payload["text"] = plain_message
            response = requests.post(url, data=payload, timeout=10)
        
        response.raise_for_status()
        print("[INFO] Telegram validation message sent successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        return False

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
    # Load environment variables - try .env file first (local), then system env vars (Render)
    if os.path.exists('.env'):
        try:
            load_dotenv()
            print("[INFO] Loaded .env file for local development")
        except Exception as e:
            print(f"[WARN] .env file exists but failed to load: {e}")
    else:
        print("[INFO] No .env file found - using system environment variables (cloud deployment mode)")
    
    # Verify telegram credentials
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    
    if telegram_token and telegram_chat:
        print("[INFO] ✓ Telegram credentials available")
    else:
        print("[WARN] ✗ Telegram credentials not configured")
    
    default_config = {
        "telegram": {
            "enabled": True,
            "bot_token": telegram_token,
            "chat_id": telegram_chat,
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

def analyze_last_prediction_cycle(predictions, current_hour):
    """Analyze the last prediction cycle for accuracy and performance"""
    try:
        if not predictions:
            return {
                "status": "no_predictions",
                "message": "No predictions available for analysis"
            }
        
        # Get the most recent prediction
        latest_prediction = predictions[-1]
        
        # Extract key metrics
        analysis = {
            "timestamp": latest_prediction.get("timestamp"),
            "predictions": {},
            "accuracy": {},
            "performance": {}
        }
        
        # Analyze each coin's prediction
        for coin in ["BTC", "ETH"]:
            coin_pred = latest_prediction.get("predictions", {}).get(coin, {})
            if not coin_pred:
                continue
                
            # Get prediction details
            direction = coin_pred.get("direction", "NEUTRAL")
            confidence = coin_pred.get("confidence_level", "medium")
            targets = coin_pred.get("targets", [])
            
            # Get validation points
            validation_points = latest_prediction.get("validation_points", [])
            coin_validations = [vp for vp in validation_points if vp.get("coin") == coin]
            
            # Calculate accuracy metrics
            hits = sum(1 for vp in coin_validations if vp.get("hit", False))
            total_targets = len(targets)
            accuracy = (hits / total_targets * 100) if total_targets > 0 else 0
            
            analysis["predictions"][coin] = {
                "direction": direction,
                "confidence": confidence,
                "targets": len(targets)
            }
            
            analysis["accuracy"][coin] = {
                "hits": hits,
                "total_targets": total_targets,
                "accuracy_percentage": accuracy
            }
        
        return analysis
        
    except Exception as e:
        print(f"[ERROR] Failed to analyze last prediction cycle: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

def format_accuracy_summary(accuracy_metrics, last_prediction_analysis):
    """Format accuracy metrics into a readable report"""
    try:
        report = "📊 <b>Prediction Validation Report</b>\n\n"
        
        # Overall metrics
        report += f"<b>Overall Performance:</b>\n"
        report += f"• Total Predictions: {accuracy_metrics['total_predictions']}\n"
        report += f"• Overall Accuracy: {accuracy_metrics['overall_accuracy']:.1f}%\n"
        report += f"• Average Confidence: {accuracy_metrics['avg_confidence']:.1f}\n\n"
        
        # Last prediction analysis
        if last_prediction_analysis and last_prediction_analysis.get("status") != "error":
            report += f"<b>Latest Prediction Analysis:</b>\n"
            
            for coin in ["BTC", "ETH"]:
                if coin in last_prediction_analysis["predictions"]:
                    pred = last_prediction_analysis["predictions"][coin]
                    acc = last_prediction_analysis["accuracy"][coin]
                    
                    report += f"\n<b>{coin}:</b>\n"
                    report += f"• Direction: {pred['direction']}\n"
                    report += f"• Confidence: {pred['confidence']}\n"
                    report += f"• Targets: {pred['targets']}\n"
                    report += f"• Accuracy: {acc['accuracy_percentage']:.1f}% ({acc['hits']}/{acc['total_targets']})\n"
        
        return report
        
    except Exception as e:
        print(f"[ERROR] Failed to format accuracy summary: {e}")
        return "Error generating accuracy report"

def validate_predictions():
    """Validate the last prediction and generate accuracy report"""
    try:
        # Load predictions
        if DATABASE_AVAILABLE:
            predictions = db_manager.load_predictions()
        else:
            try:
                with open("detailed_predictions.json", "r") as f:
                    predictions = json.load(f)
            except Exception as e:
                print(f"[ERROR] Failed to load predictions: {e}")
                return

        if not predictions:
            print("[WARN] No predictions found to validate")
            return

        # Get current prices
        try:
            current_prices = get_crypto_prices()
        except Exception as e:
            print(f"[ERROR] Failed to get current prices: {e}")
            return

        # Get current hour in Vietnam time
        current_hour = (datetime.now().hour + 7) % 24  # Convert UTC to Vietnam time
        
        # Analyze the last prediction cycle
        last_prediction_analysis = analyze_last_prediction_cycle(predictions, current_hour)
        
        # Calculate overall accuracy metrics
        accuracy_metrics = calculate_enhanced_accuracy(predictions)
        
        # Format and send the accuracy report
        report = format_accuracy_summary(accuracy_metrics, last_prediction_analysis)
        send_telegram_message(report)
        
        # Save predictions for learning
        if DATABASE_AVAILABLE:
            for prediction in predictions:
                if not prediction.get("ml_processed"):
                    db_manager.save_prediction(prediction)
                    prediction["ml_processed"] = True
        else:
            with open("detailed_predictions.json", "w") as f:
                json.dump(predictions, f, indent=4, default=str)

    except Exception as e:
        print(f"[ERROR] Validation failed: {e}")
        return

def validate_professional_targets(prediction, coin, targets, current_price, is_latest, notifications):
    """Validate professional trading targets"""
    try:
        for target in targets:
            target_price = target.get("price")
            target_type = target.get("type")
            
            if not target_price or not target_type:
                continue

            # Validate target hit
            hit, hit_type = validate_target_hit(current_price, target_price, target_type)
            
            if hit:
                # Create validation point
                validation_point = {
                    "coin": coin,
                    "type": target_type,
                    "predicted_level": target_price,
                    "current_price": current_price,
                    "hit": True,
                    "hit_type": hit_type,
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Add to validation points if not duplicate
                if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
                    prediction.setdefault("validation_points", []).append(validation_point)
                    
                    # Add notification
                    notifications.append({
                        "type": "target_hit",
                        "coin": coin,
                        "target_type": target_type,
                        "predicted_price": target_price,
                        "current_price": current_price,
                        "hit_type": hit_type
                    })

    except Exception as e:
        print(f"[ERROR] Failed to validate professional targets: {e}")

def validate_legacy_targets(prediction, coin, targets, current_price, is_latest, notifications):
    """Validate legacy trading targets"""
    try:
        for target in targets:
            target_price = target.get("price")
            target_type = target.get("type")
            
            if not target_price or not target_type:
                continue

            # Validate target hit
            hit, hit_type = validate_target_hit(current_price, target_price, target_type)
            
            if hit:
                # Create validation point
                validation_point = {
                    "coin": coin,
                    "type": target_type,
                    "predicted_level": target_price,
                    "current_price": current_price,
                    "hit": True,
                    "hit_type": hit_type,
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Add to validation points if not duplicate
                if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
                    prediction.setdefault("validation_points", []).append(validation_point)
                    
                    # Add notification
                    notifications.append({
                        "type": "target_hit",
                        "coin": coin,
                        "target_type": target_type,
                        "predicted_price": target_price,
                        "current_price": current_price,
                        "hit_type": hit_type
                    })

    except Exception as e:
        print(f"[ERROR] Failed to validate legacy targets: {e}")

def calculate_enhanced_accuracy(predictions):
    """Calculate overall accuracy metrics for predictions"""
    try:
        if not predictions:
            return {
                "total_predictions": 0,
                "overall_accuracy": 0,
                "avg_confidence": 0
            }
        
        total_predictions = 0
        correct_predictions = 0
        total_confidence = 0
        
        for prediction in predictions:
            for coin in ["BTC", "ETH"]:
                coin_pred = prediction.get("predictions", {}).get(coin, {})
                if not coin_pred:
                    continue
                
                # Skip if not validated
                if not prediction.get("hourly_validated"):
                    continue
                
                total_predictions += 1
                
                # Get confidence level
                confidence = coin_pred.get("confidence_level", "medium")
                confidence_value = {
                    "high": 80,
                    "medium": 60,
                    "low": 40
                }.get(confidence, 50)
                
                total_confidence += confidence_value
                
                # Check if prediction was correct
                validation_points = prediction.get("validation_points", [])
                for vp in validation_points:
                    if vp.get("coin") == coin and vp.get("type") in ["PROFESSIONAL_TARGET_1", "PROFESSIONAL_TARGET_2"]:
                        correct_predictions += 1
                        break
        
        # Calculate metrics
        overall_accuracy = (correct_predictions / total_predictions * 100) if total_predictions > 0 else 0
        avg_confidence = (total_confidence / total_predictions) if total_predictions > 0 else 0
        
        return {
            "total_predictions": total_predictions,
            "overall_accuracy": overall_accuracy,
            "avg_confidence": avg_confidence
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to calculate accuracy metrics: {e}")
        return {
            "total_predictions": 0,
            "overall_accuracy": 0,
            "avg_confidence": 0
        }

def validate_target_hit(current_price, target_price, target_type, scenario="NEUTRAL"):
    """Validate if a target price has been hit"""
    try:
        if not current_price or not target_price:
            return False, None
        
        # Convert prices to float if they're strings
        current_price = float(current_price)
        target_price = float(target_price)
        
        # Calculate price difference percentage
        price_diff_pct = abs((current_price - target_price) / target_price * 100)
        
        # Define hit thresholds based on target type
        if target_type.startswith("TAKE_PROFIT"):
            # Take profit targets are hit when price moves beyond them
            if scenario == "BULLISH":
                hit = current_price >= target_price
                hit_type = "BULLISH_TP" if hit else None
            elif scenario == "BEARISH":
                hit = current_price <= target_price
                hit_type = "BEARISH_TP" if hit else None
            else:  # NEUTRAL
                hit = price_diff_pct <= 0.5  # Within 0.5% of target
                hit_type = "NEUTRAL_TP" if hit else None
        
        elif target_type == "STOP_LOSS":
            # Stop loss targets are hit when price moves beyond them
            if scenario == "BULLISH":
                hit = current_price <= target_price
                hit_type = "BULLISH_SL" if hit else None
            elif scenario == "BEARISH":
                hit = current_price >= target_price
                hit_type = "BEARISH_SL" if hit else None
            else:  # NEUTRAL
                hit = price_diff_pct <= 0.5  # Within 0.5% of target
                hit_type = "NEUTRAL_SL" if hit else None
        
        elif target_type == "ENTRY":
            # Entry targets are hit when price is close to them
            hit = price_diff_pct <= 0.5  # Within 0.5% of target
            hit_type = "ENTRY" if hit else None
        
        else:
            # Default case - consider it hit if within 0.5%
            hit = price_diff_pct <= 0.5
            hit_type = "GENERAL" if hit else None
        
        return hit, hit_type
        
    except Exception as e:
        print(f"[ERROR] Failed to validate target hit: {e}")
        return False, None

def extract_professional_targets(prediction_data):
    """Extract professional trading targets from prediction data"""
    try:
        targets = []
        
        # Handle professional analysis format
        if isinstance(prediction_data, dict):
            pro_analysis = prediction_data.get("professional_analysis", {})
            price_targets = pro_analysis.get("price_targets", {})
            scenario = pro_analysis.get("primary_scenario", "NEUTRAL")
            
            # Extract entry level
            if "entry" in price_targets:
                targets.append({
                    "type": "ENTRY",
                    "price": price_targets["entry"],
                    "scenario": scenario
                })
            
            # Extract take profit levels
            if "take_profits" in price_targets:
                for i, tp in enumerate(price_targets["take_profits"], 1):
                    targets.append({
                        "type": f"TAKE_PROFIT_{i}",
                        "price": tp,
                        "scenario": scenario
                    })
            
            # Extract stop loss
            if "stop_loss" in price_targets:
                targets.append({
                    "type": "STOP_LOSS",
                    "price": price_targets["stop_loss"],
                    "scenario": scenario
                })
        
        return targets
        
    except Exception as e:
        print(f"[ERROR] Failed to extract professional targets: {e}")
        return []

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

def generate_deep_learning_insights(predictions, period_type="weekly"):
    """Generate comprehensive weekly/monthly trading insights for accelerated learning"""
    insights = {
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period_type": period_type,  # Use the passed parameter
        
        # Core Performance Review
        "performance_summary": {},
        
        # Detailed Learning Insights
        "best_setup_findings": {},
        "best_time_findings": {},
        "worst_mistake_patterns": {},
        "market_edge_analysis": {},
        
        # Strategic Recommendations
        "focus_areas": [],
        "avoid_patterns": [],
        "optimization_suggestions": [],
        
        # Learning Progress Tracking
        "improvement_metrics": {},
        "next_period_targets": {}
    }
    
    try:
        # Get enhanced accuracy metrics
        enhanced_metrics = calculate_enhanced_accuracy(predictions)
        
        if not enhanced_metrics or enhanced_metrics["validated_predictions"] == 0:
            insights["performance_summary"] = {"status": "insufficient_data", "message": "Need more completed trades for analysis"}
            return insights
        
        # === PERFORMANCE SUMMARY ===
        insights["performance_summary"] = {
            "total_predictions": enhanced_metrics["total_predictions"],
            "completed_trades": enhanced_metrics["validated_predictions"],
            "overall_win_rate": f"{enhanced_metrics['win_rate_overall']:.1%}",
            "long_win_rate": f"{enhanced_metrics['win_rate_long']:.1%}",
            "short_win_rate": f"{enhanced_metrics['win_rate_short']:.1%}",
            "r_expectancy": f"{enhanced_metrics['r_expectancy']:.2f}R",
            "average_rr_ratio": f"{enhanced_metrics['average_rr_ratio']:.1f}:1",
            "profit_factor": f"{enhanced_metrics['profit_factor']:.2f}" if enhanced_metrics['profit_factor'] != float('inf') else "∞",
            "profitability_status": "Profitable" if enhanced_metrics['r_expectancy'] > 0 else "Unprofitable"
        }
        
        # === BEST SETUP FINDINGS ===
        if enhanced_metrics["best_setup_analysis"]:
            setup_findings = {}
            
            for i, (setup_name, setup_data) in enumerate(enhanced_metrics["best_setup_analysis"].items()):
                if i >= 3:  # Top 3 setups
                    break
                    
                active_signals = [k.replace("_", " ").title() for k, v in setup_data["signals_used"].items() if v]
                
                setup_findings[f"rank_{i+1}"] = {
                    "setup_name": setup_name.replace("_", " ").title(),
                    "win_rate": f"{setup_data['win_rate']:.1%}",
                    "avg_return": f"{setup_data['avg_r_per_trade']:.2f}R",
                    "expectancy": f"{setup_data['expectancy']:.2f}",
                    "sample_size": setup_data['total_trades'],
                    "signals_used": active_signals,
                    "confluence_score": f"{setup_data['confluence_score']:.1f}/10",
                    "recommendation": f"{'HIGH PRIORITY' if setup_data['expectancy'] > 0.5 else 'MODERATE'} - Focus on this setup"
                }
            
            insights["best_setup_findings"] = setup_findings
        
        # === BEST TIME FINDINGS ===
        if enhanced_metrics["best_time_analysis"]:
            time_findings = {}
            
            for i, (time_slot, time_data) in enumerate(enhanced_metrics["best_time_analysis"].items()):
                if i >= 3:  # Top 3 times
                    break
                    
                time_findings[f"rank_{i+1}"] = {
                    "time_slot": time_slot,
                    "session": time_data['session'].replace("_", " ").title(),
                    "win_rate": f"{time_data['win_rate']:.1%}",
                    "avg_return": f"{time_data['avg_r_per_trade']:.2f}R",
                    "sample_size": time_data['total_trades'],
                    "recommendation": f"{'OPTIMAL' if time_data['win_rate'] > 0.6 else 'GOOD'} trading window"
                }
            
            insights["best_time_findings"] = time_findings
        
        # === WORST MISTAKE PATTERNS ===
        if enhanced_metrics["worst_mistakes_analysis"]:
            mistake_findings = {}
            
            for i, (mistake_code, mistake_data) in enumerate(enhanced_metrics["worst_mistakes_analysis"].items()):
                if i >= 3:  # Top 3 mistakes
                    break
                    
                mistake_findings[f"priority_{i+1}"] = {
                    "mistake_type": mistake_data['mistake_description'],
                    "frequency": mistake_data['frequency'],
                    "avg_loss_per_occurrence": f"{mistake_data['avg_loss_r']:.2f}R",
                    "total_cost": f"{mistake_data['total_impact_r']:.2f}R",
                    "impact_score": f"{mistake_data['impact_score']:.1f}",
                    "fix_priority": "CRITICAL" if mistake_data['impact_score'] > 2.0 else "HIGH",
                    "suggested_fix": get_mistake_fix_suggestion(mistake_code)
                }
            
            insights["worst_mistake_patterns"] = mistake_findings
        
        # === MARKET EDGE ANALYSIS ===
        confluence_analysis = {}
        if enhanced_metrics["confluence_performance"]:
            for level, data in enhanced_metrics["confluence_performance"].items():
                confluence_analysis[f"{level}_confluence"] = {
                    "win_rate": f"{data['win_rate']:.1%}",
                    "avg_return": f"{data['avg_r_per_trade']:.2f}R",
                    "trade_count": data['total_trades'],
                    "recommendation": get_confluence_recommendation(level, data['win_rate'])
                }
        
        insights["market_edge_analysis"] = {
            "confluence_performance": confluence_analysis,
            "key_edge_discovery": enhanced_metrics.get("key_insights", []),
            "market_bias": determine_market_bias(enhanced_metrics)
        }
        
        # === STRATEGIC RECOMMENDATIONS ===
        focus_areas = []
        avoid_patterns = []
        optimization_suggestions = []
        
        # Focus Areas
        if enhanced_metrics["best_setup_analysis"]:
            best_setup = list(enhanced_metrics["best_setup_analysis"].keys())[0]
            best_setup_data = enhanced_metrics["best_setup_analysis"][best_setup]
            if best_setup_data["expectancy"] > 0.3:
                focus_areas.append(f"Increase frequency of {best_setup.replace('_', ' ')} setups (highest expectancy)")
        
        if enhanced_metrics["best_time_analysis"]:
            best_time = list(enhanced_metrics["best_time_analysis"].keys())[0]
            best_time_data = enhanced_metrics["best_time_analysis"][best_time]
            if best_time_data["win_rate"] > 0.65:
                focus_areas.append(f"Schedule more predictions around {best_time} ({best_time_data['session'].replace('_', ' ')})")
        
        # Avoid Patterns
        if enhanced_metrics["worst_mistakes_analysis"]:
            worst_mistake = list(enhanced_metrics["worst_mistakes_analysis"].keys())[0]
            worst_mistake_data = enhanced_metrics["worst_mistakes_analysis"][worst_mistake]
            avoid_patterns.append(f"PRIORITY: Stop {worst_mistake_data['mistake_description'].lower()}")
        
        if "low" in enhanced_metrics["confluence_performance"]:
            low_conf_data = enhanced_metrics["confluence_performance"]["low"]
            if low_conf_data["win_rate"] < 0.4:
                avoid_patterns.append("Filter out low confluence setups (win rate below 40%)")
        
        # Optimization Suggestions
        if enhanced_metrics["win_rate_overall"] < 0.5 and enhanced_metrics["average_rr_ratio"] < 2.0:
            optimization_suggestions.append("Increase RR ratio targets to 2:1 minimum to offset low win rate")
        
        if enhanced_metrics["r_expectancy"] < 0.1:
            optimization_suggestions.append("Focus on confluence improvement - current expectancy too low")
        
        optimization_suggestions.extend(enhanced_metrics.get("actionable_recommendations", []))
        
        insights["focus_areas"] = focus_areas[:3]  # Top 3
        insights["avoid_patterns"] = avoid_patterns[:3]  # Top 3
        insights["optimization_suggestions"] = optimization_suggestions[:5]  # Top 5
        
        # === IMPROVEMENT METRICS ===
        # Compare with previous period (simplified - would need historical data)
        insights["improvement_metrics"] = {
            "current_expectancy": enhanced_metrics["r_expectancy"],
            "current_win_rate": enhanced_metrics["win_rate_overall"],
            "current_rr_ratio": enhanced_metrics["average_rr_ratio"],
            "trend_analysis": "Requires historical data for comparison",
            "learning_velocity": calculate_learning_velocity(enhanced_metrics)
        }
        
        # === NEXT PERIOD TARGETS ===
        current_wr = enhanced_metrics["win_rate_overall"]
        current_expectancy = enhanced_metrics["r_expectancy"]
        
        target_wr = min(current_wr + 0.05, 0.8)  # Aim for 5% improvement, max 80%
        target_expectancy = max(current_expectancy + 0.1, 0.3)  # Aim for +0.1R, min 0.3R
        
        insights["next_period_targets"] = {
            "target_win_rate": f"{target_wr:.1%}",
            "target_expectancy": f"{target_expectancy:.2f}R",
            "target_mistake_reduction": "50% reduction in top mistake frequency",
            "target_confluence_improvement": "Increase high confluence trade percentage by 20%",
            "focus_metric": "R-expectancy" if current_expectancy < 0.2 else "Win rate optimization"
        }
        
    except Exception as e:
        print(f"[ERROR] Generating deep learning insights: {e}")
        import traceback
        traceback.print_exc()
        insights["error"] = str(e)
    
    return insights

def get_mistake_fix_suggestion(mistake_code):
    """Get specific suggestions for fixing trading mistakes"""
    suggestions = {
        "poor_rr_ratio": "Set minimum 2:1 RR ratio rule, widen stop losses or better entry timing",
        "ignored_greed_signal": "Create rule: No longs when Fear & Greed > 75, wait for cooldown",
        "ignored_fear_signal": "Create rule: No shorts when Fear & Greed < 25, look for bounces",
        "short_in_low_volatility": "Avoid shorts when expected move < 3%, focus on longs in low vol",
        "insufficient_rr_for_volatility": "High volatility trades need 3:1+ RR, adjust targets",
        "overconfident_loss": "Cap position size when confidence > 80%, add confirmation delays",
        "rushed_entry": "Implement 30-min confirmation delay, wait for retests",
        "bought_overbought": "RSI > 70 = wait for pullback, use RSI divergence instead",
        "sold_oversold": "RSI < 30 = wait for relief bounce, look for reversal patterns",
        "bad_timing_session": "Avoid predictions during 00:00-03:00 UTC (low liquidity)"
    }
    return suggestions.get(mistake_code, "Review and create specific rules to avoid this pattern")

def get_confluence_recommendation(level, win_rate):
    """Get recommendations based on confluence performance"""
    if level == "high" and win_rate > 0.7:
        return "EXCELLENT - Prioritize these setups"
    elif level == "high" and win_rate > 0.5:
        return "GOOD - Continue focusing on high confluence"
    elif level == "medium" and win_rate > 0.6:
        return "SOLID - Good backup when high confluence unavailable"
    elif level == "low" and win_rate < 0.4:
        return "AVOID - Filter out low confluence setups"
    else:
        return "MONITOR - Track performance closely"

def determine_market_bias(metrics):
    """Determine overall market bias and trading preferences"""
    long_wr = metrics["win_rate_long"]
    short_wr = metrics["win_rate_short"]
    
    if long_wr > short_wr + 0.15:
        return f"LONG BIAS - {long_wr:.1%} vs {short_wr:.1%} (favor bullish setups)"
    elif short_wr > long_wr + 0.15:
        return f"SHORT BIAS - {short_wr:.1%} vs {long_wr:.1%} (favor bearish setups)"
    else:
        return f"BALANCED - Similar performance both directions ({long_wr:.1%} L / {short_wr:.1%} S)"

def calculate_learning_velocity(metrics):
    """Calculate how fast the system is learning (simplified)"""
    expectancy = metrics["r_expectancy"]
    win_rate = metrics["win_rate_overall"]
    
    if expectancy > 0.3 and win_rate > 0.6:
        return "FAST - Excellent performance metrics"
    elif expectancy > 0.1 and win_rate > 0.5:
        return "MODERATE - Good progress, room for improvement"
    elif expectancy > 0:
        return "SLOW - Positive but needs optimization"
    else:
        return "NEGATIVE - Requires major strategy revision"

def save_deep_learning_insights(insights):
    """Save deep learning insights for AI evolution"""
    period_type = insights.get('period_type', 'weekly')
    analysis_date = insights.get('analysis_date', datetime.now().isoformat())
    
    # Extract period from analysis_date for database storage
    period_str = analysis_date[:10]  # YYYY-MM-DD format
    if period_type == 'weekly':
        # Convert to week format (e.g., 2025-W20)
        date_obj = datetime.fromisoformat(analysis_date)
        week_num = date_obj.isocalendar()[1]
        period_str = f"{date_obj.year}-W{week_num:02d}"
    elif period_type == 'monthly':
        # Convert to month format (e.g., 2025-05)
        period_str = analysis_date[:7]  # YYYY-MM format
    
    # Try to save to database first
    success = False
    if DATABASE_AVAILABLE:
        try:
            success = db_manager.save_learning_insight(period_type, period_str, insights)
            if success:
                print(f"[INFO] Deep learning insights saved to database for {period_type} period {period_str}")
        except Exception as e:
            print(f"[ERROR] Failed to save insights to database: {e}")
    
    # Fallback to JSON file if database failed or not available
    if not success:
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
        
        print(f"[INFO] Deep learning insights saved to JSON file - {len(all_insights)} total analyses stored")

def format_deep_insights_summary(insights):
    """Format deep insights for Telegram - Professional Review Style"""
    if "error" in insights:
        return f"📊 Deep Analysis: {insights['error']}"
    
    report = f"🧠 <b>{insights['period_type'].upper()} DEEP LEARNING ANALYSIS</b>\n"
    report += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
    report += f"{'═' * 40}\n\n"
    
    core = insights.get("performance_summary", {})
    
    # Executive Summary
    report += f"<b>📈 EXECUTIVE SUMMARY</b>\n"
    report += f"• Total Trades: {core.get('completed_trades', 0)}\n"
    report += f"• Win Rate: {core.get('overall_win_rate', '0%')}\n"
    report += f"• R-Expectancy: {core.get('r_expectancy', '0.00R')}\n"
    report += f"• Profit Factor: {core.get('profit_factor', '0.0')}\n"
    report += f"• Status: {core.get('profitability_status', 'Unknown')}\n\n"
    
    # Top Performing Setups
    if insights.get("best_setup_findings"):
        report += f"<b>⭐ BEST PERFORMING SETUPS</b>\n"
        for rank_key, setup in insights["best_setup_findings"].items():
            rank_num = rank_key.split('_')[1]
            signals_text = ', '.join(setup.get('signals_used', [])[:2]) if setup.get('signals_used') else 'None'
            report += f"{rank_num}. {setup.get('setup_name', 'Unknown')}\n"
            report += f"   • Win Rate: {setup.get('win_rate', '0%')}\n"
            report += f"   • Avg R: {setup.get('avg_return', '0.00R')}\n"
            report += f"   • Trades: {setup.get('sample_size', 0)}\n"
            report += f"   • Signals: {signals_text}\n\n"
    
    # Best Timing
    if insights.get("best_time_findings"):
        report += f"<b>⏰ OPTIMAL TIMING</b>\n"
        
        for rank_key, time_data in insights["best_time_findings"].items():
            rank_num = rank_key.split('_')[1]
            report += f"{rank_num}. {time_data.get('time_slot', 'Unknown')} ({time_data.get('session', 'Unknown')}) - {time_data.get('win_rate', '0%')}\n"
        report += "\n"
    
    # Market Edge Analysis  
    market_edge = insights.get("market_edge_analysis", {})
    confluence_perf = market_edge.get("confluence_performance", {})
    if confluence_perf:
        report += f"<b>🌊 CONFLUENCE PERFORMANCE</b>\n"
        for level, stats in confluence_perf.items():
            level_name = level.replace('_confluence', '').title()
            report += f"• {level_name}: {stats.get('win_rate', '0%')} ({stats.get('trade_count', 0)} trades)\n"
        report += "\n"
    
    # Key Insights
    key_insights = market_edge.get("key_edge_discovery", [])
    if key_insights:
        report += f"<b>💡 KEY INSIGHTS</b>\n"
        for i, insight in enumerate(key_insights[:3], 1):
            report += f"{i}. {insight}\n"
        report += "\n"
    
    # Worst Mistakes
    if insights.get("worst_mistake_patterns"):
        report += f"<b>⚠️ TOP MISTAKES TO AVOID</b>\n"
        for priority_key, mistake in insights["worst_mistake_patterns"].items():
            priority_num = priority_key.split('_')[1]
            report += f"{priority_num}. {mistake.get('mistake_type', 'Unknown')} (Impact: {mistake.get('impact_score', '0')})\n"
        report += "\n"
    
    # Focus Areas
    if insights.get("focus_areas"):
        report += f"<b>🎯 FOCUS AREAS</b>\n"
        for i, area in enumerate(insights["focus_areas"], 1):
            report += f"{i}. {area}\n"
        report += "\n"
    
    # Optimization Suggestions
    if insights.get("optimization_suggestions"):
        report += f"<b>🔧 OPTIMIZATION SUGGESTIONS</b>\n"
        for i, suggestion in enumerate(insights["optimization_suggestions"][:3], 1):
            report += f"{i}. {suggestion}\n"
        report += "\n"
    
    report += f"<i>🚀 Evolution in progress - becoming more profitable!</i>"
    
    return report

def extract_price_from_text(text, price_type):
    """Extract price from AI prediction text"""
    if not text:
        return None
    
    # Look for specific price patterns
    patterns = {
        "entry": [r'entry.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)', r'buy.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)'],
        "target": [r'target.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)', r'tp.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)'],
        "stop": [r'stop.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)', r'sl.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)']
    }
    
    for pattern in patterns.get(price_type, []):
        match = re.search(pattern, text.lower())
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except:
                continue
    return None

def extract_direction_from_text(text):
    """Extract direction from AI prediction text"""
    if not text:
        return "NEUTRAL"
    
    text_lower = text.lower()
    if any(word in text_lower for word in ['buy', 'long', 'bullish', 'rally']):
        return "BUY"
    elif any(word in text_lower for word in ['sell', 'short', 'bearish', 'dip']):
        return "SELL"
    return "NEUTRAL"

def extract_confluence_signals(prediction):
    """Extract and analyze confluence signals used in prediction"""
    signals = {
        "technical_analysis": False,
        "volume_analysis": False,
        "support_resistance": False,
        "rsi_momentum": False,
        "macd_signal": False,
        "funding_sentiment": False,
        "fear_greed": False,
        "divergence": False,
        "breakout_pattern": False,
        "trend_alignment": False
    }
    
    try:
        # Analyze professional analysis components
        pro_analysis = prediction.get("predictions", {}).get("professional_analysis", {})
        ai_prediction = prediction.get("predictions", {}).get("ai_prediction", "")
        
        if pro_analysis:
            component_scores = pro_analysis.get("component_scores", {})
            
            # Map component scores to signals
            for component, score in component_scores.items():
                if score > 6.0:  # High confidence signal
                    if "price_action" in component:
                        signals["technical_analysis"] = True
                    elif "volume" in component:
                        signals["volume_analysis"] = True
                    elif "momentum" in component:
                        signals["rsi_momentum"] = True
                    elif "funding" in component or "sentiment" in component:
                        signals["funding_sentiment"] = True
                    elif "volatility" in component:
                        signals["breakout_pattern"] = True
            
            # Check strongest signal
            strongest = pro_analysis.get("key_factors", {}).get("strongest_signal", ["", 0])
            if strongest[1] > 7.0:
                signal_type = strongest[0].lower()
                if "technical" in signal_type:
                    signals["technical_analysis"] = True
                elif "volume" in signal_type:
                    signals["volume_analysis"] = True
                elif "support" in signal_type or "resistance" in signal_type:
                    signals["support_resistance"] = True
        
        # Analyze AI prediction text for signals
        if ai_prediction:
            text_lower = ai_prediction.lower()
            
            if any(word in text_lower for word in ['rsi', 'momentum', 'oversold', 'overbought']):
                signals["rsi_momentum"] = True
            
            if any(word in text_lower for word in ['macd', 'moving average', 'crossover']):
                signals["macd_signal"] = True
                
            if any(word in text_lower for word in ['support', 'resistance', 'level']):
                signals["support_resistance"] = True
                
            if any(word in text_lower for word in ['volume', 'accumulation', 'distribution']):
                signals["volume_analysis"] = True
                
            if any(word in text_lower for word in ['funding', 'sentiment', 'fear', 'greed']):
                signals["funding_sentiment"] = True
                
            if any(word in text_lower for word in ['divergence', 'hidden', 'regular']):
                signals["divergence"] = True
                
            if any(word in text_lower for word in ['breakout', 'breakdown', 'pattern']):
                signals["breakout_pattern"] = True
                
            if any(word in text_lower for word in ['trend', 'uptrend', 'downtrend', 'alignment']):
                signals["trend_alignment"] = True
        
        # Check market data for implicit signals
        market_data = prediction.get("market_data", {})
        if market_data:
            fear_greed = market_data.get("fear_greed", 50)
            if isinstance(fear_greed, dict):
                fear_greed = fear_greed.get("index", 50)
            
            if fear_greed < 25 or fear_greed > 75:
                signals["fear_greed"] = True
    
    except Exception as e:
        print(f"[WARN] Error extracting confluence signals: {e}")
    
    return signals

def calculate_confluence_score(signals):
    """Calculate confluence score based on signal strength"""
    if not signals:
        return 0
    
    # Weight different signals by importance
    signal_weights = {
        "technical_analysis": 2.0,
        "volume_analysis": 1.5,
        "support_resistance": 2.0,
        "rsi_momentum": 1.0,
        "macd_signal": 1.5,
        "funding_sentiment": 1.0,
        "fear_greed": 0.5,
        "divergence": 2.0,
        "breakout_pattern": 1.5,
        "trend_alignment": 1.5
    }
    
    total_score = 0
    max_possible = sum(signal_weights.values())
    
    for signal, active in signals.items():
        if active:
            total_score += signal_weights.get(signal, 1.0)
    
    return (total_score / max_possible) * 10  # Scale to 0-10

def identify_trade_mistakes(prediction, outcome, market_data, trade_metrics):
    """Identify specific mistake patterns in trades"""
    mistakes = []
    
    try:
        rr_ratio = trade_metrics.get("rr_ratio", 0)
        volatility = trade_metrics.get("volatility", "medium")
        sentiment = trade_metrics.get("sentiment", "neutral")
        confidence = trade_metrics.get("confidence", 60)
        duration_hours = trade_metrics.get("duration_hours", 0)
        
        # Get prediction details
        pro_analysis = prediction.get("predictions", {}).get("professional_analysis", {})
        direction = pro_analysis.get("primary_scenario", "NEUTRAL") if pro_analysis else "NEUTRAL"
        
        # Mistake 1: Poor Risk-Reward Ratio
        if rr_ratio < 1.5 and outcome == "SL_HIT":
            mistakes.append("poor_rr_ratio")
        
        # Mistake 2: Ignored Sentiment (Counter-trend in wrong conditions)
        if sentiment == "extreme_greed" and direction in ["BUY", "LONG", "BULLISH"] and outcome == "SL_HIT":
            mistakes.append("ignored_greed_signal")
        elif sentiment == "extreme_fear" and direction in ["SELL", "SHORT", "BEARISH"] and outcome == "SL_HIT":
            mistakes.append("ignored_fear_signal")
        
        # Mistake 3: Wrong Volatility Assessment
        if volatility == "low" and direction in ["SELL", "SHORT", "BEARISH"] and outcome == "SL_HIT":
            mistakes.append("short_in_low_volatility")
        elif volatility == "high" and rr_ratio < 2.0 and outcome == "SL_HIT":
            mistakes.append("insufficient_rr_for_volatility")
        
        # Mistake 4: Overconfidence
        if confidence > 80 and outcome == "SL_HIT":
            mistakes.append("overconfident_loss")
        
        # Mistake 5: Rushed Entry (very quick hits)
        if duration_hours < 1 and outcome == "SL_HIT":
            mistakes.append("rushed_entry")
        
        # Mistake 6: Didn't Wait for Confirmation
        rsi = market_data.get("btc_rsi", 50)
        if direction in ["BUY", "LONG", "BULLISH"] and rsi > 75 and outcome == "SL_HIT":
            mistakes.append("bought_overbought")
        elif direction in ["SELL", "SHORT", "BEARISH"] and rsi < 25 and outcome == "SL_HIT":
            mistakes.append("sold_oversold")
        
        # Mistake 7: Ignored Support/Resistance
        entry_price = trade_metrics.get("entry_price", 0)
        # This would need support/resistance data to implement fully
        
        # Mistake 8: Wrong Time Session
        try:
            # Handle both timestamp formats for prediction timestamp
            pred_timestamp_str = prediction["timestamp"]
            if 'T' in pred_timestamp_str:
                pred_time = datetime.fromisoformat(pred_timestamp_str.replace('Z', ''))
            else:
                pred_time = datetime.strptime(pred_timestamp_str, "%Y-%m-%d %H:%M:%S")
            pred_hour = pred_time.hour
        except Exception as e:
            print(f"[WARN] Error parsing prediction timestamp for mistake analysis: {e}")
            pred_hour = 12  # Default to noon
            
        if pred_hour in [0, 1, 2, 23] and outcome == "SL_HIT":  # Dead hours
            mistakes.append("bad_timing_session")
        
    except Exception as e:
        print(f"[WARN] Error identifying trade mistakes: {e}")
    
    return mistakes

def classify_time_session(hour):
    """Classify trading session based on hour"""
    if 0 <= hour < 6:
        return "asia_night"
    elif 6 <= hour < 12:
        return "asia_day"
    elif 12 <= hour < 18:
        return "europe"
    else:
        return "us_evening"

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
