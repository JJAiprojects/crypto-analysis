#!/usr/bin/env python3

import requests
import json
import os
import pandas as pd
import time
import concurrent.futures
import yfinance as yf
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import re
from openai import OpenAI
from telegram_utils import send_telegram_message, TelegramBot
from ml_enhancer import PredictionEnhancer
from risk_manager import RiskManager
from dotenv import load_dotenv

# ----------------------------
# 1. Config
# ----------------------------
def load_config():
    """Load configuration with proper handling of sensitive data"""
    # Load environment variables
    load_dotenv()
    
    # Initialize config with default values
    config = {
        "api_keys": {
            "openai": os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY"),
            "fred": os.getenv("FRED_API_KEY", "YOUR_FRED_API_KEY"),
            "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY", "YOUR_ALPHAVANTAGE_API_KEY")
        },
        "telegram": {
            "enabled": True,
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
            "test": {
                "enabled": True,
                "bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN", ""),
                "chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID", "")
            }
        },
        "ai_insights_enabled": True,
        "storage": {
            "file": "crypto_data_history.csv"
        },
        "api": {
            "max_retries": 3,
            "timeout": 10,
            "backoff_factor": 2
        },
        "indicators": {
            "include_macroeconomic": True,
            "include_stock_indices": True,
            "include_commodities": True,
            "include_social_metrics": True
        },
        "ml": {
            "enabled": True,
            "model_directory": "models",
            "retrain_interval_days": 7
        },
        "risk": {
            "enabled": True,
            "max_risk_per_trade": 0.02,
            "risk_reward_ratio": 2,
            "account_size": 10000
        },
        "test_mode": {
            "enabled": False,
            "send_telegram": False,
            "output_prefix": "test_"
        }
    }
    
    # Try to load existing config
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                existing_config = json.load(f)
                # Update config with existing values while preserving structure
                for key, value in existing_config.items():
                    if key in config:
                        if isinstance(value, dict) and isinstance(config[key], dict):
                            config[key].update(value)
                        else:
                            config[key] = value
        except Exception as e:
            print(f"[ERROR] Loading config: {e}")
    
    # Save the updated config
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Saving config: {e}")
    
    return config

config = load_config()

# Initialize ML and Risk Management components
ml_enhancer = PredictionEnhancer()
risk_manager = RiskManager()

# ----------------------------
# 2. API Request Handler
# ----------------------------
def resilient_request(url, params=None, headers=None, max_retries=None, timeout=None):
    if max_retries is None:
        max_retries = config["api"]["max_retries"]
    if timeout is None:
        timeout = config["api"]["timeout"]
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            
            # Log response headers for debugging
            print(f"\n[DEBUG] API Response Headers for {url}:")
            for header, value in response.headers.items():
                print(f"  {header}: {value}")
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"[WARN] Rate limited, waiting {retry_after}s (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_after)
                continue
                
            # Check for other common status codes
            if response.status_code == 403:
                print(f"[ERROR] Access forbidden. Check if API endpoint is still valid: {url}")
                return None
            elif response.status_code == 404:
                print(f"[ERROR] Endpoint not found: {url}")
                return None
            elif response.status_code == 500:
                print(f"[ERROR] Server error from {url}")
                time.sleep(5)  # Wait before retrying
                continue
            
            # Check for remaining rate limits
            remaining = response.headers.get("X-Rate-Limit-Remaining")
            if remaining:
                print(f"[INFO] Remaining API calls: {remaining}")
                if int(remaining) < 10:
                    print("[WARN] Low on remaining API calls!")
                
            response.raise_for_status()
            
            # Check if response is valid JSON
            try:
                data = response.json()
                if not data:
                    print(f"[WARN] Empty response from {url}")
                    return None
                return data
            except json.JSONDecodeError as e:
                print(f"[ERROR] Invalid JSON response from {url}: {e}")
                print(f"Response text: {response.text[:200]}...")  # Print first 200 chars of response
                return None
            
        except requests.exceptions.RequestException as e:
            backoff = config["api"]["backoff_factor"] ** attempt
            print(f"[ERROR] API request failed (attempt {attempt+1}/{max_retries}): {e}")
            print(f"[INFO] Retrying in {backoff:.1f}s...")
            time.sleep(backoff)
    
    print(f"[CRITICAL] All {max_retries} attempts failed for URL: {url}")
    return None

# ----------------------------
# 3.1 Macroeconomic Data
# ----------------------------
def get_m2_money_supply():
    # First check for environment variable, then fallback to config file
    fred_key = os.environ.get("FRED_API_KEY")
    if not fred_key:
        fred_key = config["api_keys"]["fred"]
    
    if not fred_key or fred_key == "YOUR_FRED_API_KEY":
        print("[WARN] FRED API key not configured - using alternative source for M2 data")
        return get_m2_money_supply_alternative()
    
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "M2SL",
        "api_key": fred_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1
    }
    
    try:
        data = resilient_request(url, params)
        if data and "observations" in data and len(data["observations"]) > 0:
            latest = data["observations"][0]
            return {
                "m2_supply": float(latest["value"]) * 1e9,
                "m2_date": latest["date"]
            }
    except Exception as e:
        print(f"[ERROR] M2 Money Supply from FRED: {e}")
    
    return get_m2_money_supply_alternative()

def get_m2_money_supply_alternative():
    try:
        url = "https://fred.stlouisfed.org/series/M2SL"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        value_text = soup.select_one('.series-meta-observation-value')
        date_text = soup.select_one('.series-meta-observation-date')
        
        if value_text and date_text:
            value_str = value_text.text.strip()
            value = float(re.sub(r'[^\d.]', '', value_str)) * 1e9
            date = date_text.text.strip()
            return {
                "m2_supply": value,
                "m2_date": date
            }
    except Exception as e:
        print(f"[ERROR] Alternative M2 retrieval failed: {e}")
    
    return {
        "m2_supply": None,
        "m2_date": None
    }

def get_inflation_data():
    try:
        # First check for environment variable, then fallback to config file
        alpha_key = os.environ.get("ALPHAVANTAGE_API_KEY") 
        if not alpha_key:
            alpha_key = config["api_keys"]["alphavantage"]
            
        if not alpha_key or alpha_key == "YOUR_ALPHAVANTAGE_API_KEY":
            print("[WARN] AlphaVantage API key not configured - using alternative inflation source")
            return get_inflation_alternative()
            
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "CPI",
            "interval": "monthly",
            "apikey": alpha_key
        }
        
        data = resilient_request(url, params)
        if data and "data" in data and len(data["data"]) > 0:
            latest = data["data"][0]
            previous = data["data"][1]
            
            current = float(latest["value"])
            prev_year = None
            
            for entry in data["data"]:
                if entry["date"][:4] == str(int(latest["date"][:4]) - 1) and entry["date"][5:7] == latest["date"][5:7]:
                    prev_year = float(entry["value"])
                    break
            
            if prev_year:
                yoy_inflation = ((current - prev_year) / prev_year) * 100
            else:
                mom_inflation = ((current - float(previous["value"])) / float(previous["value"])) * 100
                yoy_inflation = mom_inflation * 12
            
            return {
                "inflation_rate": yoy_inflation,
                "inflation_date": latest["date"]
            }
    except Exception as e:
        print(f"[ERROR] Inflation data: {e}")
    
    return get_inflation_alternative()

