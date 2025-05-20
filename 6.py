#!/usr/bin/env python3

import requests
import json
import os
import pandas as pd
import time
import concurrent.futures
import yfinance as yf
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
from openai import OpenAI
from telegram_utils import send_telegram_message

# ----------------------------
# 1. Config
# ----------------------------
def load_config():
    default_config = {
        "api_keys": {
            "openai": "YOUR_OPENAI_API_KEY",
            "fred": "YOUR_FRED_API_KEY",
            "alphavantage": "YOUR_ALPHAVANTAGE_API_KEY"
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
        }
    }
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
    with open("config.json", "w") as f:
        json.dump(default_config, f, indent=4)
        print("[INFO] Default config.json created. Please update your API key.")
    return default_config

config = load_config()

# ----------------------------
# 2. API Request Handler
# ----------------------------
def resilient_request(url, params=None, max_retries=None, timeout=None):
    if max_retries is None:
        max_retries = config["api"]["max_retries"]
    if timeout is None:
        timeout = config["api"]["timeout"]
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"[WARN] Rate limited, waiting {retry_after}s (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_after)
                continue
                
            response.raise_for_status()
            return response.json()
            
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
    data = resilient_request(url, params)
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
    
    for symbol, label in symbols.items():
        try:
            data = resilient_request(url, {"symbol": symbol, "interval": "1d", "limit": 20})
            if not data:
                continue
                
            closes = [float(k[4]) for k in data]
            sma7 = sum(closes[-7:]) / 7
            sma14 = sum(closes[-14:]) / 14
            
            changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [max(0, c) for c in changes]
            losses = [max(0, -c) for c in changes]
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            rs = avg_gain / avg_loss if avg_loss != 0 else 1e10
            rsi = 100 - (100 / (1 + rs))
            
            trend = "bullish" if sma7 > sma14 else "bearish"
            
            signal = "NEUTRAL"
            signal_confidence = 0.0
            
            if rsi > 70:
                signal = "SELL" if rsi > 75 else "STRONG SELL"
                signal_confidence = (rsi - 70) * 4
            elif rsi < 30:
                signal = "BUY" if rsi < 25 else "STRONG BUY"
                signal_confidence = (30 - rsi) * 4
                
            indicators[label] = {
                "price": closes[-1],
                "sma7": sma7,
                "sma14": sma14,
                "rsi14": rsi,
                "trend": trend,
                "signal": signal,
                "signal_confidence": signal_confidence
            }
            
            indicators[f"{label.lower()}_rsi"] = rsi
            indicators[f"{label.lower()}_trend"] = trend
            indicators[f"{label.lower()}_signal"] = signal
            indicators[f"{label.lower()}_signal_confidence"] = signal_confidence
            
        except Exception as e:
            print(f"[ERROR] Technicals {label}: {e}")
    
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
        "technicals": get_technical_indicators,
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
    
    return results

