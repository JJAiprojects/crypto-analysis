#!/usr/bin/env python3

import requests
import json
import pandas as pd
from datetime import datetime
import time
import os
import re

def validate_predictions():
    """Check if price has hit predicted levels and update prediction file"""
    prediction_file = "detailed_predictions.json"
    
    if not os.path.exists(prediction_file):
        print("[INFO] No predictions to validate yet")
        return
    
    # Get current prices
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd")
        current_prices = response.json()
        btc_price = current_prices["bitcoin"]["usd"]
        eth_price = current_prices["ethereum"]["usd"]
        
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
    
    # Validate open predictions
    updated = False
    now = datetime.now()
    
    for i, prediction in enumerate(predictions):
        # Skip already completed predictions
        if prediction.get("final_accuracy") is not None:
            continue
        
        # Get prediction timestamp
        pred_time = datetime.strptime(prediction["timestamp"], "%Y-%m-%d %H:%M:%S")
        
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
                tp_match = re.findall(r'TP[0-9]+:\s*\$([0-9,]+(?:\.[0-9]+)?)', tp_str)
                for tp in tp_match:
                    try:
                        # Convert to float, removing commas
                        tp_targets.append(float(tp.replace(',', '')))
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
            
            # Check if current price is within entry range
            if entry_range and len(entry_range) == 2:
                min_range = min(entry_range)
                max_range = max(entry_range)
                if min_range <= btc_price <= max_range:
                    validation_point = {
                        "coin": "BTC",
                        "type": "ENTRY_POINT_HIT",
                        "predicted_range": [min_range, max_range],
                        "actual_price": btc_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    prediction["validation_points"].append(validation_point)
                    updated = True
                    print(f"[INFO] BTC entry point hit: ${btc_price}")
            
            # Get direction
            direction = btc_pred.get("direction", "").upper() if btc_pred.get("direction") else ""
            
            # Check take profit targets
            for idx, tp in enumerate(tp_targets):
                # For bullish direction, price needs to go up to hit TP
                # For bearish direction, price needs to go down to hit TP
                if (direction == "BULLISH" and btc_price >= tp) or \
                   (direction == "BEARISH" and btc_price <= tp):
                    validation_point = {
                        "coin": "BTC",
                        "type": f"TP{idx+1}_HIT",
                        "predicted_level": tp,
                        "actual_price": btc_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    prediction["validation_points"].append(validation_point)
                    updated = True
                    print(f"[INFO] BTC TP{idx+1} hit: ${btc_price}")
            
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
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    prediction["validation_points"].append(validation_point)
                    updated = True
                    print(f"[INFO] BTC stop loss hit: ${btc_price}")
        
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
                tp_match = re.findall(r'TP[0-9]+:\s*\$([0-9,]+(?:\.[0-9]+)?)', tp_str)
                for tp in tp_match:
                    try:
                        tp_targets.append(float(tp.replace(',', '')))
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
            
            # Check if current price is within entry range
            if entry_range and len(entry_range) == 2:
                min_range = min(entry_range)
                max_range = max(entry_range)
                if min_range <= eth_price <= max_range:
                    validation_point = {
                        "coin": "ETH",
                        "type": "ENTRY_POINT_HIT",
                        "predicted_range": [min_range, max_range],
                        "actual_price": eth_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    prediction["validation_points"].append(validation_point)
                    updated = True
                    print(f"[INFO] ETH entry point hit: ${eth_price}")
            
            # Get direction
            direction = eth_pred.get("direction", "").upper() if eth_pred.get("direction") else ""
            
            # Check take profit targets
            for idx, tp in enumerate(tp_targets):
                if (direction == "BULLISH" and eth_price >= tp) or \
                   (direction == "BEARISH" and eth_price <= tp):
                    validation_point = {
                        "coin": "ETH",
                        "type": f"TP{idx+1}_HIT",
                        "predicted_level": tp,
                        "actual_price": eth_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    prediction["validation_points"].append(validation_point)
                    updated = True
                    print(f"[INFO] ETH TP{idx+1} hit: ${eth_price}")
            
            # Check stop loss
            if sl_level:
                if (direction == "BULLISH" and eth_price <= sl_level) or \
                   (direction == "BEARISH" and eth_price >= sl_level):
                    validation_point = {
                        "coin": "ETH",
                        "type": "STOP_LOSS_HIT",
                        "predicted_level": sl_level,
                        "actual_price": eth_price,
                        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    prediction["validation_points"].append(validation_point)
                    updated = True
                    print(f"[INFO] ETH stop loss hit: ${eth_price}")
        
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
                                    print(f"[INFO] {coin} prediction from {pred_time} has expired. Final accuracy: {accuracy:.2f}%")
                        except Exception as e:
                            print(f"[ERROR] Failed to parse timeframe for {coin}: {e}")
    
    # Save updated predictions
    if updated:
        try:
            with open(prediction_file, "w") as f:
                json.dump(predictions, f, indent=4)
            print("[INFO] Prediction file updated")
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