def get_inflation_alternative():
    try:
        url = "https://www.usinflationcalculator.com/inflation/current-inflation-rates/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > 1:
                latest_row = rows[1]
                cells = latest_row.find_all('td')
                if len(cells) >= 13:
                    for cell in reversed(cells[1:-1]):
                        if cell.text.strip() and cell.text.strip() != '-':
                            try:
                                rate = float(cell.text.strip().replace('%', ''))
                                month = rows[0].find_all('th')[cells.index(cell)].text.strip()
                                year = datetime.now().year if datetime.now().month > 1 else datetime.now().year - 1
                                return {
                                    "inflation_rate": rate,
                                    "inflation_date": f"{year}-{month}"
                                }
                            except ValueError:
                                continue
    except Exception as e:
        print(f"[ERROR] Alternative inflation retrieval failed: {e}")
    
    return {
        "inflation_rate": None,
        "inflation_date": None
    }

def get_interest_rates():
    try:
        # First check for environment variable, then fallback to config file
        alpha_key = os.environ.get("ALPHAVANTAGE_API_KEY")
        if not alpha_key:
            alpha_key = config["api_keys"]["alphavantage"]
            
        if alpha_key and alpha_key != "YOUR_ALPHAVANTAGE_API_KEY":
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "FEDERAL_FUNDS_RATE",
                "interval": "daily",
                "apikey": alpha_key
            }
            
            data = resilient_request(url, params)
            if data and "data" in data and len(data["data"]) > 0:
                fed_rate = float(data["data"][0]["value"])
                fed_date = data["data"][0]["date"]
                
                params["function"] = "TREASURY_YIELD"
                params["maturity"] = "10year"
                
                t10_data = resilient_request(url, params)
                if t10_data and "data" in t10_data and len(t10_data["data"]) > 0:
                    t10_yield = float(t10_data["data"][0]["value"])
                    return {
                        "fed_rate": fed_rate,
                        "t10_yield": t10_yield,
                        "rate_date": fed_date
                    }
    except Exception as e:
        print(f"[ERROR] Interest rate data (method 1): {e}")
    
    try:
        tickers = {
            "^TNX": "t10_yield",
            "^FVX": "t5_yield",
        }
        
        rates = {"fed_rate": None}
        for ticker, key in tickers.items():
            try:
                data = yf.Ticker(ticker).history(period="1d")
                if not data.empty:
                    rates[key] = data['Close'].iloc[-1]
            except Exception as e:
                print(f"[ERROR] Failed to get data for {ticker}: {e}")
                
        try:
            url = "https://fred.stlouisfed.org/series/FEDFUNDS"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            value_text = soup.select_one('.series-meta-observation-value')
            
            if value_text:
                fed_rate = float(re.sub(r'[^\d.]', '', value_text.text.strip()))
                rates["fed_rate"] = fed_rate
        except Exception as e:
            print(f"[ERROR] Fed rate fallback retrieval: {e}")
            
        if rates["t10_yield"] is not None or rates["fed_rate"] is not None:
            rates["rate_date"] = datetime.now().strftime("%Y-%m-%d")
            return rates
            
    except Exception as e:
        print(f"[ERROR] Interest rate data (method 2): {e}")
    
    return {
        "fed_rate": None,
        "t10_yield": None,
        "rate_date": None
    }

def get_stock_indices():
    if not config["indicators"]["include_stock_indices"]:
        return {}
        
    tickers = {
        "^GSPC": "sp500",
        "^DJI": "dow_jones",
        "^IXIC": "nasdaq",
        "^VIX": "vix"
    }
    
    indices = {}
    try:
        for ticker, key in tickers.items():
            try:
                data = yf.Ticker(ticker).history(period="5d")
                if not data.empty:
                    current = data['Close'].iloc[-1]
                    prev = data['Close'].iloc[-2] if len(data) > 1 else None
                    
                    indices[key] = current
                    if prev:
                        indices[f"{key}_change"] = ((current - prev) / prev) * 100
            except Exception as e:
                print(f"[ERROR] Failed to get data for {ticker}: {e}")
                continue
        
        if indices:
            indices["indices_date"] = datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        print(f"[ERROR] Stock indices data: {e}")
    
    return indices

def get_commodity_prices():
    if not config["indicators"]["include_commodities"]:
        return {}
        
    tickers = {
        "GC=F": "gold",
        "SI=F": "silver",
        "CL=F": "crude_oil",
        "NG=F": "natural_gas"
    }
    
    commodities = {}
    try:
        for ticker, key in tickers.items():
            try:
                data = yf.Ticker(ticker).history(period="2d")
                if not data.empty:
                    commodities[key] = data['Close'].iloc[-1]
            except Exception as e:
                print(f"[ERROR] Failed to get data for {ticker}: {e}")
                continue
                
        if commodities:
            commodities["commodities_date"] = datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        print(f"[ERROR] Commodity prices: {e}")
    
    return commodities

def get_crypto_social_metrics():
    if not config["indicators"]["include_social_metrics"]:
        return {}
        
    try:
        crypto_terms = ["bitcoin", "ethereum", "crypto"]
        mentions = {}
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        try:
            url = "https://bitcointalk.org/index.php"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                stats = soup.select('.board_stats')
                if stats:
                    text = stats[0].text.strip()
                    numbers = re.findall(r'\d+', text)
                    if len(numbers) >= 2:
                        mentions["forum_posts"] = int(numbers[0])
                        mentions["forum_topics"] = int(numbers[1])
        except Exception as e:
            print(f"[ERROR] Forum stats retrieval: {e}")
            
        try:
            repos = {
                "bitcoin/bitcoin": "btc_github_stars",
                "ethereum/go-ethereum": "eth_github_stars"
            }
            
            for repo, key in repos.items():
                url = f"https://api.github.com/repos/{repo}"
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    mentions[key] = data.get("stargazers_count")
                    commits_url = f"https://api.github.com/repos/{repo}/commits"
                    commits_response = requests.get(commits_url, headers=headers, timeout=10)
                    if commits_response.status_code == 200:
                        recent_commits = len(commits_response.json())
                        coin = "btc" if "bitcoin" in repo else "eth"
                        mentions[f"{coin}_recent_commits"] = recent_commits
        except Exception as e:
            print(f"[ERROR] GitHub stats retrieval: {e}")
        
        if mentions:
            mentions["social_date"] = datetime.now().strftime("%Y-%m-%d")
            return mentions
            
    except Exception as e:
        print(f"[ERROR] Social metrics: {e}")
    
    return {}

# ----------------------------
# 3.2 Crypto Market Data
# ----------------------------
def get_crypto_data():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin,ethereum", "vs_currencies": "usd"}
    
    # Add CoinGecko-specific headers
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    
    data = resilient_request(url, params=params, headers=headers)
    if data:
        return {"btc": data["bitcoin"]["usd"], "eth": data["ethereum"]["usd"]}
    return {"btc": None, "eth": None}