# ----------------------------
# 5. Save History
# ----------------------------
def save_today_data(all_data):
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Determine if this is a morning or evening run
    current_hour = datetime.now().hour
    session = "morning" if current_hour < 15 else "evening"
    
    file = config["storage"]["file"]
    
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
    """Save structured prediction with detailed metrics"""
    prediction_file = "detailed_predictions.json"
    today = datetime.now().strftime("%Y-%m-%d")
    current_hour = datetime.now().hour
    session = "morning" if current_hour < 15 else "evening"
    
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
            "fear_greed": int(market_data.get("fear_greed")) if pd.notna(market_data.get("fear_greed")) else None,
        },
        "predictions": prediction_data,
        "validation_points": [],  # To be filled by validation script
        "final_accuracy": None    # To be determined later
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
            # If file is corrupted, create a new one
            print("[WARN] Prediction history file is corrupted. Creating a new one.")
            with open(prediction_file, "w") as f:
                json.dump([], f)
            return "Prediction history was reset due to file corruption. No previous predictions available."
        
        # If predictions file is empty or invalid
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
            pred_session = pred.get("session", "unknown")  # Handle older entries without session
            
            # Skip current session's predictions (too recent)
            if pred_date == today and pred_session == current_session:
                continue
                
            # For morning predictions on the same day, compare with evening data
            if pred_date == today and pred_session == "morning" and current_session == "evening":
                # Current evening data is our comparison point
                current_data = df[(df['date'] == today) & (df['session'] == "evening")]
                if len(current_data) > 0:
                    current_row = current_data.iloc[0]
                    
                    # Get prediction and actual values
                    pred_btc = pred["btc_price"]
                    actual_btc = current_row["btc_price"]
                    
                    # Check if prediction was correct (intraday prediction)
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
                        "timeframe": "Intraday (AM to PM)"
                    })
            
            # For older predictions, look for subsequent sessions
            else:
                # Find the next 2-3 data points after this prediction
                if "session" in df.columns:
                    # For newer data with session column
                    query_mask = ((df['date'] > pred_date) | 
                                 ((df['date'] == pred_date) & 
                                  (df['session'] != pred_session)))
                    subsequent_data = df[query_mask].sort_values(by=['date', 'session']).head(3)
                else:
                    # For older data without session column
                    subsequent_data = df[df['date'] > pred_date].head(2)
                
                if len(subsequent_data) > 0:
                    # We have data to compare with prediction
                    next_data = subsequent_data.iloc[0] if len(subsequent_data) > 0 else None
                    second_data = subsequent_data.iloc[1] if len(subsequent_data) > 1 else None
                    third_data = subsequent_data.iloc[2] if len(subsequent_data) > 2 else None
                    
                    # Extract values for comparison
                    pred_btc = pred["btc_price"]
                    next_btc = next_data["btc_price"] if next_data is not None else None
                    second_btc = second_data["btc_price"] if second_data is not None else None
                    third_btc = third_data["btc_price"] if third_data is not None else None
                    
                    # Determine timeframe based on sessions
                    if "session" in df.columns and next_data is not None:
                        if pred_date == next_data["date"]:
                            timeframe = "Intraday (AM to PM)"
                        elif pred_session == "evening" and next_data["session"] == "morning":
                            timeframe = "Overnight"
                        else:
                            timeframe = "24-48 hours"
                    else:
                        timeframe = "24-48 hours"
                    
                    # Check if prediction was directionally correct 
                    if pred_btc is not None and next_btc is not None:
                        if "rally" in pred["prediction"].lower() and next_btc > pred_btc:
                            direction = "CORRECT"
                        elif "dip" in pred["prediction"].lower() and next_btc < pred_btc:
                            direction = "CORRECT"
                        elif "stagnation" in pred["prediction"].lower() and abs(next_btc - pred_btc) / pred_btc < 0.02:
                            direction = "CORRECT"
                        else:
                            direction = "INCORRECT"
                    else:
                        direction = "UNKNOWN"
                    
                    result = {
                        "prediction_date": f"{pred_date} ({pred_session if 'session' in pred else 'all-day'})",
                        "prediction_summary": pred["prediction"][:100] + "..." if pred["prediction"] and len(pred["prediction"]) > 100 else pred["prediction"],
                        "btc_at_prediction": pred_btc,
                        "btc_actual": next_btc,
                        "btc_second_point": second_btc,
                        "btc_third_point": third_btc,
                        "direction": direction,
                        "timeframe": timeframe
                    }
                    
                    results.append(result)
        
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
                
            if result.get('btc_second_point') is not None and result['btc_at_prediction'] is not None:
                change = ((result['btc_second_point'] - result['btc_at_prediction']) / result['btc_at_prediction']) * 100
                output += f"BTC later point: ${result['btc_second_point']:.2f} ({change:.2f}%)\n"
                
            output += f"Directional Accuracy: {result['direction']}\n\n"
            
        return output
            
    except Exception as e:
        print(f"[ERROR] Analyzing prediction accuracy: {e}")
        # In case of unexpected error, reset the file
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
    if not config["api_keys"]["openai"] or config["api_keys"]["openai"] == "YOUR_OPENAI_API_KEY":
        return "AI summary unavailable. Please add your OpenAI API key to config.json."
        
    try:
        client = OpenAI(api_key=config["api_keys"]["openai"])
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] GPT call failed: {e}")
        return f"AI summary unavailable: {str(e)}"

