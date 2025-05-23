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
from professional_analysis import ProfessionalTraderAnalysis
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
            "openai": "YOUR_OPENAI_API_KEY",
            "fred": "YOUR_FRED_API_KEY",
            "alphavantage": "YOUR_ALPHAVANTAGE_API_KEY"
        },
        "telegram": {
            "enabled": True,
            "bot_token": "",
            "chat_id": "",
            "test": {
                "enabled": True,
                "bot_token": "",
                "chat_id": ""
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
    
    # Try to load existing config (non-sensitive settings only)
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                existing_config = json.load(f)
                # Update config with existing values while preserving structure
                # BUT exclude sensitive data that should come from environment variables
                for key, value in existing_config.items():
                    if key in config:
                        if key == "api_keys" or key == "telegram":
                            # Skip sensitive data - don't override with config.json values
                            continue
                        elif isinstance(value, dict) and isinstance(config[key], dict):
                            config[key].update(value)
                        else:
                            config[key] = value
        except Exception as e:
            print(f"[ERROR] Loading config: {e}")
    
    # NOW load sensitive data from environment variables (this ensures they're never overwritten)
    config["api_keys"]["openai"] = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
    config["api_keys"]["fred"] = os.getenv("FRED_API_KEY", "YOUR_FRED_API_KEY")
    config["api_keys"]["alphavantage"] = os.getenv("ALPHAVANTAGE_API_KEY", "YOUR_ALPHAVANTAGE_API_KEY")
    
    config["telegram"]["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "")
    config["telegram"]["chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "")
    config["telegram"]["test"]["bot_token"] = os.getenv("TEST_TELEGRAM_BOT_TOKEN", "")
    config["telegram"]["test"]["chat_id"] = os.getenv("TEST_TELEGRAM_CHAT_ID", "")
    
    # Create a safe version of config for saving (without sensitive data)
    safe_config = config.copy()
    safe_config["api_keys"] = {
        "openai": "YOUR_OPENAI_API_KEY",
        "fred": "YOUR_FRED_API_KEY",
        "alphavantage": "YOUR_ALPHAVANTAGE_API_KEY"
    }
    safe_config["telegram"] = {
        "enabled": config["telegram"]["enabled"],
        "bot_token": "YOUR_BOT_TOKEN",
        "chat_id": "YOUR_CHAT_ID",
        "test": {
            "enabled": config["telegram"]["test"]["enabled"],
            "bot_token": "YOUR_TEST_BOT_TOKEN",
            "chat_id": "YOUR_TEST_CHAT_ID"
        }
    }
    
    # Save the safe config (without sensitive data)
    try:
        with open("config.json", "w") as f:
            json.dump(safe_config, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Saving config: {e}")
    
    print(f"[INFO] Loaded config - Using environment variables for sensitive data")
    print(f"[INFO] Telegram enabled: {config['telegram']['enabled']}")
    print(f"[INFO] Test bot configured: {'Yes' if config['telegram']['test']['bot_token'] else 'No'}")
    
    return config

config = load_config()

# Initialize ML and Risk Management components
ml_enhancer = PredictionEnhancer()
risk_manager = RiskManager()
professional_trader = ProfessionalTraderAnalysis()

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
            
            # --- Enhanced TP/SL Logic ---
            # Even tighter settings for higher leverage
            leverage = 13.5  # midpoint of 12-15x
            risk_per_trade = 0.03  # still 3%
            strategy = "scalp"  # tightest stops/targets

            # Determine trend bias
            trend_bias = "with" if (
                (signal in ["BUY", "STRONG BUY"] and trend.startswith("bull")) or
                (signal in ["SELL", "STRONG SELL"] and trend.startswith("bear"))
            ) else "against"

            # Set RRR based on trend bias
            rrr = 3 if trend_bias == "with" else 1.5

            # Adjust ATR multipliers for leverage and strategy
            if leverage >= 7:
                sl_atr_mult = 1.0
                tp_atr_mult = 2.0
            else:
                sl_atr_mult = 1.5
                tp_atr_mult = 3.0
            if strategy == "scalp":
                sl_atr_mult *= 0.7
                tp_atr_mult *= 0.7
            elif strategy == "swing":
                sl_atr_mult *= 1.2
                tp_atr_mult *= 1.2

            # Calculate SL/TP using ATR, RRR, and support/resistance
            if signal in ["BUY", "STRONG BUY"]:
                entry_low = nearest_support
                entry_high = current_price
                # SL: just below support, but not tighter than ATR-based
                sl = min(entry_low - sl_atr_mult * atr, nearest_support * 0.98)
                # TP: RRR * risk, but capped at resistance
                risk = abs(entry_high - sl)
                tp1 = min(entry_high + rrr * risk, nearest_resistance * 1.01)
                tp2 = min(entry_high + (rrr+1) * risk, nearest_resistance * 1.02)
            elif signal in ["SELL", "STRONG SELL"]:
                entry_low = current_price
                entry_high = nearest_resistance
                # SL: just above resistance, but not tighter than ATR-based
                sl = max(entry_high + sl_atr_mult * atr, nearest_resistance * 1.005)
                # TP: RRR * risk, but capped at support
                risk = abs(entry_low - sl)
                tp1 = max(entry_low - rrr * risk, nearest_support * 0.99)
                tp2 = max(entry_low - (rrr+1) * risk, nearest_support * 0.98)
            else:
                entry_low = current_price * 0.99
                entry_high = current_price * 1.01
                tp1 = current_price
                tp2 = current_price
                sl = current_price

            print(f"[DEBUG] Entry Range: ${entry_low:,.2f} - ${entry_high:,.2f}")
            print(f"[DEBUG] TP1: ${tp1:,.2f} (RRR: {rrr}x)")
            print(f"[DEBUG] TP2: ${tp2:,.2f} (RRR: {rrr+1}x)")
            print(f"[DEBUG] SL: ${sl:,.2f} (ATR/Support/Resistance based)")

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
    
    # Get professional trader analysis
    pro_analysis = {}
    try:
        pro_analysis = professional_trader.generate_probabilistic_forecast(market_data)
        print(f"[INFO] Professional analysis completed: {pro_analysis.get('primary_scenario', 'Unknown')} scenario")
    except Exception as e:
        print(f"[ERROR] Professional analysis failed: {e}")
    
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
            "professional_analysis": pro_analysis,
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
def ask_ai(market_data):
    # First check for environment variable, then fallback to config file
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = config["api_keys"]["openai"]
    
    if not api_key or api_key == "YOUR_OPENAI_API_KEY":
        return "AI summary unavailable. Please add your OpenAI API key to config.json or set the OPENAI_API_KEY environment variable."
    
    # Generate professional trader analysis
    print("\n[INFO] Running professional trader analysis...")
    pro_analysis = professional_trader.generate_probabilistic_forecast(market_data)
    
    if "error" in pro_analysis:
        return f"Professional analysis unavailable: {pro_analysis['error']}"
    
    # Determine if this is a morning or evening prediction
    current_hour = datetime.now().hour
    session = "morning" if current_hour < 15 else "evening"
    timeframe = "next 12 hours" if session == "morning" else "overnight and early morning"
    
    # Create detailed market context for AI
    btc_data = market_data.get('technical_indicators', {}).get('BTC', {})
    fear_greed = market_data.get('fear_greed', {})
    futures = market_data.get('futures', {}).get('BTC', {})
    
    # Enhanced prompt with professional analysis
    enhanced_prompt = f"""You are a professional cryptocurrency trader with 10+ years of experience. Analyze the following comprehensive market data and provide a detailed 12-hour forecast for BTC.

=== PROFESSIONAL ANALYSIS SUMMARY ===
Primary Scenario: {pro_analysis['primary_scenario'].upper()} ({pro_analysis['confidence_level']} confidence)
Bullish Probability: {pro_analysis['bullish_probability']}%
Bearish Probability: {pro_analysis['bearish_probability']}%

Current Price: ${pro_analysis['price_targets']['current']:,.0f}
Target 1: ${pro_analysis['price_targets']['target_1']:,.0f}
Target 2: ${pro_analysis['price_targets']['target_2']:,.0f}
Stop Loss: ${pro_analysis['price_targets']['stop_loss']:,.0f}
Expected Move: ${pro_analysis['price_targets']['expected_move']:,.0f}

=== COMPONENT ANALYSIS ===
Price Action Score: {pro_analysis['component_scores']['price_action']:.2f}
Volume Flow Score: {pro_analysis['component_scores']['volume_flow']:.2f}
Volatility Score: {pro_analysis['component_scores']['volatility']:.2f}
Momentum Score: {pro_analysis['component_scores']['momentum']:.2f}
Funding/Sentiment Score: {pro_analysis['component_scores']['funding_sentiment']:.2f}
Macro Context Score: {pro_analysis['component_scores']['macro_context']:.2f}

Strongest Signal: {pro_analysis['key_factors']['strongest_signal'][0]} ({pro_analysis['key_factors']['strongest_signal'][1]:.2f})
Volatility Regime: {pro_analysis['risk_assessment']['volatility_regime']}

=== DETAILED MARKET DATA ===
BTC Price: ${btc_data.get('price', 0):,.0f}
Support: ${btc_data.get('support', 0):,.0f}
Resistance: ${btc_data.get('resistance', 0):,.0f}
RSI: {btc_data.get('rsi14', 0):.1f}
Trend: {btc_data.get('trend', 'unknown')}
ATR: ${btc_data.get('atr', 0):,.0f}

Funding Rate: {futures.get('funding_rate', 0)*100:.3f}%
Open Interest: ${futures.get('open_interest', 0):,.0f}
Long/Short Ratio: {futures.get('long_ratio', 0):.2f}/{futures.get('short_ratio', 0):.2f}

Fear & Greed Index: {fear_greed.get('index', 50) if isinstance(fear_greed, dict) else 50}
BTC Dominance: {market_data.get('btc_dominance', 0):.1f}%

=== YOUR TASK ===
As a professional trader, provide your analysis for the {timeframe} in this structure:

**EXECUTIVE SUMMARY**
- Primary thesis and confidence level
- Key risk factors to monitor

**TECHNICAL ANALYSIS**
- Market structure assessment
- Key levels and price action
- Volume analysis

**SENTIMENT & POSITIONING**
- Funding rate implications
- Fear/greed assessment
- Crowd positioning

**TRADING PLAN**
- Entry strategy and levels
- Take profit targets with rationale
- Stop loss placement
- Position sizing recommendation
- Risk/reward analysis

**SCENARIO PLANNING**
- Primary scenario (probability)
- Alternative scenario (probability)
- Invalidation levels

Keep your analysis concise, professional, and actionable. Focus on the highest probability outcomes based on the data convergence."""
        
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": enhanced_prompt}],
            temperature=0.3,  # Lower temperature for more focused analysis
            max_tokens=1500   # Allow for detailed response
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

def calculate_trading_confidence(price, support, resistance, rsi, trend, signal, volume_trend, atr, funding_rate=None, fear_greed=None):
    """Calculate trading confidence based on confluence scoring system"""
    confidence_score = 0
    max_score = 8
    
    # 1. Trend Bias (Uptrend on 1H & 4H timeframes)
    if trend and trend.lower() in ['bullish', 'bearish']:
        if (signal in ['BUY', 'STRONG BUY'] and 'bullish' in trend.lower()) or \
           (signal in ['SELL', 'STRONG SELL'] and 'bearish' in trend.lower()):
            confidence_score += 1
    
    # 2. Support/Resistance (Entry near major S/R levels)
    if support and resistance and price:
        # Check if price is near support (for buys) or resistance (for sells)
        support_distance = abs(price - support) / price
        resistance_distance = abs(price - resistance) / price
        
        if signal in ['BUY', 'STRONG BUY'] and support_distance < 0.02:  # Within 2% of support
            confidence_score += 1
        elif signal in ['SELL', 'STRONG SELL'] and resistance_distance < 0.02:  # Within 2% of resistance
            confidence_score += 1
    
    # 3. RSI (Bullish divergence/momentum vs oversold/overbought)
    if rsi:
        if signal in ['BUY', 'STRONG BUY'] and (rsi < 40 or (rsi < 60 and rsi > 40)):  # Oversold or neutral-bullish
            confidence_score += 1
        elif signal in ['SELL', 'STRONG SELL'] and (rsi > 60 or (rsi > 40 and rsi < 70)):  # Overbought or neutral-bearish
            confidence_score += 1
    
    # 4. Volume (Increasing on breakout)
    if volume_trend:
        if volume_trend.lower() == 'increasing':
            confidence_score += 1
    
    # 5. Funding Rate (Neutral or opposite crowd bias)
    if funding_rate is not None:
        # Contrarian approach: negative funding (shorts paying) supports long signals
        if signal in ['BUY', 'STRONG BUY'] and funding_rate < 0:
            confidence_score += 1
        elif signal in ['SELL', 'STRONG SELL'] and funding_rate > 0.01:  # High positive funding
            confidence_score += 1
    
    # 6. Volatility/ATR (Enough room to TP before SL zone)
    if atr and price and support and resistance:
        price_range = resistance - support
        if atr < price_range * 0.3:  # ATR is reasonable compared to S/R range
            confidence_score += 1
    
    # 7. Sentiment (Low retail euphoria for contrarian plays)
    if fear_greed is not None:
        if signal in ['BUY', 'STRONG BUY'] and fear_greed < 40:  # Fear supports buying
            confidence_score += 1
        elif signal in ['SELL', 'STRONG SELL'] and fear_greed > 70:  # Greed supports selling
            confidence_score += 1
    
    # 8. Price Action (Clean breakout/pattern)
    if price and support and resistance:
        # Check for clean position relative to S/R
        if signal in ['BUY', 'STRONG BUY'] and price > support * 1.005:  # Above support
            confidence_score += 1
        elif signal in ['SELL', 'STRONG SELL'] and price < resistance * 0.995:  # Below resistance
            confidence_score += 1
    
    # Normalize to percentage
    confidence_percentage = (confidence_score / max_score) * 100
    
    # Determine confidence level and guidance
    if confidence_percentage >= 70:
        level = "HIGH"
        guidance = "Full position, standard TP/SL"
    elif confidence_percentage >= 50:
        level = "MEDIUM" 
        guidance = "Partial position, tight management"
    else:
        level = "LOW"
        guidance = "Skip or scalp with tight stops"
    
    return {
        'score': confidence_score,
        'max_score': max_score,
        'percentage': confidence_percentage,
        'level': level,
        'guidance': guidance
    }

def format_telegram_message(indicators, pro_analysis=None):
    """Format market analysis message for Telegram with professional analysis"""
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
        
        # Determine primary scenario based on both BTC and ETH
        primary_scenario = "NEUTRAL"
        confidence_level = "low"
        bullish_prob = 50
        bearish_prob = 50
        strongest_signal = "technical"
        volatility_regime = "medium"
        
        # Use professional analysis if available
        if pro_analysis and "error" not in pro_analysis:
            primary_scenario = pro_analysis['primary_scenario']
            confidence_level = pro_analysis['confidence_level']
            bullish_prob = pro_analysis['bullish_probability']
            bearish_prob = pro_analysis['bearish_probability']
            strongest_signal = pro_analysis['key_factors']['strongest_signal'][0]
            volatility_regime = pro_analysis['risk_assessment']['volatility_regime']
        else:
            # Fallback to basic analysis
            if btc_signal == eth_signal:
                primary_scenario = btc_signal
            else:
                primary_scenario = btc_signal if btc_confidence > eth_confidence else eth_signal
            confidence_level = "medium"
            if primary_scenario in ["BUY", "STRONG BUY"]:
                bullish_prob = 65
                bearish_prob = 35
            elif primary_scenario in ["SELL", "STRONG SELL"]:
                bullish_prob = 35
                bearish_prob = 65
            else:
                bullish_prob = 50
                bearish_prob = 50
            volatility_regime = btc_data.get('volatility', 'medium')
        
        # Generate logical targets for BTC based on scenario
        def generate_logical_targets(current_price, support, resistance, scenario, levels):
            """Generate targets that make logical sense for the scenario"""
            if scenario in ["BUY", "STRONG BUY", "BULLISH"]:
                # Bullish: targets above current price, stop below
                target_1 = max(resistance * 0.98, current_price * 1.02)  # At least 2% up
                target_2 = max(resistance * 1.01, current_price * 1.05)  # At least 5% up
                stop_loss = min(support * 1.01, current_price * 0.98)   # At most 2% down
            elif scenario in ["SELL", "STRONG SELL", "BEARISH"]:
                # Bearish: targets below current price, stop above
                target_1 = min(support * 1.02, current_price * 0.98)    # At least 2% down
                target_2 = min(support * 0.99, current_price * 0.95)    # At least 5% down
                stop_loss = max(resistance * 0.99, current_price * 1.02) # At most 2% up
            else:
                # Neutral: small movements
                target_1 = current_price * 1.01
                target_2 = current_price * 1.02
                stop_loss = current_price * 0.99
            
            return {
                'current': current_price,
                'target_1': target_1,
                'target_2': target_2,
                'stop_loss': stop_loss
            }
        
        # Generate BTC and ETH targets
        btc_targets = generate_logical_targets(btc_price, btc_support, btc_resistance, primary_scenario, btc_levels)
        eth_targets = generate_logical_targets(eth_price, eth_support, eth_resistance, eth_signal, eth_levels)
        
        # Override with professional analysis targets if available and logical
        if pro_analysis and "error" not in pro_analysis:
            pro_targets = pro_analysis['price_targets']
            # Validate that professional targets make sense
            if primary_scenario in ["BUY", "STRONG BUY", "BULLISH"]:
                # For bullish scenarios, targets should be above current price
                if (pro_targets.get('target_1', 0) > pro_targets.get('current', 0) and 
                    pro_targets.get('stop_loss', 0) < pro_targets.get('current', 0)):
                    btc_targets = pro_targets
            elif primary_scenario in ["SELL", "STRONG SELL", "BEARISH"]:
                # For bearish scenarios, targets should be below current price
                if (pro_targets.get('target_1', 0) < pro_targets.get('current', 0) and 
                    pro_targets.get('stop_loss', 0) > pro_targets.get('current', 0)):
                    btc_targets = pro_targets
        
        # Format the message with safe HTML
        message = "🔍 <b>PROFESSIONAL CRYPTO ANALYSIS</b>\n\n"
        
        # Executive Summary with professional analysis
        message += "📊 <b>EXECUTIVE SUMMARY</b>\n"
        message += f"• Scenario: <b>{primary_scenario.upper()}</b> ({confidence_level} confidence)\n"
        message += f"• Timeframe: {timeframe}\n"
        message += f"• Bullish: {bullish_prob}% | Bearish: {bearish_prob}%\n"
        message += f"• Strongest Signal: {strongest_signal.replace('_', ' ').title()}\n"
        message += f"• Volatility: {volatility_regime.title()}\n\n"
        
        # BTC Analysis with professional targets
        message += "₿ <b>BTC ANALYSIS</b>\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"💰 Current: <code>${btc_targets['current']:,.0f}</code>\n"
        message += f"📈 Resistance: <code>${btc_resistance:,.0f}</code>\n"
        message += f"📉 Support: <code>${btc_support:,.0f}</code>\n"
        message += f"📊 RSI: {btc_data.get('rsi14', 0):.1f} | Signal: {btc_signal}\n"
        message += f"📈 Trend: {btc_data.get('trend', 'Unknown').title()}\n\n"
        
        # Calculate BTC confidence
        btc_conf = calculate_trading_confidence(
            price=btc_price,
            support=btc_support, 
            resistance=btc_resistance,
            rsi=btc_data.get('rsi14'),
            trend=btc_data.get('trend'),
            signal=btc_signal,
            volume_trend=btc_data.get('volume_trend'),
            atr=btc_data.get('atr')
        )
        
        # BTC Trading Plan (immediately after BTC Analysis)
        message += f"🎯 <b>BTC TRADING PLAN - {primary_scenario.upper()}</b>\n"
        message += f"• Entry Zone: <code>${btc_targets['current']:,.0f}</code>\n"
        
        # Calculate direction and format safely - ensure proper escaping
        tp1_change = calculate_percentage(btc_targets['current'], btc_targets['target_1'])
        tp2_change = calculate_percentage(btc_targets['current'], btc_targets['target_2'])
        sl_change = calculate_percentage(btc_targets['current'], btc_targets['stop_loss'])
        
        # Ensure percentages are properly formatted (avoid special characters)
        tp1_str = f"{tp1_change:.1f}" if tp1_change else "0.0"
        tp2_str = f"{tp2_change:.1f}" if tp2_change else "0.0"
        sl_str = f"{sl_change:.1f}" if sl_change else "0.0"
        
        # Use safe formatting with proper HTML escaping
        if btc_targets['target_1'] > btc_targets['current']:
            message += f"• Target 1: ↗️ <code>${btc_targets['target_1']:,.0f}</code> (+{tp1_str}%)\n"
        else:
            message += f"• Target 1: ↘️ <code>${btc_targets['target_1']:,.0f}</code> (-{tp1_str}%)\n"
            
        if btc_targets['target_2'] > btc_targets['current']:
            message += f"• Target 2: ↗️ <code>${btc_targets['target_2']:,.0f}</code> (+{tp2_str}%)\n"
        else:
            message += f"• Target 2: ↘️ <code>${btc_targets['target_2']:,.0f}</code> (-{tp2_str}%)\n"
            
        if btc_targets['stop_loss'] < btc_targets['current']:
            message += f"• Stop Loss: ↘️ <code>${btc_targets['stop_loss']:,.0f}</code> (-{sl_str}%)\n"
        else:
            message += f"• Stop Loss: ↗️ <code>${btc_targets['stop_loss']:,.0f}</code> (+{sl_str}%)\n"
        
        # Calculate risk/reward with safe formatting
        risk = abs(btc_targets['current'] - btc_targets['stop_loss'])
        reward = abs(btc_targets['target_1'] - btc_targets['current'])
        rr_ratio = reward / risk if risk > 0 else 0
        rr_str = f"{rr_ratio:.1f}" if rr_ratio else "0.0"
        message += f"• Risk/Reward: 1:{rr_str}\n"
        
        # Add confidence scoring
        message += f"• <b>Confidence: {btc_conf['percentage']:.0f}% ({btc_conf['level']})</b>\n"
        message += f"• Strategy: {btc_conf['guidance']}\n\n"
        
        # ETH Analysis
        message += "Ξ <b>ETH ANALYSIS</b>\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"💰 Current: <code>${eth_targets['current']:,.0f}</code>\n"
        message += f"📈 Resistance: <code>${eth_resistance:,.0f}</code>\n"
        message += f"📉 Support: <code>${eth_support:,.0f}</code>\n"
        message += f"📊 RSI: {eth_data.get('rsi14', 0):.1f} | Signal: {eth_signal}\n"
        message += f"📈 Trend: {eth_data.get('trend', 'Unknown').title()}\n\n"
        
        # Calculate ETH confidence
        eth_conf = calculate_trading_confidence(
            price=eth_price,
            support=eth_support,
            resistance=eth_resistance, 
            rsi=eth_data.get('rsi14'),
            trend=eth_data.get('trend'),
            signal=eth_signal,
            volume_trend=eth_data.get('volume_trend'),
            atr=eth_data.get('atr')
        )
        
        # ETH Trading Plan (immediately after ETH Analysis)
        message += f"🎯 <b>ETH TRADING PLAN - {eth_signal.upper()}</b>\n"
        message += f"• Entry: <code>${eth_targets['current']:,.0f}</code>\n"
        
        eth_tp1_change = calculate_percentage(eth_targets['current'], eth_targets['target_1'])
        eth_sl_change = calculate_percentage(eth_targets['current'], eth_targets['stop_loss'])
        
        # Safe percentage formatting
        eth_tp1_str = f"{eth_tp1_change:.1f}" if eth_tp1_change else "0.0"
        eth_sl_str = f"{eth_sl_change:.1f}" if eth_sl_change else "0.0"
        
        if eth_targets['target_1'] > eth_targets['current']:
            message += f"• Target: ↗️ <code>${eth_targets['target_1']:,.0f}</code> (+{eth_tp1_str}%)\n"
        else:
            message += f"• Target: ↘️ <code>${eth_targets['target_1']:,.0f}</code> (-{eth_tp1_str}%)\n"
            
        if eth_targets['stop_loss'] < eth_targets['current']:
            message += f"• Stop: ↘️ <code>${eth_targets['stop_loss']:,.0f}</code> (-{eth_sl_str}%)\n"
        else:
            message += f"• Stop: ↗️ <code>${eth_targets['stop_loss']:,.0f}</code> (+{eth_sl_str}%)\n"
            
        # Add ETH confidence scoring
        message += f"• <b>Confidence: {eth_conf['percentage']:.0f}% ({eth_conf['level']})</b>\n"
        message += f"• Strategy: {eth_conf['guidance']}\n\n"
        
        # Market Context
        message += "📈 <b>MARKET CONTEXT</b>\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"• BTC Volume: {btc_data.get('volume_trend', 'Unknown').title()}\n"
        message += f"• ETH Volume: {eth_data.get('volume_trend', 'Unknown').title()}\n"
        message += f"• BTC ATR: <code>${btc_data.get('atr', 0):,.0f}</code>\n"
        message += f"• ETH ATR: <code>${eth_data.get('atr', 0):,.0f}</code>\n"
        
        if pro_analysis and "error" not in pro_analysis:
            expected_move = pro_analysis['price_targets'].get('expected_move', 0)
            message += f"• Expected Move: <code>${expected_move:,.0f}</code>\n"
        
        message += "\n⚠️ <b>Risk Management: Use proper position sizing and stick to your plan</b>"
        
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
        message = format_telegram_message(market_data["technical_indicators"], professional_trader.generate_probabilistic_forecast(market_data))
        
        # Debug: Show message details
        print(f"[DEBUG] Message length: {len(message)} characters")
        if len(message) > 4096:
            print(f"[WARN] Message exceeds Telegram limit (4096 chars)")
        
        # Show first 500 chars for debugging
        print(f"[DEBUG] Message preview:")
        print(f"{'='*50}")
        print(message[:500] + "..." if len(message) > 500 else message)
        print(f"{'='*50}")
        
        # Create a new instance of the Telegram bot with current settings
        bot = TelegramBot(
            bot_token=config["telegram"]["bot_token"],
            chat_id=config["telegram"]["chat_id"]
        )
        success = bot.send_message(message)
        
        if success:
            print("[INFO] Telegram message sent successfully")
        else:
            print("[ERROR] Failed to send Telegram message")
        
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