def get_futures_sentiment():
    base_url = "https://fapi.binance.com"
    symbols = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
    data = {}
    
    def get_funding(symbol):
        url = f"{base_url}/fapi/v1/premiumIndex"
        data = resilient_request(url, {"symbol": symbol})
        return float(data["lastFundingRate"]) * 100 if data else None
        
    def get_ratio(symbol):
        url = f"{base_url}/futures/data/topLongShortAccountRatio"
        data = resilient_request(url, {"symbol": symbol, "period": "1d", "limit": 1})
        return (float(data[0]["longAccount"]), float(data[0]["shortAccount"])) if data else (None, None)
        
    def get_oi(symbol):
        url = f"{base_url}/futures/data/openInterestHist"
        data = resilient_request(url, {"symbol": symbol, "period": "5m", "limit": 1})
        return float(data[0]["sumOpenInterestValue"]) if data else None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols)*3) as executor:
        futures = {}
        for sym, label in symbols.items():
            futures[f"{label}_funding"] = executor.submit(get_funding, sym)
            futures[f"{label}_ratio"] = executor.submit(get_ratio, sym)
            futures[f"{label}_oi"] = executor.submit(get_oi, sym)
        
        for sym, label in symbols.items():
            funding = futures[f"{label}_funding"].result()
            long_ratio, short_ratio = futures[f"{label}_ratio"].result()
            oi = futures[f"{label}_oi"].result()
            
            data[label] = {
                "funding_rate": funding,
                "long_ratio": long_ratio,
                "short_ratio": short_ratio,
                "open_interest": oi
            }
            
            data[f"{label.lower()}_funding"] = funding
            
    return data

def get_fear_greed_index():
    try:
        data = resilient_request("https://api.alternative.me/fng/")
        if data:
            return {"index": int(data["data"][0]["value"]), "sentiment": data["data"][0]["value_classification"]}
    except Exception as e:
        print(f"[ERROR] Fear & Greed: {e}")
    return {"index": None, "sentiment": None}

def get_btc_dominance():
    try:
        data = resilient_request("https://api.coingecko.com/api/v3/global")
        if data:
            return data["data"]["market_cap_percentage"]["btc"]
    except Exception as e:
        print(f"[ERROR] BTC Dominance: {e}")
    return None

def get_global_market_cap():
    try:
        data = resilient_request("https://api.coingecko.com/api/v3/global")
        if data:
            return data["data"]["total_market_cap"]["usd"], data["data"]["market_cap_change_percentage_24h_usd"]
    except Exception as e:
        print(f"[ERROR] Global Market Cap: {e}")
    return None, None

def get_trading_volumes():
    try:
        data = resilient_request("https://api.coingecko.com/api/v3/coins/markets", 
                                params={"vs_currency": "usd", "ids": "bitcoin,ethereum"})
        if data:
            volumes = {}
            for coin in data:
                coin_id = coin["id"]
                volumes[coin_id] = coin["total_volume"]
                if coin_id == "bitcoin":
                    volumes["btc_volume"] = coin["total_volume"]
                elif coin_id == "ethereum":
                    volumes["eth_volume"] = coin["total_volume"]
            return volumes
    except Exception as e:
        print(f"[ERROR] Trading Volumes: {e}")
    return {"btc_volume": None, "eth_volume": None}