# ----------------------------
# 7. Main Script
# ----------------------------
if __name__ == "__main__":
    print("=== ✅ Starting Market Crypto Summary ===\n")
    
    all_data = collect_all_data()
    
    # Extract data for display
    crypto = all_data.get("crypto", {})
    technicals = all_data.get("technicals", {})
    levels = all_data.get("levels", {})
    fear = all_data.get("fear_greed", {})
    dominance = all_data.get("btc_dominance")
    market_cap, market_cap_change = all_data.get("market_cap", (None, None))
    volumes = all_data.get("volumes", {})
    futures = all_data.get("futures", {})
    
    # ------------------------------------
    # Display ALL collected data with [DATA] prefix
    # ------------------------------------
    print("\n=== 📊 Crypto Market Data ===")
    print(f"[DATA] BTC: ${crypto.get('btc')}, ETH: ${crypto.get('eth')}")
    
    if "BTC" in technicals:
        btc_tech = technicals["BTC"]
        btc_lvl = levels.get("BTC", {})
        print(f"[DATA] BTC RSI: {btc_tech['rsi14']:.1f}, Trend: {btc_tech['trend'].upper()}, " + 
              f"Signal: {btc_tech['signal']} (Confidence: {btc_tech['signal_confidence']:.1f})")
        print(f"[DATA] BTC Support: ${btc_lvl.get('support', 'N/A'):.0f}, " + 
              f"Resistance: ${btc_lvl.get('resistance', 'N/A'):.0f}")
    
    if "ETH" in technicals:
        eth_tech = technicals["ETH"]
        eth_lvl = levels.get("ETH", {})
        print(f"[DATA] ETH RSI: {eth_tech['rsi14']:.1f}, Trend: {eth_tech['trend'].upper()}, " + 
              f"Signal: {eth_tech['signal']} (Confidence: {eth_tech['signal_confidence']:.1f})")
        print(f"[DATA] ETH Support: ${eth_lvl.get('support', 'N/A'):.0f}, " + 
              f"Resistance: ${eth_lvl.get('resistance', 'N/A'):.0f}")
    
    print(f"[DATA] BTC Dominance: {dominance:.2f}%" if dominance else "[DATA] BTC Dominance: N/A")
    print(f"[DATA] Fear & Greed Index: {fear.get('index')} ({fear.get('sentiment')})" if fear.get('index') else "[DATA] Fear & Greed Index: N/A")
    
    if market_cap and market_cap_change:
        print(f"[DATA] Market Cap: ${market_cap/1e12:.2f}T ({market_cap_change:.2f}% 24h)")
    
    # Display trading volumes
    if volumes.get("btc_volume"):
        print(f"[DATA] BTC 24h Volume: ${volumes.get('btc_volume')/1e9:.2f}B")
    if volumes.get("eth_volume"):
        print(f"[DATA] ETH 24h Volume: ${volumes.get('eth_volume')/1e9:.2f}B")
    
    # Display futures data
    if "BTC" in futures:
        btc_futures = futures["BTC"]
        print(f"[DATA] BTC Funding Rate: {btc_futures.get('funding_rate'):.4f}%")
        if btc_futures.get('long_ratio') and btc_futures.get('short_ratio'):
            print(f"[DATA] BTC Long/Short Ratio: {btc_futures.get('long_ratio'):.2f}/{btc_futures.get('short_ratio'):.2f}")
        if btc_futures.get('open_interest'):
            print(f"[DATA] BTC Open Interest: ${btc_futures.get('open_interest')/1e9:.2f}B")
    
    if "ETH" in futures:
        eth_futures = futures["ETH"]
        print(f"[DATA] ETH Funding Rate: {eth_futures.get('funding_rate'):.4f}%")
        if eth_futures.get('long_ratio') and eth_futures.get('short_ratio'):
            print(f"[DATA] ETH Long/Short Ratio: {eth_futures.get('long_ratio'):.2f}/{eth_futures.get('short_ratio'):.2f}")
        if eth_futures.get('open_interest'):
            print(f"[DATA] ETH Open Interest: ${eth_futures.get('open_interest')/1e9:.2f}B")
    
    # Display macroeconomic data
    print("\n=== 📈 Macroeconomic Data ===")
    m2_data = all_data.get("m2_supply", {})
    if m2_data and m2_data.get("m2_supply"):
        print(f"[DATA] M2 Money Supply: ${m2_data.get('m2_supply')/1e12:.2f}T ({m2_data.get('m2_date')})")
    
    inflation_data = all_data.get("inflation", {})
    if inflation_data and inflation_data.get("inflation_rate"):
        print(f"[DATA] Inflation Rate: {inflation_data.get('inflation_rate'):.2f}% ({inflation_data.get('inflation_date')})")
    
    interest_data = all_data.get("interest_rates", {})
    if interest_data:
        if interest_data.get("fed_rate"):
            print(f"[DATA] Fed Funds Rate: {interest_data.get('fed_rate'):.2f}%")
        if interest_data.get("t10_yield"):
            print(f"[DATA] 10-Year Treasury Yield: {interest_data.get('t10_yield'):.2f}%")
        if interest_data.get("t5_yield"):
            print(f"[DATA] 5-Year Treasury Yield: {interest_data.get('t5_yield'):.2f}%")
    
    # Display stock indices
    indices = all_data.get("stock_indices", {})
    if indices:
        print("\n=== 🏢 Stock Market Indices ===")
        if "sp500" in indices:
            print(f"[DATA] S&P 500: {indices['sp500']:.2f} " + 
                  f"({indices.get('sp500_change', 0):.2f}%)" if indices.get('sp500_change') else "")
        if "dow_jones" in indices:
            print(f"[DATA] Dow Jones: {indices['dow_jones']:.2f} " + 
                  f"({indices.get('dow_jones_change', 0):.2f}%)" if indices.get('dow_jones_change') else "")
        if "nasdaq" in indices:
            print(f"[DATA] NASDAQ: {indices['nasdaq']:.2f} " + 
                  f"({indices.get('nasdaq_change', 0):.2f}%)" if indices.get('nasdaq_change') else "")
        if "vix" in indices:
            print(f"[DATA] VIX (Volatility): {indices['vix']:.2f}")
    
    # Display commodity prices
    commodities = all_data.get("commodities", {})
    if commodities:
        print("\n=== 🥇 Commodity Prices ===")
        if "gold" in commodities:
            print(f"[DATA] Gold: ${commodities['gold']:.2f}")
        if "silver" in commodities:
            print(f"[DATA] Silver: ${commodities['silver']:.2f}")
        if "crude_oil" in commodities:
            print(f"[DATA] Crude Oil: ${commodities['crude_oil']:.2f}")
        if "natural_gas" in commodities:
            print(f"[DATA] Natural Gas: ${commodities['natural_gas']:.2f}")
    
    # Display social metrics
    social = all_data.get("social_metrics", {})
    if social:
        print("\n=== 👥 Social Metrics ===")
        if "forum_posts" in social:
            print(f"[DATA] Forum Posts: {social['forum_posts']:,}")
        if "forum_topics" in social:
            print(f"[DATA] Forum Topics: {social['forum_topics']:,}")
        if "btc_github_stars" in social:
            print(f"[DATA] BTC GitHub Stars: {social['btc_github_stars']:,}")
        if "eth_github_stars" in social:
            print(f"[DATA] ETH GitHub Stars: {social['eth_github_stars']:,}")
        if "btc_recent_commits" in social:
            print(f"[DATA] BTC Recent Commits: {social['btc_recent_commits']:,}")
        if "eth_recent_commits" in social:
            print(f"[DATA] ETH Recent Commits: {social['eth_recent_commits']:,}")
    
    print("\n=== 💾 Data Storage ===")
    # Save to file
    save_today_data(all_data)
    
    # AI Insights
    if config.get("ai_insights_enabled"):
        try:
            file = config["storage"]["file"]
            if not os.path.exists(file):
                print("\n[WARN] No historical data available for AI insights")
            else:
                df = pd.read_csv(file)
                if len(df) < 2:
                    print("\n[WARN] Need at least 2 days of data for AI insights")
                else:
                    days = min(3, len(df))
                    last_days = df.tail(days).to_dict("records")
                    
                    # Get current prices to add to the prompt
                    current_btc_price = df.iloc[-1].get('btc_price') if 'btc_price' in df.columns and pd.notna(df.iloc[-1].get('btc_price')) else 'N/A'
                    current_eth_price = df.iloc[-1].get('eth_price') if 'eth_price' in df.columns and pd.notna(df.iloc[-1].get('eth_price')) else 'N/A'
                    
                    # Build a much more comprehensive prompt that includes ALL data points
                    detailed_data = []
                    for row in last_days:
                        data_point = f"DATE: {row['date']}\n"
                        
                        # Crypto prices and market structure
                        data_point += "CRYPTO PRICES:\n"
                        data_point += f"- BTC: ${row['btc_price']:.2f}\n" if 'btc_price' in row and pd.notna(row['btc_price']) else ""
                        data_point += f"- ETH: ${row['eth_price']:.2f}\n" if 'eth_price' in row and pd.notna(row['eth_price']) else ""
                        data_point += f"- BTC Dominance: {row['btc_dominance']:.2f}%\n" if 'btc_dominance' in row and pd.notna(row['btc_dominance']) else ""
                        data_point += f"- Market Cap: ${row['market_cap']/1e12:.2f}T\n" if 'market_cap' in row and pd.notna(row['market_cap']) else ""
                        
                        # Trading volumes and activity
                        data_point += "\nTRADING ACTIVITY:\n"
                        data_point += f"- BTC Volume: ${row['btc_volume']/1e9:.2f}B\n" if 'btc_volume' in row and pd.notna(row['btc_volume']) else ""
                        data_point += f"- ETH Volume: ${row['eth_volume']/1e9:.2f}B\n" if 'eth_volume' in row and pd.notna(row['eth_volume']) else ""
                        data_point += f"- BTC Funding Rate: {row['btc_funding']:.4f}%\n" if 'btc_funding' in row and pd.notna(row['btc_funding']) else ""
                        data_point += f"- ETH Funding Rate: {row['eth_funding']:.4f}%\n" if 'eth_funding' in row and pd.notna(row['eth_funding']) else ""
                        
                        # Technical indicators
                        data_point += "\nTECHNICAL INDICATORS:\n"
                        data_point += f"- BTC RSI: {row['btc_rsi']:.2f}\n" if 'btc_rsi' in row and pd.notna(row['btc_rsi']) else ""
                        data_point += f"- ETH RSI: {row['eth_rsi']:.2f}\n" if 'eth_rsi' in row and pd.notna(row['eth_rsi']) else ""
                        data_point += f"- BTC Trend: {row['btc_trend']}\n" if 'btc_trend' in row and pd.notna(row['btc_trend']) else ""
                        data_point += f"- ETH Trend: {row['eth_trend']}\n" if 'eth_trend' in row and pd.notna(row['eth_trend']) else ""
                        data_point += f"- BTC Signal: {row['btc_signal']}\n" if 'btc_signal' in row and pd.notna(row['btc_signal']) else ""
                        data_point += f"- ETH Signal: {row['eth_signal']}\n" if 'eth_signal' in row and pd.notna(row['eth_signal']) else ""
                        data_point += f"- Fear & Greed: {row['fear_greed']} (0=Extreme Fear, 100=Extreme Greed)\n" if 'fear_greed' in row and pd.notna(row['fear_greed']) else ""
                        
                        # Macroeconomic indicators
                        data_point += "\nMACROECONOMIC INDICATORS:\n"
                        data_point += f"- M2 Money Supply: ${row['m2_supply']/1e12:.2f}T\n" if 'm2_supply' in row and pd.notna(row['m2_supply']) else ""
                        data_point += f"- Inflation Rate: {row['inflation_rate']:.2f}%\n" if 'inflation_rate' in row and pd.notna(row['inflation_rate']) else ""
                        data_point += f"- Fed Rate: {row['fed_rate']:.2f}%\n" if 'fed_rate' in row and pd.notna(row['fed_rate']) else ""
                        data_point += f"- 10Y Treasury: {row['t10_yield']:.2f}%\n" if 't10_yield' in row and pd.notna(row['t10_yield']) else ""
                        
                        # Stock market
                        data_point += "\nSTOCK MARKET:\n"
                        data_point += f"- S&P 500: {row['sp500']:.2f}\n" if 'sp500' in row and pd.notna(row['sp500']) else ""
                        data_point += f"- Dow Jones: {row['dow_jones']:.2f}\n" if 'dow_jones' in row and pd.notna(row['dow_jones']) else ""
                        data_point += f"- NASDAQ: {row['nasdaq']:.2f}\n" if 'nasdaq' in row and pd.notna(row['nasdaq']) else ""
                        data_point += f"- VIX: {row['vix']:.2f}\n" if 'vix' in row and pd.notna(row['vix']) else ""
                        
                        # Commodities
                        data_point += "\nCOMMODITIES:\n"
                        data_point += f"- Gold: ${row['gold']:.2f}\n" if 'gold' in row and pd.notna(row['gold']) else ""
                        data_point += f"- Silver: ${row['silver']:.2f}\n" if 'silver' in row and pd.notna(row['silver']) else ""
                        data_point += f"- Crude Oil: ${row['crude_oil']:.2f}\n" if 'crude_oil' in row and pd.notna(row['crude_oil']) else ""
                        
                        detailed_data.append(data_point)
                    
                    # Get prediction accuracy analysis for past predictions
                    accuracy_analysis = get_prediction_accuracy()
                    
                    prompt = f"""
As a crypto market analyst, provide a highly structured market assessment that includes specific, actionable trading advice with exact price levels. Your response MUST follow this exact structure:

## OVERALL MARKET ANALYSIS
Provide a concise assessment of current crypto market conditions and the macro environment.

## BTC TRADING RECOMMENDATION
- Current Price: ${current_btc_price}
- Direction: [BULLISH/BEARISH/SIDEWAYS]
- Primary Trade Setup: [SPECIFIC ENTRY/EXIT RECOMMENDATION] 
- Entry Price Range: $X,XXX - $X,XXX
- Take Profit Targets: TP1: $X,XXX (XX%), TP2: $X,XXX (XX%)
- Stop Loss: $X,XXX (XX%)
- Timeframe: [SPECIFIC HOURS/DAYS]
- Key Support Levels: $X,XXX, $X,XXX, $X,XXX
- Key Resistance Levels: $X,XXX, $X,XXX, $X,XXX
- Invalidation Scenario: [SPECIFIC PRICE OR CONDITION]
- Confidence Score: X/10
- Confidence Rationale: [EXPLAIN WHY THIS CONFIDENCE LEVEL]

## ETH TRADING RECOMMENDATION
- Current Price: ${current_eth_price}
- Direction: [BULLISH/BEARISH/SIDEWAYS]
- Primary Trade Setup: [SPECIFIC ENTRY/EXIT RECOMMENDATION]
- Entry Price Range: $X,XXX - $X,XXX
- Take Profit Targets: TP1: $X,XXX (XX%), TP2: $X,XXX (XX%)
- Stop Loss: $X,XXX (XX%)
- Timeframe: [SPECIFIC HOURS/DAYS]
- Key Support Levels: $X,XXX, $X,XXX, $X,XXX
- Key Resistance Levels: $X,XXX, $X,XXX, $X,XXX
- Invalidation Scenario: [SPECIFIC PRICE OR CONDITION]
- Confidence Score: X/10
- Confidence Rationale: [EXPLAIN WHY THIS CONFIDENCE LEVEL]

## MARKET STRUCTURE INSIGHTS
- Correlation Analysis: [CRYPTO-STOCKS-COMMODITIES RELATIONSHIPS]
- Volume Analysis: [INSIGHTS ON VOLUME PATTERNS]
- Market Breadth: [ANALYSIS OF BROADER MARKET HEALTH]
- Dominant Market Force: [TECHNICAL/FUNDAMENTAL/SENTIMENT]

## RISK ASSESSMENT
- Market Risk Level: X/10 [1=LOW RISK, 10=HIGH RISK]
- Key Risk Factors: [LIST SPECIFIC RISKS]
- Volatility Expectation: [HIGH/MEDIUM/LOW] with [INCREASING/DECREASING] trend

Your predictions will be tracked and compared with actual outcomes for accuracy. Be precise with price levels and realistic with confidence scores.

{accuracy_analysis}

DATA FOR ANALYSIS:
""" + "\n\n".join(detailed_data)
                    
                    print("\n=== 📈 AI Market Interpretation ===\n")
                    ai_analysis = ask_ai(prompt)
                    # After printing the AI analysis, replace the Telegram code with this:
                    print(ai_analysis)

                    # Enhanced Telegram notification with more details
                    try:
                        # Create a simple message with the most important parts
                        message = "🤖 <b>CRYPTO MARKET ANALYSIS</b>\n\n"
                        
                        # Add market overview summary
                        if "## OVERALL MARKET ANALYSIS" in ai_analysis:
                            overview = ai_analysis.split("## OVERALL MARKET ANALYSIS")[1].split("## BTC TRADING RECOMMENDATION")[0].strip()
                            # Get first sentence or first 150 characters
                            if "." in overview[:150]:
                                summary = overview.split(".")[0] + "."
                            else:
                                summary = overview[:150] + "..."
                            message += f"<b>Overview:</b> {summary}\n\n"
                        
                        # Extract sections properly
                        btc_section = ""
                        eth_section = ""
                        
                        if "## BTC TRADING RECOMMENDATION" in ai_analysis and "## ETH TRADING RECOMMENDATION" in ai_analysis:
                            btc_section = ai_analysis.split("## BTC TRADING RECOMMENDATION")[1].split("## ETH TRADING RECOMMENDATION")[0]
                            
                            if "## MARKET STRUCTURE INSIGHTS" in ai_analysis:
                                eth_section = ai_analysis.split("## ETH TRADING RECOMMENDATION")[1].split("## MARKET STRUCTURE INSIGHTS")[0]
                            else:
                                eth_section = ai_analysis.split("## ETH TRADING RECOMMENDATION")[1]
                        
                        # Extract BTC details from BTC section
                        btc_direction = ""
                        btc_entry = ""
                        btc_tp = ""
                        btc_sl = ""
                        btc_time = ""
                        btc_confidence = ""
                        
                        for line in btc_section.split("\n"):
                            if "Direction:" in line:
                                btc_direction = line.split("Direction:")[1].strip()
                            elif "Entry Price Range:" in line:
                                btc_entry = line
                            elif "Take Profit Targets:" in line:
                                btc_tp = line
                            elif "Stop Loss:" in line:
                                btc_sl = line
                            elif "Timeframe:" in line:
                                btc_time = line.split("Timeframe:")[1].strip()
                            elif "Confidence Score:" in line:
                                btc_confidence = line.split("Confidence Score:")[1].strip()
                        
                        # Add BTC section
                        message += f"<b>🔶 BTC ({btc_direction}):</b>\n"
                        message += f"{btc_entry}\n"
                        message += f"{btc_tp}\n"
                        message += f"{btc_sl}\n"
                        if btc_time:
                            message += f"- Timeframe: {btc_time}\n"
                        if btc_confidence:
                            message += f"- Confidence: {btc_confidence}\n"
                        message += "\n"
                        
                        # Extract ETH details from ETH section
                        eth_direction = ""
                        eth_entry = ""
                        eth_tp = ""
                        eth_sl = ""
                        eth_time = ""
                        eth_confidence = ""
                        
                        for line in eth_section.split("\n"):
                            if "Direction:" in line:
                                eth_direction = line.split("Direction:")[1].strip()
                            elif "Entry Price Range:" in line:
                                eth_entry = line
                            elif "Take Profit Targets:" in line:
                                eth_tp = line
                            elif "Stop Loss:" in line:
                                eth_sl = line
                            elif "Timeframe:" in line:
                                eth_time = line.split("Timeframe:")[1].strip()
                            elif "Confidence Score:" in line:
                                eth_confidence = line.split("Confidence Score:")[1].strip()
                        
                        # Add ETH section
                        message += f"<b>💠 ETH ({eth_direction}):</b>\n"
                        message += f"{eth_entry}\n"
                        message += f"{eth_tp}\n"
                        message += f"{eth_sl}\n"
                        if eth_time:
                            message += f"- Timeframe: {eth_time}\n"
                        if eth_confidence:
                            message += f"- Confidence: {eth_confidence}\n"
                        message += "\n"
                        
                        # Find risk level and volatility
                        risk_level = "N/A"
                        volatility = ""
                        
                        if "## RISK ASSESSMENT" in ai_analysis:
                            risk_section = ai_analysis.split("## RISK ASSESSMENT")[1]
                            for line in risk_section.split("\n"):
                                if "Market Risk Level:" in line:
                                    risk_level = line.split("Market Risk Level:")[1].strip()
                                elif "Volatility Expectation:" in line:
                                    volatility = line.split("Volatility Expectation:")[1].strip()
                        
                        message += f"<b>⚠️ RISK ASSESSMENT:</b>\n"
                        message += f"- Risk Level: {risk_level}\n"
                        if volatility:
                            message += f"- Volatility: {volatility}\n"
                        message += f"\n<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>"
                        
                        # Send the message
                        send_telegram_message(message)
                        print("[INFO] Enhanced Telegram market analysis sent")
                    except Exception as e:
                        print(f"[ERROR] Failed to send Telegram notification: {e}")
                    
                    # Parse the AI response to extract structured prediction data
                    try:
                        # Extract prediction sections
                        structured_prediction = {}
                        
                        # Very basic parsing - in production you'd want more robust extraction
                        if "## BTC TRADING RECOMMENDATION" in ai_analysis and "## ETH TRADING RECOMMENDATION" in ai_analysis:
                            btc_section = ai_analysis.split("## BTC TRADING RECOMMENDATION")[1].split("## ETH TRADING RECOMMENDATION")[0]
                            eth_section = ai_analysis.split("## ETH TRADING RECOMMENDATION")[1].split("## MARKET STRUCTURE INSIGHTS")[0] if "## MARKET STRUCTURE INSIGHTS" in ai_analysis else ai_analysis.split("## ETH TRADING RECOMMENDATION")[1]
                            
                            # Extract BTC prediction components
                            btc_prediction = {}
                            for field in ["Direction:", "Primary Trade Setup:", "Entry Price Range:", "Take Profit Targets:", 
                                        "Stop Loss:", "Timeframe:", "Confidence Score:", "Key Support Levels:", "Key Resistance Levels:"]:
                                if field in btc_section:
                                    field_line = [line for line in btc_section.split("\n") if field in line]
                                    if field_line:
                                        key = field.replace(":", "").strip().lower().replace(" ", "_")
                                        btc_prediction[key] = field_line[0].split(field)[1].strip()
                            
                            # Extract ETH prediction components  
                            eth_prediction = {}
                            for field in ["Direction:", "Primary Trade Setup:", "Entry Price Range:", "Take Profit Targets:", 
                                        "Stop Loss:", "Timeframe:", "Confidence Score:", "Key Support Levels:", "Key Resistance Levels:"]:
                                if field in eth_section:
                                    field_line = [line for line in eth_section.split("\n") if field in line]
                                    if field_line:
                                        key = field.replace(":", "").strip().lower().replace(" ", "_")
                                        eth_prediction[key] = field_line[0].split(field)[1].strip()
                            
                            structured_prediction = {
                                "btc_prediction": btc_prediction,
                                "eth_prediction": eth_prediction
                            }
                            
                            # Save detailed prediction
                            current_data = df.iloc[-1].to_dict()
                            save_detailed_prediction(structured_prediction, current_data)
                            print("[INFO] Structured prediction data saved successfully")
                        else:
                            print("[WARN] Could not parse structured format from AI response")
                        
                        # Also save in the original format for backward compatibility
                        save_prediction(ai_analysis, current_data)
                        
                    except Exception as e:
                        print(f"[ERROR] Failed to parse structured prediction: {e}")
                        # Fall back to original format
                        current_data = df.iloc[-1].to_dict()
                        save_prediction(ai_analysis, current_data)
                    
        except Exception as e:
            print(f"\n[ERROR] Failed to generate AI insights: {e}")

    print("\n=== ✅ Done ===")