def get_technical_indicators():
    url = "https://api.binance.com/api/v3/klines"
    symbols = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
    indicators = {}
    
    print("\n[DEBUG] Starting technical analysis...")
    
    for symbol, label in symbols.items():
        try:
            print(f"\n[DEBUG] Analyzing {label}...")
            
            # Get more historical data for better analysis
            params = {
                "symbol": symbol,
                "interval": "1d",
                "limit": 50
            }
            
            # Add Binance-specific headers
            headers = {
                "X-MBX-APIKEY": "",  # Empty for public endpoints
                "User-Agent": "Mozilla/5.0"  # Add user agent to avoid some rate limits
            }
            
            data = resilient_request(url, params=params, headers=headers)
            if not data:
                print(f"[ERROR] No data received for {label}")
                continue
                
            print(f"[DEBUG] Received {len(data)} candles for {label}")
            
            # Extract price data
            closes = [float(k[4]) for k in data]
            highs = [float(k[2]) for k in data]
            lows = [float(k[3]) for k in data]
            volumes = [float(k[5]) for k in data]
            
            current_price = closes[-1]
            print(f"[DEBUG] Current price: ${current_price:,.2f}")
            
            # Calculate moving averages
            sma7 = sum(closes[-7:]) / 7
            sma14 = sum(closes[-14:]) / 14
            sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
            
            sma50_str = f"${sma50:,.2f}" if sma50 is not None else "N/A"
            print(f"[DEBUG] Moving Averages - SMA7: ${sma7:,.2f}, SMA14: ${sma14:,.2f}, SMA50: {sma50_str}")
            
            # Calculate RSI
            changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [max(0, c) for c in changes]
            losses = [max(0, -c) for c in changes]
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            rs = avg_gain / avg_loss if avg_loss != 0 else 1e10
            rsi = 100 - (100 / (1 + rs))
            
            print(f"[DEBUG] RSI: {rsi:.2f}")
            
            # Calculate support and resistance levels
            recent_highs = highs[-20:]
            recent_lows = lows[-20:]
            
            # Find local maxima and minima
            resistance_levels = []
            support_levels = []
            
            for i in range(1, len(recent_highs)-1):
                if recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i+1]:
                    resistance_levels.append(recent_highs[i])
                if recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i+1]:
                    support_levels.append(recent_lows[i])
            
            # Get nearest support and resistance
            nearest_support = max([s for s in support_levels if s < current_price], default=current_price * 0.95)
            nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.05)
            
            print(f"[DEBUG] Support: ${nearest_support:,.2f}, Resistance: ${nearest_resistance:,.2f}")
            
            # Calculate ATR for volatility
            tr_values = []
            for i in range(1, len(closes)):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                )
                tr_values.append(tr)
            atr = sum(tr_values[-14:]) / 14
            
            print(f"[DEBUG] ATR: ${atr:,.2f}")
            
            # Determine trend with multiple confirmations
            trend = "neutral"
            if sma7 > sma14:
                if sma50 and closes[-1] > sma50:
                    trend = "bullish"
                else:
                    trend = "bullish_weak"
            elif sma7 < sma14:
                if sma50 and closes[-1] < sma50:
                    trend = "bearish"
                else:
                    trend = "bearish_weak"
            
            print(f"[DEBUG] Trend: {trend}")
            
            # Determine RSI momentum zone
            rsi_zone = "neutral"
            if rsi > 60:
                rsi_zone = "bullish"
            elif rsi < 40:
                rsi_zone = "bearish"
            
            print(f"[DEBUG] RSI Zone: {rsi_zone}")
            
            # Calculate volume trend
            avg_volume = sum(volumes[-5:]) / 5
            volume_trend = "increasing" if volumes[-1] > avg_volume * 1.2 else "decreasing" if volumes[-1] < avg_volume * 0.8 else "stable"
            
            print(f"[DEBUG] Volume Trend: {volume_trend}")
            
            # Generate signal with multiple confirmations
            signal = "NEUTRAL"
            signal_confidence = 0.0
            
            # Base confidence on trend strength
            if trend == "bullish":
                base_confidence = 7.0
            elif trend == "bullish_weak":
                base_confidence = 5.0
            elif trend == "bearish":
                base_confidence = 7.0
            elif trend == "bearish_weak":
                base_confidence = 5.0
            else:
                base_confidence = 3.0
            
            # Adjust confidence based on RSI
            if rsi > 70:
                rsi_factor = 1.2 if trend == "bearish" or trend == "bearish_weak" else 0.8
            elif rsi < 30:
                rsi_factor = 1.2 if trend == "bullish" or trend == "bullish_weak" else 0.8
            else:
                rsi_factor = 1.0
            
            # Adjust confidence based on volume
            volume_factor = 1.2 if volume_trend == "increasing" else 0.8 if volume_trend == "decreasing" else 1.0
            
            # Calculate final confidence
            signal_confidence = min(10, base_confidence * rsi_factor * volume_factor)
            
            # Generate signal based on all factors
            if trend in ["bullish", "bullish_weak"]:
                if rsi > 70:
                    signal = "SELL"
                elif rsi < 50:
                    signal = "STRONG BUY"
                else:
                    signal = "BUY"
            elif trend in ["bearish", "bearish_weak"]:
                if rsi < 30:
                    signal = "BUY"
                elif rsi > 50:
                    signal = "STRONG SELL"
                else:
                    signal = "SELL"
            
            print(f"[DEBUG] Signal: {signal} (Confidence: {signal_confidence:.1f})")
            
            # Calculate take profit and stop loss levels based on ATR
            if signal in ["BUY", "STRONG BUY"]:
                # For long positions
                entry_low = nearest_support
                entry_high = current_price
                
                # Use ATR for SL and TP calculations
                sl_distance = 1.5 * atr  # 1.5x ATR for stop loss
                tp1_distance = 2 * atr   # 2x ATR for first target
                tp2_distance = 3 * atr   # 3x ATR for second target
                
                # Calculate actual levels
                sl = entry_low - sl_distance  # Place SL below entry using ATR
                tp1 = entry_high + tp1_distance  # First TP using 2x ATR
                tp2 = entry_high + tp2_distance  # Second TP using 3x ATR
                
                # Validate against support/resistance
                sl = max(sl, nearest_support * 0.95)  # Don't set SL too far below support
                tp1 = min(tp1, nearest_resistance * 1.05)  # Don't set TP1 too far above resistance
                tp2 = min(tp2, nearest_resistance * 1.10)  # Allow TP2 to be slightly higher
                
            elif signal in ["SELL", "STRONG SELL"]:
                # For short positions
                entry_low = current_price
                entry_high = nearest_resistance
                
                # Use ATR for SL and TP calculations
                sl_distance = 1.5 * atr  # 1.5x ATR for stop loss
                tp1_distance = 2 * atr   # 2x ATR for first target
                tp2_distance = 3 * atr   # 3x ATR for second target
                
                # Calculate actual levels
                sl = entry_high + sl_distance  # Place SL above entry using ATR
                tp1 = entry_low - tp1_distance  # First TP using 2x ATR
                tp2 = entry_low - tp2_distance  # Second TP using 3x ATR
                
                # Validate against support/resistance
                sl = min(sl, nearest_resistance * 1.05)  # Don't set SL too far above resistance
                tp1 = max(tp1, nearest_support * 0.95)  # Don't set TP1 too far below support
                tp2 = max(tp2, nearest_support * 0.90)  # Allow TP2 to be slightly lower
                
            else:
                # For neutral positions
                entry_low = current_price * 0.99
                entry_high = current_price * 1.01
                tp1 = current_price
                tp2 = current_price
                sl = current_price
            
            print(f"[DEBUG] Entry Range: ${entry_low:,.2f} - ${entry_high:,.2f}")
            print(f"[DEBUG] TP1: ${tp1:,.2f} (ATR multiplier: 2x)")
            print(f"[DEBUG] TP2: ${tp2:,.2f} (ATR multiplier: 3x)")
            print(f"[DEBUG] SL: ${sl:,.2f} (ATR multiplier: 1.5x)")
            
            # Calculate risk-reward ratio
            if sl != current_price:  # Avoid division by zero
                risk = abs(current_price - sl)
                reward1 = abs(current_price - tp1)
                reward2 = abs(current_price - tp2)
                rrr1 = reward1 / risk if risk > 0 else 0
                rrr2 = reward2 / risk if risk > 0 else 0
                print(f"[DEBUG] Risk-Reward Ratio - TP1: {rrr1:.2f}, TP2: {rrr2:.2f}")
            
            # Calculate risk level based on volatility and confidence
            volatility = "high" if atr > current_price * 0.03 else "medium" if atr > current_price * 0.015 else "low"
            volatility_factor = 1.5 if volatility == "high" else 1.0 if volatility == "medium" else 0.5
            risk_level = min(10, max(1, (volatility_factor * (signal_confidence / 10)) * 10))
            
            # Structure the indicators with key_levels
            indicators[label] = {
                "price": closes[-1],
                "sma7": sma7,
                "sma14": sma14,
                "sma50": sma50,
                "rsi14": rsi,
                "trend": trend,
                "rsi_zone": rsi_zone,
                "volume_trend": volume_trend,
                "signal": signal,
                "signal_confidence": signal_confidence,
                "support": nearest_support,
                "resistance": nearest_resistance,
                "atr": atr,
                "volatility": volatility,
                "risk_level": risk_level,
                "key_levels": {
                    "entry_range": f"${entry_low:,.0f} - ${entry_high:,.0f}",
                    "tp1": tp1,
                    "tp2": tp2,
                    "sl": sl,
                    "rrr1": rrr1 if 'rrr1' in locals() else None,
                    "rrr2": rrr2 if 'rrr2' in locals() else None
                }
            }
            
            # Add individual indicators for easy access
            indicators[f"{label.lower()}_rsi"] = rsi
            indicators[f"{label.lower()}_trend"] = trend
            indicators[f"{label.lower()}_signal"] = signal
            indicators[f"{label.lower()}_signal_confidence"] = signal_confidence
            indicators[f"{label.lower()}_support"] = nearest_support
            indicators[f"{label.lower()}_resistance"] = nearest_resistance
            
        except Exception as e:
            print(f"[ERROR] Technicals {label}: {e}")
            import traceback
            traceback.print_exc()
    
    return indicators

def get_support_resistance_levels():
    url = "https://api.binance.com/api/v3/klines"
    levels = {}
    
    for symbol, label in {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}.items():
        try:
            data = resilient_request(url, {"symbol": symbol, "interval": "1d", "limit": 20})
            if not data:
                continue
                
            highs = [float(k[2]) for k in data[-5:]]
            lows = [float(k[3]) for k in data[-5:]]
            levels[label] = {"support": min(lows), "resistance": max(highs)}
        except Exception as e:
            print(f"[ERROR] Support/Resistance {label}: {e}")
    
    return levels

def get_historical_price_data():
    tickers = ["BTC-USD", "ETH-USD"]
    timeframes = ["1h", "4h", "1d"]
    
    historical_data = {}
    for ticker in tickers:
        ticker_data = {}
        for timeframe in timeframes:
            # Convert timeframe to yfinance interval and period
            interval = timeframe
            if timeframe == "1h":
                period = "2d"  # Get 2 days of hourly data
            elif timeframe == "4h":
                period = "7d"  # Get 7 days of 4-hour data
            else:
                period = "30d"  # Get 30 days of daily data
                
            try:
                data = yf.download(ticker, period=period, interval=interval)
                # Calculate ATR (Average True Range) for volatility
                data['tr1'] = abs(data['High'] - data['Low'])
                data['tr2'] = abs(data['High'] - data['Close'].shift())
                data['tr3'] = abs(data['Low'] - data['Close'].shift())
                data['TR'] = data[['tr1', 'tr2', 'tr3']].max(axis=1)
                data['ATR'] = data['TR'].rolling(14).mean()
                
                # Convert index and Series to lists correctly
                ticker_data[timeframe] = {
                    'timestamps': list(data.index.strftime('%Y-%m-%d %H:%M:%S')),  # Convert datetime index to string list
                    'open': data['Open'].values.tolist(),
                    'high': data['High'].values.tolist(),
                    'low': data['Low'].values.tolist(),
                    'close': data['Close'].values.tolist(),
                    'volume': data['Volume'].values.tolist(),
                    'atr': data['ATR'].values.tolist()
                }
            except Exception as e:
                print(f"[ERROR] Failed to get {timeframe} data for {ticker}: {e}")
                
        historical_data[ticker.split('-')[0]] = ticker_data
    
    return historical_data

# ----------------------------
# 4. Parallel Data Collection
# ----------------------------
def collect_all_data():
    print("[INFO] Collecting market data...")
    
    data_tasks = {
        "crypto": get_crypto_data,
        "futures": get_futures_sentiment,
        "fear_greed": get_fear_greed_index,
        "btc_dominance": get_btc_dominance,
        "market_cap": get_global_market_cap,
        "volumes": get_trading_volumes,
        "technical_indicators": get_technical_indicators,
        "levels": get_support_resistance_levels,
        "historical_data": get_historical_price_data
    }
    
    if config["indicators"].get("include_macroeconomic", True):
        data_tasks.update({
            "m2_supply": get_m2_money_supply,
            "inflation": get_inflation_data,
            "interest_rates": get_interest_rates
        })
    
    if config["indicators"].get("include_stock_indices", True):
        data_tasks["stock_indices"] = get_stock_indices
    
    if config["indicators"].get("include_commodities", True):
        data_tasks["commodities"] = get_commodity_prices
    
    if config["indicators"].get("include_social_metrics", True):
        data_tasks["social_metrics"] = get_crypto_social_metrics
    
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(data_tasks)) as executor:
        future_to_task = {executor.submit(func): task_name for task_name, func in data_tasks.items()}
        
        for future in concurrent.futures.as_completed(future_to_task):
            task_name = future_to_task[future]
            try:
                results[task_name] = future.result()
                print(f"[INFO] Completed: {task_name}")
            except Exception as e:
                print(f"[ERROR] Task {task_name} failed: {e}")
                results[task_name] = None
    
    # Print collected data for verification
    print("\n[INFO] Collected Market Data:")
    essential_data = {
        'crypto': results.get('crypto', {}),
        'btc_dominance': results.get('btc_dominance'),
        'market_cap': results.get('market_cap'),
        'fear_greed': results.get('fear_greed', {}),
        'technical_indicators': results.get('technical_indicators', {}),
        'levels': results.get('levels', {}),
        'futures': {
            'BTC': results.get('futures', {}).get('BTC', {}),
            'ETH': results.get('futures', {}).get('ETH', {})
        }
    }
    
    for key, value in essential_data.items():
        if value is not None:
            print(f"\n{key.upper()}:")
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    if isinstance(subvalue, dict):
                        print(f"  {subkey}:")
                        for k, v in subvalue.items():
                            print(f"    {k}: {v}")
                    else:
                        print(f"  {subkey}: {subvalue}")
            else:
                print(f"  {value}")
    
    return results

# ----------------------------
# 5. Save History
# ----------------------------
def save_today_data(all_data):
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Determine if this is a morning or evening run
    current_hour = datetime.now().hour
    session = "morning" if current_hour < 15 else "evening"
    
    # Use test file if in test mode
    file = config["storage"]["file"]
    if config["test_mode"]["enabled"]:
        file = config["test_mode"]["output_prefix"] + file
        print(f"[TEST] Using test data file: {file}")
    
    crypto = all_data.get("crypto", {})
    futures = all_data.get("futures", {})
    fear_greed = all_data.get("fear_greed", {})
    market_cap_data = all_data.get("market_cap", (None, None))
    volumes = all_data.get("volumes", {})
    technicals = all_data.get("technicals", {})
    
    data = {
        "date": today,
        "session": session,  # Add morning/evening marker
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Add exact timestamp
        "btc_price": crypto.get("btc"),
        "eth_price": crypto.get("eth"),
        "btc_funding": futures.get("btc_funding"),
        "eth_funding": futures.get("eth_funding"),
        "fear_greed": fear_greed.get("index"),
        "btc_dominance": all_data.get("btc_dominance"),
        "market_cap": market_cap_data[0] if market_cap_data[0] else None,
        "btc_volume": volumes.get("btc_volume"),
        "eth_volume": volumes.get("eth_volume"),
        "btc_rsi": technicals.get("btc_rsi"),
        "eth_rsi": technicals.get("eth_rsi"),
        "btc_trend": technicals.get("btc_trend"),
        "eth_trend": technicals.get("eth_trend"),
        "btc_signal": technicals.get("btc_signal"),
        "eth_signal": technicals.get("eth_signal"),
        "btc_signal_confidence": technicals.get("btc_signal_confidence"),
        "eth_signal_confidence": technicals.get("eth_signal_confidence")
    }
    
    if config["indicators"].get("include_macroeconomic", True):
        m2_data = all_data.get("m2_supply", {})
        if m2_data:
            data["m2_supply"] = m2_data.get("m2_supply")
            data["m2_supply_date"] = m2_data.get("m2_date")
        
        inflation_data = all_data.get("inflation", {})
        if inflation_data:
            data["inflation_rate"] = inflation_data.get("inflation_rate")
            data["inflation_date"] = inflation_data.get("inflation_date")
        
        interest_data = all_data.get("interest_rates", {})
        if interest_data:
            data["fed_rate"] = interest_data.get("fed_rate")
            data["t10_yield"] = interest_data.get("t10_yield")
            if "t5_yield" in interest_data:
                data["t5_yield"] = interest_data.get("t5_yield")
            data["rate_date"] = interest_data.get("rate_date")
    
    indices = all_data.get("stock_indices", {})
    if indices:
        for key, value in indices.items():
            if key != "indices_date":
                data[key] = value
    
    commodities = all_data.get("commodities", {})
    if commodities:
        for key, value in commodities.items():
            if key != "commodities_date":
                data[key] = value
    
    social = all_data.get("social_metrics", {})
    if social:
        for key, value in social.items():
            if key != "social_date":
                data[key] = value
    
    df = pd.DataFrame([data])
    
    if os.path.exists(file):
        try:
            old = pd.read_csv(file)
            
            # Handle upgrading older CSV files without session column
            if 'session' not in old.columns:
                print("[INFO] Upgrading CSV format to include session data")
                old['session'] = 'all-day'  # Mark existing entries as all-day
                old['timestamp'] = old['date'] + ' 12:00:00'  # Add default timestamp
                
            # Check if we already have an entry for this date and session
            existing_entry = old[(old['date'] == today) & (old['session'] == session)]
            if len(existing_entry) > 0:
                print(f"[INFO] Updating data for {today} ({session})")
                old = old[~((old['date'] == today) & (old['session'] == session))]
            
            for col in df.columns:
                if col not in old.columns:
                    old[col] = None
            
            for col in old.columns:
                if col not in df.columns:
                    df[col] = None
            
            # Make sure columns are in the same order
            common_cols = [col for col in old.columns if col in df.columns]
            df = df[common_cols]
            old = old[common_cols]
            
            df = pd.concat([old, df], ignore_index=True)
        except Exception as e:
            print(f"[ERROR] Reading existing CSV: {e}")
            print("[INFO] Creating a new CSV file with the current data")
            # If error occurs, just use the new data and start fresh
            pass    
    try:
        df.to_csv(file, index=False)
        print(f"[INFO] Data saved to {file} for {today} ({session})")
    except Exception as e:
        print(f"[ERROR] Saving CSV: {e}")

# ----------------------------
# 6. Prediction Tracking
# ----------------------------
def save_prediction(prediction, data):
    """Save AI prediction with timestamp and current data"""
    prediction_file = "prediction_history.json"
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Determine if this is a morning or evening run
    current_hour = datetime.now().hour
    session = "morning" if current_hour < 15 else "evening"
    
    # Create prediction record with JSON-serializable values
    # Convert numpy/pandas types to native Python types
    prediction_record = {
        "date": today,
        "session": session,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prediction": prediction,
        "btc_price": float(data.get("btc_price")) if pd.notna(data.get("btc_price")) else None,
        "eth_price": float(data.get("eth_price")) if pd.notna(data.get("eth_price")) else None,
        "btc_rsi": float(data.get("btc_rsi")) if pd.notna(data.get("btc_rsi")) else None,
        "eth_rsi": float(data.get("eth_rsi")) if pd.notna(data.get("eth_rsi")) else None,
        "fear_greed": int(data.get("fear_greed")) if pd.notna(data.get("fear_greed")) else None,
        "market_cap": float(data.get("market_cap")) if pd.notna(data.get("market_cap")) else None
    }
    
    # Load existing predictions
    predictions = []
    if os.path.exists(prediction_file):
        try:
            with open(prediction_file, "r") as f:
                predictions = json.load(f)
        except Exception as e:
            print(f"[ERROR] Loading prediction history: {e}")
    
    # Add new prediction
    predictions.append(prediction_record)
    
    # Save predictions
    try:
        with open(prediction_file, "w") as f:
            json.dump(predictions, f, indent=4)
        print(f"[INFO] Prediction saved to {prediction_file} for {today} ({session})")
    except Exception as e:
        print(f"[ERROR] Saving prediction: {e}")

def save_detailed_prediction(prediction_data, market_data):
    """Save structured prediction with detailed metrics and risk analysis"""
    # Use test file if in test mode
    prediction_file = "detailed_predictions.json"
    if config["test_mode"]["enabled"]:
        prediction_file = config["test_mode"]["output_prefix"] + prediction_file
        print(f"[TEST] Using test prediction file: {prediction_file}")
    
    today = datetime.now().strftime("%Y-%m-%d")
    current_hour = datetime.now().hour
    session = "morning" if current_hour < 15 else "evening"
    
    # Get ML predictions if enabled
    ml_predictions = {}
    if config["ml"]["enabled"]:
        try:
            ml_predictions = ml_enhancer.predict(market_data)
        except Exception as e:
            print(f"[ERROR] ML prediction failed: {e}")
    
    # Get risk analysis if enabled
    risk_analysis = {}
    if config["risk"]["enabled"] and ml_predictions:
        try:
            # Update risk metrics
            prediction_confidence = ml_predictions.get('direction', {}).get('confidence', 0.5)
            risk_manager.update_risk_metrics(market_data, prediction_confidence)
            
            # Calculate position size
            position_size = risk_manager.calculate_position_size(
                config["risk"]["account_size"],
                config["risk"]["max_risk_per_trade"]
            )
            
            # Calculate stop loss and take profit levels
            if 'btc_price' in market_data:
                entry_price = market_data['btc_price']
                direction = 'long' if ml_predictions.get('direction', {}).get('prediction') == 'rally' else 'short'
                
                stop_loss = risk_manager.calculate_stop_loss(entry_price, direction)
                take_profit = risk_manager.calculate_take_profit(
                    entry_price,
                    direction,
                    config["risk"]["risk_reward_ratio"]
                )
            
            risk_analysis = risk_manager.get_risk_summary()
        except Exception as e:
            print(f"[ERROR] Risk analysis failed: {e}")
    
    # Extract fear & greed index from dictionary
    fear_greed_data = market_data.get("fear_greed", {})
    fear_greed_index = fear_greed_data.get("index") if isinstance(fear_greed_data, dict) else fear_greed_data
    
    # Create a structured prediction record
    prediction_record = {
        "date": today,
        "session": session,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_data": {
            "btc_price": float(market_data.get("btc_price")) if pd.notna(market_data.get("btc_price")) else None,
            "eth_price": float(market_data.get("eth_price")) if pd.notna(market_data.get("eth_price")) else None,
            "btc_rsi": float(market_data.get("btc_rsi")) if pd.notna(market_data.get("btc_rsi")) else None,
            "eth_rsi": float(market_data.get("eth_rsi")) if pd.notna(market_data.get("eth_rsi")) else None,
            "fear_greed": int(fear_greed_index) if pd.notna(fear_greed_index) else None,
        },
        "predictions": {
            "ai_prediction": prediction_data,
            "ml_predictions": ml_predictions
        },
        "risk_analysis": risk_analysis,
        "validation_points": [],
        "final_accuracy": None
    }
    
    # Load existing predictions
    predictions = []
    if os.path.exists(prediction_file):
        try:
            with open(prediction_file, "r") as f:
                predictions = json.load(f)
        except Exception as e:
            print(f"[ERROR] Loading detailed prediction history: {e}")
    
    # Add new prediction
    predictions.append(prediction_record)
    
    # Save predictions
    try:
        with open(prediction_file, "w") as f:
            json.dump(predictions, f, indent=4)
        print(f"[INFO] Detailed prediction saved to {prediction_file} for {today} ({session})")
    except Exception as e:
        print(f"[ERROR] Saving detailed prediction: {e}")

def get_prediction_accuracy():
    """Compare previous predictions with actual outcomes"""
    prediction_file = "prediction_history.json"
    price_file = config["storage"]["file"]
    
    # Check if required files exist
    if not os.path.exists(price_file):
        return "No historical price data available for comparison."
    
    if not os.path.exists(prediction_file):
        return "No previous predictions available for comparison yet."
    
    try:
        # Load predictions - handle potential file corruption
        try:
            with open(prediction_file, "r") as f:
                predictions = json.load(f)
        except json.JSONDecodeError:
            print("[WARN] Prediction history file is corrupted. Creating a new one.")
            with open(prediction_file, "w") as f:
                json.dump([], f)
            return "Prediction history was reset due to file corruption. No previous predictions available."
        
        if not predictions or not isinstance(predictions, list):
            return "No valid previous predictions available yet."
        
        # Load price history
        df = pd.read_csv(price_file)
        
        # Find predictions old enough for comparison
        today = datetime.now().strftime("%Y-%m-%d")
        current_hour = datetime.now().hour
        current_session = "morning" if current_hour < 15 else "evening"
        
        results = []
        
        for pred in predictions:
            pred_date = pred["date"]
            pred_session = pred.get("session", "unknown")
            
            # Skip current session's predictions (too recent)
            if pred_date == today and pred_session == current_session:
                continue
                
            # For morning predictions, compare with evening data
            if pred_date == today and pred_session == "morning" and current_session == "evening":
                current_data = df[(df['date'] == today) & (df['session'] == "evening")]
                if len(current_data) > 0:
                    current_row = current_data.iloc[0]
                    
                    pred_btc = pred["btc_price"]
                    actual_btc = current_row["btc_price"]
                    
                    direction = "UNKNOWN"
                    if pred_btc is not None and actual_btc is not None:
                        if "rally" in pred["prediction"].lower() and actual_btc > pred_btc:
                            direction = "CORRECT"
                        elif "dip" in pred["prediction"].lower() and actual_btc < pred_btc:
                            direction = "CORRECT"
                        elif "stagnation" in pred["prediction"].lower() and abs(actual_btc - pred_btc) / pred_btc < 0.01:
                            direction = "CORRECT"
                        else:
                            direction = "INCORRECT"
                    
                    results.append({
                        "prediction_date": f"{pred_date} ({pred_session})",
                        "prediction_summary": pred["prediction"][:100] + "..." if pred["prediction"] and len(pred["prediction"]) > 100 else pred["prediction"],
                        "btc_at_prediction": pred_btc,
                        "btc_actual": actual_btc,
                        "direction": direction,
                        "timeframe": "12-hour (AM to PM)"
                    })
            
            # For evening predictions, compare with next morning data
            elif pred_date == today and pred_session == "evening":
                next_morning = df[(df['date'] > pred_date) | 
                                ((df['date'] == pred_date) & (df['session'] == "morning"))].head(1)
                if len(next_morning) > 0:
                    next_row = next_morning.iloc[0]
                    
                    pred_btc = pred["btc_price"]
                    actual_btc = next_row["btc_price"]
                    
                    direction = "UNKNOWN"
                    if pred_btc is not None and actual_btc is not None:
                        if "rally" in pred["prediction"].lower() and actual_btc > pred_btc:
                            direction = "CORRECT"
                        elif "dip" in pred["prediction"].lower() and actual_btc < pred_btc:
                            direction = "CORRECT"
                        elif "stagnation" in pred["prediction"].lower() and abs(actual_btc - pred_btc) / pred_btc < 0.01:
                            direction = "CORRECT"
                        else:
                            direction = "INCORRECT"
                    
                    results.append({
                        "prediction_date": f"{pred_date} ({pred_session})",
                        "prediction_summary": pred["prediction"][:100] + "..." if pred["prediction"] and len(pred["prediction"]) > 100 else pred["prediction"],
                        "btc_at_prediction": pred_btc,
                        "btc_actual": actual_btc,
                        "direction": direction,
                        "timeframe": "12-hour (PM to AM)"
                    })
        
        if not results:
            return "No predictions old enough for comparison yet."
            
        # Create a readable summary
        output = "PREVIOUS PREDICTION ACCURACY:\n\n"
        for result in results:
            output += f"Date: {result['prediction_date']}\n"
            output += f"Prediction: {result['prediction_summary']}\n"
            output += f"Timeframe: {result['timeframe']}\n"
            
            if result['btc_at_prediction'] is not None:
                output += f"BTC at prediction: ${result['btc_at_prediction']:.2f}\n"
            
            if result['btc_actual'] is not None and result['btc_at_prediction'] is not None:
                change = ((result['btc_actual'] - result['btc_at_prediction']) / result['btc_at_prediction']) * 100
                output += f"BTC actual: ${result['btc_actual']:.2f} ({change:.2f}%)\n"
                
            output += f"Directional Accuracy: {result['direction']}\n\n"
            
        return output
            
    except Exception as e:
        print(f"[ERROR] Analyzing prediction accuracy: {e}")
        try:
            with open(prediction_file, "w") as f:
                json.dump([], f)
            print("[INFO] Reset prediction history file due to error.")
        except:
            pass
        return "Prediction history was reset due to an error. No previous predictions available."

# ----------------------------
# 6. GPT Market Insight
# ----------------------------
def ask_ai(prompt):
    # First check for environment variable, then fallback to config file
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = config["api_keys"]["openai"]
    
    if not api_key or api_key == "YOUR_OPENAI_API_KEY":
        return "AI summary unavailable. Please add your OpenAI API key to config.json or set the OPENAI_API_KEY environment variable."
    
    # Determine if this is a morning or evening prediction
    current_hour = datetime.now().hour
    session = "morning" if current_hour < 15 else "evening"
    timeframe = "next 12 hours" if session == "morning" else "overnight and early morning"
    
    # Enhance the prompt with timeframe context
    enhanced_prompt = f"""Based on the following market data, provide a detailed analysis and prediction for the {timeframe}.
Focus on short-term price movements and key levels that might be reached within this timeframe.
Include specific entry points, take profit targets, and stop loss levels that are realistically achievable within {timeframe}.

Market Data:
{prompt}

Please structure your response as follows:
1. Market Analysis: Brief overview of current market conditions
2. BTC Prediction:
   - Direction (bullish/bearish/sideways)
   - Entry Price Range
   - Take Profit Targets (TP1, TP2, TP3)
   - Stop Loss Level
3. ETH Prediction (if significant movement expected)
4. Risk Assessment
5. Key Events/Levels to Watch

Keep all price targets within a realistic range for the {timeframe} timeframe."""
        
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": enhanced_prompt}],
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] GPT call failed: {e}")
        return f"AI summary unavailable: {str(e)}"

def train_ml_models():
    """Train machine learning models on historical data"""
    if not config["ml"]["enabled"]:
        return
    
    try:
        # Create model directory if it doesn't exist
        model_dir = config["ml"]["model_directory"]
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
            print(f"[INFO] Created model directory: {model_dir}")
        
        # Load historical data
        df = pd.read_csv(config["storage"]["file"])
        
        # Load prediction history
        prediction_file = "detailed_predictions.json"
        if os.path.exists(prediction_file):
            with open(prediction_file, "r") as f:
                prediction_history = json.load(f)
        else:
            prediction_history = []
            print("[WARN] No prediction history found. Starting with empty history.")
        
        # Train models
        ml_enhancer.train_models(df, prediction_history)
        
        # Save trained models
        ml_enhancer.save_models(model_dir)
        
        # Save training metrics
        metrics = {
            'last_training': datetime.now().isoformat(),
            'data_points': len(df),
            'prediction_history_size': len(prediction_history)
        }
        with open(f"{model_dir}/model_metrics.json", "w") as f:
            json.dump(metrics, f, indent=4)
        
        print("[INFO] ML models trained and saved successfully")
    except Exception as e:
        print(f"[ERROR] Training ML models: {e}")
        import traceback
        traceback.print_exc()

def should_retrain_models():
    """Check if models should be retrained based on config settings"""
    if not config["ml"]["enabled"]:
        return False
    
    model_dir = config["ml"]["model_directory"]
    if not os.path.exists(model_dir):
        return True
    
    # Check if any model files are missing
    required_files = ['direction_model.joblib', 'price_model.joblib', 'scaler.joblib']
    if not all(os.path.exists(f"{model_dir}/{f}") for f in required_files):
        return True
    
    # Check last training time
    try:
        with open(f"{model_dir}/model_metrics.json", "r") as f:
            metrics = json.load(f)
            last_training = datetime.fromisoformat(metrics.get('last_training', '2000-01-01'))
            days_since_training = (datetime.now() - last_training).days
            return days_since_training >= config["ml"]["retrain_interval_days"]
    except Exception:
        return True

def calculate_percentage(current, target):
    """Calculate percentage change between current and target price"""
    if not current or not target or current == 0:
        return 0
    return round(abs((target - current) / current * 100), 1)  # Round to 1 decimal place

def format_telegram_message(indicators):
    """Format market analysis message for Telegram"""
    try:
        # Get current time
        current_hour = datetime.now().hour
        
        # Determine timeframe based on time of day
        if 5 <= current_hour < 12:  # Morning
            timeframe = "next 12 hours"
        elif 12 <= current_hour < 17:  # Afternoon
            timeframe = "next 12 hours"
        else:  # Evening
            timeframe = "overnight and early morning"
        
        # Get BTC and ETH data
        btc_data = indicators.get("BTC", {})
        eth_data = indicators.get("ETH", {})
        
        # Get current prices
        btc_price = btc_data.get("price", 0)
        eth_price = eth_data.get("price", 0)
        
        # Get signals and confidence
        btc_signal = btc_data.get("signal", "NEUTRAL")
        eth_signal = eth_data.get("signal", "NEUTRAL")
        btc_confidence = btc_data.get("signal_confidence", 0)
        eth_confidence = eth_data.get("signal_confidence", 0)
        
        # Get support and resistance levels
        btc_support = btc_data.get("support", 0)
        btc_resistance = btc_data.get("resistance", 0)
        eth_support = eth_data.get("support", 0)
        eth_resistance = eth_data.get("resistance", 0)
        
        # Get key levels
        btc_levels = btc_data.get("key_levels", {})
        eth_levels = eth_data.get("key_levels", {})
        
        # Get risk levels
        btc_risk = btc_data.get("risk_level", 0)
        eth_risk = eth_data.get("risk_level", 0)
        
        # Calculate overall market trend
        if btc_signal == eth_signal:
            market_trend = btc_signal
        else:
            # If signals differ, use the one with higher confidence
            market_trend = btc_signal if btc_confidence > eth_confidence else eth_signal
        
        # Format the message with improved visual structure
        message = "ðŸ” *CRYPTO MARKET ANALYSIS*\n\n"
        
        # Overview section with emoji
        message += "ðŸ“Š *OVERVIEW*\n"
        message += f"â€¢ Signal: {market_trend}\n"
        message += f"â€¢ Timeframe: {timeframe}\n\n"
        
        # BTC Analysis with clear sections
        message += "â‚¿ *BTC ANALYSIS*\n"
        message += "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        message += f"ðŸ’° Current Price: `${btc_price:,.0f}`\n"
        message += f"ðŸ“ˆ Resistance: `${btc_resistance:,.0f}`\n"
        message += f"ðŸ“‰ Support: `${btc_support:,.0f}`\n\n"
        
        # Position recommendation for BTC
        message += f"ðŸŽ¯ *{btc_signal} POSITION*\n"
        message += f"â€¢ Entry: {btc_levels.get('entry_range', 'N/A')}\n"
        message += f"â€¢ TP1: `${btc_levels.get('tp1', 0):,.0f}` ({calculate_percentage(btc_price, btc_levels.get('tp1', 0))}%) [RR: {btc_levels.get('rrr1', 0):.1f}]\n"
        message += f"â€¢ TP2: `${btc_levels.get('tp2', 0):,.0f}` ({calculate_percentage(btc_price, btc_levels.get('tp2', 0))}%) [RR: {btc_levels.get('rrr2', 0):.1f}]\n"
        message += f"â€¢ SL: `${btc_levels.get('sl', 0):,.0f}` ({calculate_percentage(btc_price, btc_levels.get('sl', 0))}%)\n"
        message += f"â€¢ ATR: `${btc_data.get('atr', 0):,.0f}`\n"
        message += f"â€¢ Confidence: {btc_confidence:.1f}/10\n\n"
        
        # ETH Analysis with clear sections
        message += "Îž *ETH ANALYSIS*\n"
        message += "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        message += f"ðŸ’° Current Price: `${eth_price:,.0f}`\n"
        message += f"ðŸ“ˆ Resistance: `${eth_resistance:,.0f}`\n"
        message += f"ðŸ“‰ Support: `${eth_support:,.0f}`\n\n"
        
        # Position recommendation for ETH
        message += f"ðŸŽ¯ *{eth_signal} POSITION*\n"
        message += f"â€¢ Entry: {eth_levels.get('entry_range', 'N/A')}\n"
        message += f"â€¢ TP1: `${eth_levels.get('tp1', 0):,.0f}` ({calculate_percentage(eth_price, eth_levels.get('tp1', 0))}%) [RR: {eth_levels.get('rrr1', 0):.1f}]\n"
        message += f"â€¢ TP2: `${eth_levels.get('tp2', 0):,.0f}` ({calculate_percentage(eth_price, eth_levels.get('tp2', 0))}%) [RR: {eth_levels.get('rrr2', 0):.1f}]\n"
        message += f"â€¢ SL: `${eth_levels.get('sl', 0):,.0f}` ({calculate_percentage(eth_price, eth_levels.get('sl', 0))}%)\n"
        message += f"â€¢ ATR: `${eth_data.get('atr', 0):,.0f}`\n"
        message += f"â€¢ Confidence: {eth_confidence:.1f}/10\n\n"
        
        # Risk Assessment with clear section
        message += "âš ï¸ *RISK ASSESSMENT*\n"
        message += "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        message += f"â€¢ BTC Risk Level: {btc_risk:.1f}/10\n"
        message += f"â€¢ ETH Risk Level: {eth_risk:.1f}/10\n"
        
        return message
        
    except Exception as e:
        print(f"[ERROR] Message formatting: {e}")
        import traceback
        traceback.print_exc()
        return "Error formatting message"

def main():
    """Main execution function"""
    global config  # Make sure we're using the global config
    
    # Log times in different timezones
    server_time = datetime.now()
    utc_time = datetime.now(timezone.utc)
    print(f"[INFO] UTC time: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Server time: {server_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Server timezone: {time.tzname[0]}")
    print(f"[INFO] Expected Vietnam time: {(utc_time + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Handle test mode configuration
    is_test_mode = config["test_mode"]["enabled"]
    if is_test_mode:
        print("[TEST] Running in test mode")
        print("[TEST] Using test Telegram bot")
        # Store original production settings
        original_bot_token = config["telegram"]["bot_token"]
        original_chat_id = config["telegram"]["chat_id"]
        # Switch to test settings
        config["telegram"]["bot_token"] = config["telegram"]["test"]["bot_token"]
        config["telegram"]["chat_id"] = config["telegram"]["test"]["chat_id"]
        config["telegram"]["enabled"] = True  # Enable Telegram in test mode
        print(f"[TEST] Using test bot token: {config['telegram']['bot_token'][:10]}...")
        print(f"[TEST] Using test chat ID: {config['telegram']['chat_id']}")
    
    # Check if models need retraining
    if should_retrain_models():
        print("[INFO] Retraining ML models...")
        train_ml_models()
    
    # Collect market data
    print("[INFO] Collecting market data...")
    market_data = collect_all_data()
    
    # Get AI prediction
    print("\n[INFO] Getting AI prediction...")
    prediction = ask_ai(market_data)
    
    # Save detailed prediction with ML and risk analysis
    print("\n[INFO] Saving detailed prediction...")
    save_detailed_prediction(prediction, market_data)
    
    # Send Telegram notification if configured
    if config.get("telegram", {}).get("enabled"):
        print("\n[INFO] Sending Telegram message...")
        message = format_telegram_message(market_data["technical_indicators"])
        # Create a new instance of the Telegram bot with current settings
        bot = TelegramBot(
            bot_token=config["telegram"]["bot_token"],
            chat_id=config["telegram"]["chat_id"]
        )
        bot.send_message(message)
        print("[INFO] Telegram message sent successfully")
        
        # Restore original production settings if in test mode
        if is_test_mode:
            config["telegram"]["bot_token"] = original_bot_token
            config["telegram"]["chat_id"] = original_chat_id
            print("[TEST] Restored production Telegram settings")
    else:
        print("[WARN] Telegram notifications are disabled")

if __name__ == "__main__":
    # Check for test mode argument
    import sys
    config = load_config()  # Load config first
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        config["test_mode"]["enabled"] = True
        print("[TEST] Test mode enabled")
    main()
