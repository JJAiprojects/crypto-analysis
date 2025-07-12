#!/usr/bin/env python3

import requests
import json
import os
import pandas as pd
import time
import concurrent.futures
import yfinance as yf
import numpy as np
import hmac
import hashlib
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import re

class CryptoDataCollector:
    def __init__(self, config):
        self.config = config
        # Enhanced API keys for new data sources
        self.coinmarketcal_key = os.getenv("COINMARKETCAL_API_KEY")
        self.news_api_key = os.getenv("NEWS_API_KEY") 
        self.binance_api_key = os.getenv("BINANCE_API_KEY")
        self.binance_secret = os.getenv("BINANCE_SECRET")
        self.etherscan_api_key = os.getenv("ETHERSCAN_API_KEY")
        self.polygon_api_key = os.getenv("POLYGON_API_KEY")
    
    def resilient_request(self, url, params=None, headers=None, max_retries=None, timeout=None):
        """Make resilient API requests with retries and error handling"""
        if max_retries is None:
            max_retries = self.config["api"]["max_retries"]
        if timeout is None:
            timeout = self.config["api"]["timeout"]
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
                
                # Enhanced rate limiting protection
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    # Intelligent retry_after calculation
                    if 'binance' in url.lower():
                        retry_after = min(retry_after, 180)  # Binance: Max 3 minutes
                    elif 'coingecko' in url.lower():
                        retry_after = min(retry_after, 300)  # CoinGecko: Max 5 minutes
                    else:
                        retry_after = min(retry_after, 120)  # Others: Max 2 minutes
                    
                    # Add exponential backoff for repeated rate limits
                    backoff_multiplier = 2 ** (attempt - 1) if attempt > 1 else 1
                    actual_wait = min(retry_after * backoff_multiplier, 600)  # Max 10 minutes total
                    
                    print(f"[WARN] Rate limited on {url}, waiting {actual_wait}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(actual_wait)
                    continue
                    
                # Check for other common status codes
                if response.status_code == 403:
                    print(f"[ERROR] Access forbidden: {url}")
                    return None
                elif response.status_code == 404:
                    print(f"[ERROR] Endpoint not found: {url}")
                    return None
                elif response.status_code == 502 or response.status_code == 503:
                    print(f"[WARN] Server temporarily unavailable ({response.status_code}): {url}")
                    time.sleep(min(10, 2 ** attempt))  # Exponential backoff up to 10s
                    continue
                elif response.status_code == 500:
                    print(f"[ERROR] Server error from {url}")
                    time.sleep(5)
                    continue
                
                response.raise_for_status()
                
                try:
                    data = response.json()
                    if not data:
                        print(f"[WARN] Empty response from {url}")
                        return None
                    
                    # Add small delay after successful CoinGecko calls to be respectful
                    if 'coingecko' in url.lower():
                        time.sleep(0.5)  # 500ms delay for CoinGecko
                    
                    return data
                except json.JSONDecodeError as e:
                    print(f"[ERROR] Invalid JSON response from {url}: {e}")
                    return None
                
            except requests.exceptions.RequestException as e:
                backoff = min(30, self.config["api"]["backoff_factor"] ** attempt)  # Cap backoff at 30s
                print(f"[ERROR] API request failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"[INFO] Retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
        
        print(f"[CRITICAL] All {max_retries} attempts failed for URL: {url}")
        return None

    # ----------------------------
    # Macroeconomic Data Collection
    # ----------------------------
    def get_m2_money_supply(self):
        """Get M2 money supply data from FRED API with fallback"""
        fred_key = self.config["api_keys"]["fred"]
        
        if not fred_key:
            print("[WARN] FRED API key not configured - using alternative source")
            return self._get_m2_alternative()
        
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": "M2SL",
            "api_key": fred_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1
        }
        
        try:
            data = self.resilient_request(url, params)
            if data and "observations" in data and len(data["observations"]) > 0:
                latest = data["observations"][0]
                return {
                    "m2_supply": float(latest["value"]) * 1e9,
                    "m2_date": latest["date"]
                }
        except Exception as e:
            print(f"[ERROR] M2 Money Supply from FRED: {e}")
        
        return self._get_m2_alternative()

    def _get_m2_alternative(self):
        """Alternative M2 data source"""
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
                return {"m2_supply": value, "m2_date": date}
        except Exception as e:
            print(f"[ERROR] Alternative M2 retrieval failed: {e}")
        
        return {"m2_supply": None, "m2_date": None}

    def get_inflation_data(self):
        """Get inflation data with multiple fallbacks"""
        alpha_key = self.config["api_keys"]["alphavantage"]
        
        if alpha_key:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "CPI",
                "interval": "monthly", 
                "apikey": alpha_key
            }
            
            try:
                data = self.resilient_request(url, params)
                if data and "data" in data and len(data["data"]) > 0:
                    latest = data["data"][0]
                    current = float(latest["value"])
                    
                    # Calculate YoY inflation
                    for entry in data["data"]:
                        if entry["date"][:4] == str(int(latest["date"][:4]) - 1) and entry["date"][5:7] == latest["date"][5:7]:
                            prev_year = float(entry["value"])
                            yoy_inflation = ((current - prev_year) / prev_year) * 100
                            return {
                                "inflation_rate": yoy_inflation,
                                "inflation_date": latest["date"]
                            }
            except Exception as e:
                print(f"[ERROR] AlphaVantage inflation data: {e}")
        
        return self._get_inflation_alternative()

    def _get_inflation_alternative(self):
        """Alternative inflation data source"""
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
                                    return {
                                        "inflation_rate": rate,
                                        "inflation_date": f"{datetime.now().year}-{datetime.now().month:02d}"
                                    }
                                except ValueError:
                                    continue
        except Exception as e:
            print(f"[ERROR] Alternative inflation retrieval failed: {e}")
        
        return {"inflation_rate": None, "inflation_date": None}

    def get_interest_rates(self):
        """Get interest rates from multiple sources"""
        alpha_key = self.config["api_keys"]["alphavantage"]
        
        # Try AlphaVantage first
        if alpha_key:
            try:
                url = "https://www.alphavantage.co/query"
                
                # Get Fed Funds Rate
                params = {"function": "FEDERAL_FUNDS_RATE", "interval": "daily", "apikey": alpha_key}
                fed_data = self.resilient_request(url, params)
                
                # Get 10Y Treasury
                params = {"function": "TREASURY_YIELD", "interval": "daily", "maturity": "10year", "apikey": alpha_key}
                treasury_data = self.resilient_request(url, params)
                
                # Check if both responses have expected data structure
                if (fed_data and "data" in fed_data and len(fed_data["data"]) > 0 and 
                    treasury_data and "data" in treasury_data and len(treasury_data["data"]) > 0):
                    try:
                        return {
                            "fed_rate": float(fed_data["data"][0]["value"]),
                            "t10_yield": float(treasury_data["data"][0]["value"]),
                            "rate_date": fed_data["data"][0]["date"]
                        }
                    except (KeyError, ValueError, IndexError) as parse_error:
                        print(f"[ERROR] AlphaVantage data parsing: {parse_error}")
                else:
                    print("[WARN] AlphaVantage interest rates: Invalid response structure - missing 'data' key or empty data")
                    if fed_data:
                        print(f"[DEBUG] Fed response keys: {list(fed_data.keys())}")
                    if treasury_data:
                        print(f"[DEBUG] Treasury response keys: {list(treasury_data.keys())}")
                        
            except Exception as e:
                print(f"[ERROR] AlphaVantage interest rates: {e}")
        
        # Fallback to Yahoo Finance
        try:
            rates = {}
            tickers = {"^TNX": "t10_yield", "^FVX": "t5_yield"}
            
            for ticker, key in tickers.items():
                try:
                    data = yf.Ticker(ticker).history(period="1d")
                    if not data.empty:
                        rates[key] = data['Close'].iloc[-1]
                except Exception as e:
                    print(f"[ERROR] Failed to get {ticker}: {e}")
            
            # Try to get Fed rate from FRED website
            try:
                url = "https://fred.stlouisfed.org/series/FEDFUNDS"
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                value_text = soup.select_one('.series-meta-observation-value')
                
                if value_text:
                    rates["fed_rate"] = float(re.sub(r'[^\d.]', '', value_text.text.strip()))
            except Exception as e:
                print(f"[ERROR] Fed rate scraping: {e}")
            
            if rates:
                rates["rate_date"] = datetime.now().strftime("%Y-%m-%d")
                return rates
                
        except Exception as e:
            print(f"[ERROR] Interest rate fallback: {e}")
        
        return {"fed_rate": None, "t10_yield": None, "rate_date": None}

    def get_stock_indices(self):
        """Get stock market indices data"""
        if not self.config["indicators"]["include_stock_indices"]:
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
                    print(f"[ERROR] Failed to get {ticker}: {e}")
                    continue
            
            if indices:
                indices["indices_date"] = datetime.now().strftime("%Y-%m-%d")
                
        except Exception as e:
            print(f"[ERROR] Stock indices: {e}")
        
        return indices

    def get_commodity_prices(self):
        """Get commodity prices"""
        if not self.config["indicators"]["include_commodities"]:
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
                    print(f"[ERROR] Failed to get {ticker}: {e}")
                    continue
                    
            if commodities:
                commodities["commodities_date"] = datetime.now().strftime("%Y-%m-%d")
                
        except Exception as e:
            print(f"[ERROR] Commodity prices: {e}")
        
        return commodities

    def get_crypto_social_metrics(self):
        """Get crypto social metrics"""
        if not self.config["indicators"]["include_social_metrics"]:
            return {}
            
        mentions = {}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        # Get forum stats
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
            print(f"[ERROR] Forum stats: {e}")
        
        # Get GitHub stats
        try:
            repos = {
                "bitcoin/bitcoin": "btc_github_stars",
                "ethereum/go-ethereum": "eth_github_stars"
            }
            
            for repo, key in repos.items():
                try:
                    url = f"https://api.github.com/repos/{repo}"
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        mentions[key] = data.get("stargazers_count")
                        
                        # Get recent commits
                        commits_url = f"https://api.github.com/repos/{repo}/commits"
                        commits_response = requests.get(commits_url, headers=headers, timeout=10)
                        if commits_response.status_code == 200:
                            recent_commits = len(commits_response.json())
                            coin = "btc" if "bitcoin" in repo else "eth"
                            mentions[f"{coin}_recent_commits"] = recent_commits
                except Exception as e:
                    print(f"[ERROR] GitHub stats for {repo}: {e}")
                    
        except Exception as e:
            print(f"[ERROR] GitHub stats: {e}")
        
        if mentions:
            mentions["social_date"] = datetime.now().strftime("%Y-%m-%d")
            
        return mentions

    # ----------------------------
    # Crypto Market Data
    # ----------------------------
    def get_crypto_data(self):
        """Get basic crypto price data from Binance (replacing CoinGecko)"""
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            symbols = ["BTCUSDT", "ETHUSDT"]
            
            data = {}
            for symbol in symbols:
                params = {"symbol": symbol}
                result = self.resilient_request(url, params=params)
                if result and "price" in result:
                    price = float(result["price"])
                    if symbol == "BTCUSDT":
                        data["btc"] = price
                    elif symbol == "ETHUSDT":
                        data["eth"] = price
            
            if data.get("btc") and data.get("eth"):
                print(f"[INFO] ✅ Crypto prices from Binance: BTC ${data['btc']:,.0f}, ETH ${data['eth']:,.0f}")
                return data
            else:
                print("[WARN] ⚠️ Incomplete crypto price data from Binance")
                return {"btc": None, "eth": None}
                
        except Exception as e:
            print(f"[ERROR] Binance crypto price retrieval failed: {e}")
            return {"btc": None, "eth": None}

    def get_futures_sentiment(self):
        """Get futures market sentiment data"""
        base_url = "https://fapi.binance.com"
        symbols = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
        data = {}
        
        def get_funding(symbol):
            try:
                url = f"{base_url}/fapi/v1/premiumIndex"
                result = self.resilient_request(url, {"symbol": symbol})
                if result and "lastFundingRate" in result:
                    return float(result["lastFundingRate"]) * 100
                else:
                    print(f"[WARN] No funding rate data for {symbol}")
                    return None
            except Exception as e:
                print(f"[ERROR] Funding rate for {symbol}: {e}")
                return None
            
        def get_ratio(symbol):
            try:
                url = f"{base_url}/futures/data/topLongShortAccountRatio"
                result = self.resilient_request(url, {"symbol": symbol, "period": "1d", "limit": 1})
                if result and len(result) > 0 and "longAccount" in result[0] and "shortAccount" in result[0]:
                    return float(result[0]["longAccount"]), float(result[0]["shortAccount"])
                else:
                    print(f"[WARN] No long/short ratio data for {symbol}")
                    return None, None
            except Exception as e:
                print(f"[ERROR] Long/short ratio for {symbol}: {e}")
                return None, None
            
        def get_oi(symbol):
            try:
                url = f"{base_url}/futures/data/openInterestHist"
                result = self.resilient_request(url, {"symbol": symbol, "period": "5m", "limit": 1})
                if result and len(result) > 0 and "sumOpenInterestValue" in result[0]:
                    return float(result[0]["sumOpenInterestValue"])
                else:
                    print(f"[WARN] No open interest data for {symbol}")
                    return None
            except Exception as e:
                print(f"[ERROR] Open interest for {symbol}: {e}")
                return None
        
        # Use smaller thread pool to reduce concurrent load on Binance API
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for sym, label in symbols.items():
                futures[f"{label}_funding"] = executor.submit(get_funding, sym)
                futures[f"{label}_ratio"] = executor.submit(get_ratio, sym)
                futures[f"{label}_oi"] = executor.submit(get_oi, sym)
                # Add small delay between submissions to spread load
                time.sleep(0.2)
            
            for sym, label in symbols.items():
                try:
                    funding = futures[f"{label}_funding"].result(timeout=30)
                    long_ratio, short_ratio = futures[f"{label}_ratio"].result(timeout=30)
                    oi = futures[f"{label}_oi"].result(timeout=30)
                    
                    data[label] = {
                        "funding_rate": funding,
                        "long_ratio": long_ratio,
                        "short_ratio": short_ratio,
                        "open_interest": oi
                    }
                    
                    data[f"{label.lower()}_funding"] = funding
                    
                except concurrent.futures.TimeoutError:
                    print(f"[ERROR] Timeout getting futures data for {label}")
                    data[label] = {
                        "funding_rate": None,
                        "long_ratio": None,
                        "short_ratio": None,
                        "open_interest": None
                    }
                except Exception as e:
                    print(f"[ERROR] Processing futures data for {label}: {e}")
                    data[label] = {
                        "funding_rate": None,
                        "long_ratio": None,
                        "short_ratio": None,
                        "open_interest": None
                    }
                
        return data

    def get_fear_greed_index(self):
        """Get Fear & Greed index"""
        try:
            data = self.resilient_request("https://api.alternative.me/fng/")
            if data:
                return {
                    "index": int(data["data"][0]["value"]), 
                    "sentiment": data["data"][0]["value_classification"]
                }
        except Exception as e:
            print(f"[ERROR] Fear & Greed: {e}")
        return {"index": None, "sentiment": None}

    def get_btc_dominance(self):
        """Get BTC dominance"""
        try:
            # Use the combined global data call to avoid duplicate API requests
            global_data = self._get_global_data()
            if global_data:
                return global_data.get("btc_dominance")
        except Exception as e:
            print(f"[ERROR] BTC Dominance: {e}")
        return None

    def get_global_market_cap(self):
        """Get global crypto market cap"""
        try:
            # Use the combined global data call to avoid duplicate API requests
            global_data = self._get_global_data()
            if global_data:
                return global_data.get("market_cap"), global_data.get("market_cap_change")
        except Exception as e:
            print(f"[ERROR] Global Market Cap: {e}")
        return None, None

    def _get_global_data(self):
        """Get global data from CoinGecko (cached to avoid duplicate calls)"""
        if not hasattr(self, '_global_data_cache'):
            self._global_data_cache = None
            self._global_data_timestamp = 0
        
        # Cache for 30 seconds to avoid duplicate calls
        current_time = time.time()
        if (self._global_data_cache is not None and 
            current_time - self._global_data_timestamp < 30):
            return self._global_data_cache
        
        try:
            data = self.resilient_request("https://api.coingecko.com/api/v3/global")
            if data and "data" in data:
                self._global_data_cache = {
                    "btc_dominance": data["data"]["market_cap_percentage"]["btc"],
                    "market_cap": data["data"]["total_market_cap"]["usd"],
                    "market_cap_change": data["data"]["market_cap_change_percentage_24h_usd"]
                }
                self._global_data_timestamp = current_time
                return self._global_data_cache
        except Exception as e:
            print(f"[ERROR] Global data retrieval: {e}")
        
        return None

    def get_trading_volumes(self):
        """Get trading volumes from Binance (replacing CoinGecko)"""
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            symbols = ["BTCUSDT", "ETHUSDT"]
            
            volumes = {}
            for symbol in symbols:
                params = {"symbol": symbol}
                result = self.resilient_request(url, params=params)
                if result and "volume" in result and "quoteVolume" in result:
                    # quoteVolume is the volume in USDT (quote currency)
                    volume_usdt = float(result["quoteVolume"])
                    if symbol == "BTCUSDT":
                        volumes["btc_volume"] = volume_usdt
                        volumes["bitcoin"] = volume_usdt
                    elif symbol == "ETHUSDT":
                        volumes["eth_volume"] = volume_usdt
                        volumes["ethereum"] = volume_usdt
            
            if volumes.get("btc_volume") and volumes.get("eth_volume"):
                print(f"[INFO] ✅ Trading volumes from Binance: BTC ${volumes['btc_volume']/1e9:.1f}B, ETH ${volumes['eth_volume']/1e9:.1f}B")
                return volumes
            else:
                print("[WARN] ⚠️ Incomplete volume data from Binance")
                return {"btc_volume": None, "eth_volume": None}
                
        except Exception as e:
            print(f"[ERROR] Binance volume retrieval failed: {e}")
            return {"btc_volume": None, "eth_volume": None}

    def get_technical_indicators(self):
        """Get comprehensive technical indicators"""
        url = "https://api.binance.com/api/v3/klines"
        symbols = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
        indicators = {}
        
        print("\n[DEBUG] Starting technical analysis...")
        
        for symbol, label in symbols.items():
            try:
                print(f"\n[DEBUG] Analyzing {label}...")
                
                params = {
                    "symbol": symbol,
                    "interval": "1d",
                    "limit": 50
                }
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                
                data = self.resilient_request(url, params=params, headers=headers)
                if not data:
                    print(f"[ERROR] No data received for {label}")
                    continue
                
                # Extract price data
                closes = [float(k[4]) for k in data]
                highs = [float(k[2]) for k in data]
                lows = [float(k[3]) for k in data]
                volumes = [float(k[5]) for k in data]
                
                current_price = closes[-1]
                
                # Calculate moving averages
                sma7 = sum(closes[-7:]) / 7
                sma14 = sum(closes[-14:]) / 14
                sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
                
                # Calculate RSI
                changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                gains = [max(0, c) for c in changes]
                losses = [max(0, -c) for c in changes]
                avg_gain = sum(gains[-14:]) / 14
                avg_loss = sum(losses[-14:]) / 14
                rs = avg_gain / avg_loss if avg_loss != 0 else 1e10
                rsi = 100 - (100 / (1 + rs))
                
                # Calculate support and resistance levels
                recent_highs = highs[-20:]
                recent_lows = lows[-20:]
                
                resistance_levels = []
                support_levels = []
                
                for i in range(1, len(recent_highs)-1):
                    if recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i+1]:
                        resistance_levels.append(recent_highs[i])
                    if recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i+1]:
                        support_levels.append(recent_lows[i])
                
                nearest_support = max([s for s in support_levels if s < current_price], default=current_price * 0.95)
                nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.05)
                
                # Calculate ATR
                tr_values = []
                for i in range(1, len(closes)):
                    tr = max(
                        highs[i] - lows[i],
                        abs(highs[i] - closes[i-1]),
                        abs(lows[i] - closes[i-1])
                    )
                    tr_values.append(tr)
                atr = sum(tr_values[-14:]) / 14
                
                # Calculate ATR-based support and resistance levels
                atr_support = current_price - (1.5 * atr) if atr > 0 else current_price * 0.98
                atr_resistance = current_price + (1.5 * atr) if atr > 0 else current_price * 1.02
                
                # Calculate SMA-based support and resistance levels
                sma_support = sma14 * 0.98
                sma_resistance = sma14 * 1.02
                
                # Determine trend
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
                
                # RSI zones
                rsi_zone = "neutral"
                if rsi > 60:
                    rsi_zone = "bullish"
                elif rsi < 40:
                    rsi_zone = "bearish"
                
                # Volume trend
                avg_volume = sum(volumes[-5:]) / 5
                volume_trend = "increasing" if volumes[-1] > avg_volume * 1.2 else "decreasing" if volumes[-1] < avg_volume * 0.8 else "stable"
                
                # Generate signal
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
                
                # Adjust confidence based on RSI and volume
                rsi_factor = 1.2 if rsi > 70 and trend.startswith("bear") else 1.2 if rsi < 30 and trend.startswith("bull") else 1.0
                volume_factor = 1.2 if volume_trend == "increasing" else 0.8 if volume_trend == "decreasing" else 1.0
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
                
                # Calculate TP/SL levels
                leverage = 13.5
                strategy = "scalp"
                
                trend_bias = "with" if (
                    (signal in ["BUY", "STRONG BUY"] and trend.startswith("bull")) or
                    (signal in ["SELL", "STRONG SELL"] and trend.startswith("bear"))
                ) else "against"
                
                rrr = 3 if trend_bias == "with" else 1.5
                sl_atr_mult = 0.7 if strategy == "scalp" else 1.0
                
                if signal in ["BUY", "STRONG BUY"]:
                    entry_low = nearest_support
                    entry_high = current_price
                    sl = min(entry_low - sl_atr_mult * atr, nearest_support * 0.98)
                    risk = abs(entry_high - sl)
                    tp1 = min(entry_high + rrr * risk, nearest_resistance * 1.01)
                    tp2 = min(entry_high + (rrr+1) * risk, nearest_resistance * 1.02)
                elif signal in ["SELL", "STRONG SELL"]:
                    entry_low = current_price
                    entry_high = nearest_resistance
                    sl = max(entry_high + sl_atr_mult * atr, nearest_resistance * 1.005)
                    risk = abs(entry_low - sl)
                    tp1 = max(entry_low - rrr * risk, nearest_support * 0.99)
                    tp2 = max(entry_low - (rrr+1) * risk, nearest_support * 0.98)
                else:
                    entry_low = current_price * 0.99
                    entry_high = current_price * 1.01
                    tp1 = current_price
                    tp2 = current_price
                    sl = current_price
                
                # Calculate volatility and risk level
                volatility = "high" if atr > current_price * 0.03 else "medium" if atr > current_price * 0.015 else "low"
                volatility_factor = 1.5 if volatility == "high" else 1.0 if volatility == "medium" else 0.5
                risk_level = min(10, max(1, (volatility_factor * (signal_confidence / 10)) * 10))
                
                # Structure the indicators
                indicators[label] = {
                    "price": current_price,
                    "sma7": sma7,
                    "sma14": sma14,
                    "sma50": sma50,
                    "rsi14": rsi,
                    "trend": trend,
                    "rsi_zone": rsi_zone,
                    "volume_trend": volume_trend,
                    "signal": signal,
                    "signal_confidence": signal_confidence,
                    "support": nearest_support,           # PRIMARY - Pivot point method
                    "resistance": nearest_resistance,     # PRIMARY - Pivot point method
                    "atr_support": atr_support,          # REFERENCE - ATR method
                    "atr_resistance": atr_resistance,    # REFERENCE - ATR method
                    "sma_support": sma_support,          # REFERENCE - SMA method
                    "sma_resistance": sma_resistance,    # REFERENCE - SMA method
                    "atr": atr,                          # Raw ATR for risk management
                    "volatility": volatility,
                    "risk_level": risk_level,
                    "key_levels": {
                        "entry_range": f"${entry_low:,.0f} - ${entry_high:,.0f}",
                        "tp1": tp1,
                        "tp2": tp2,
                        "sl": sl,
                        "rrr1": abs(tp1 - current_price) / abs(current_price - sl) if sl != current_price else 0,
                        "rrr2": abs(tp2 - current_price) / abs(current_price - sl) if sl != current_price else 0
                    }
                }
                
                # Add individual indicators for easy access
                indicators[f"{label.lower()}_rsi"] = rsi
                indicators[f"{label.lower()}_trend"] = trend
                indicators[f"{label.lower()}_signal"] = signal
                indicators[f"{label.lower()}_signal_confidence"] = signal_confidence
                indicators[f"{label.lower()}_support"] = nearest_support
                indicators[f"{label.lower()}_resistance"] = nearest_resistance
                
                print(f"[DEBUG] {label} - Price: ${current_price:,.2f}, RSI: {rsi:.1f}, Signal: {signal}")
                
                # Add delay between API calls to be respectful to Binance servers
                # Increased delay for Render.com to prevent rate limiting
                if symbol != "ETHUSDT":  # Don't delay after the last symbol
                    time.sleep(2.0)  # Increased from 0.5s to 2.0s for better rate limiting
                
            except Exception as e:
                print(f"[ERROR] Technicals {label}: {e}")
                continue
        
        return indicators

    def get_historical_price_data(self):
        """Get extended historical price data with additional indicators"""
        tickers = ["BTC-USD", "ETH-USD"]
        timeframes = ["1h", "4h", "1d", "1wk", "1mo"]
        
        historical_data = {}
        for ticker in tickers:
            ticker_data = {}
            for timeframe in timeframes:
                interval = timeframe
                if timeframe == "1h":
                    period = "2d"
                elif timeframe == "4h":
                    period = "7d"
                elif timeframe == "1d":
                    period = "6mo"
                elif timeframe == "1wk":
                    period = "2y"
                    interval = "1wk"
                elif timeframe == "1mo":
                    period = "10y"
                    interval = "1mo"
                    
                try:
                    data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
                    if data.empty:
                        continue
                        
                    # Calculate ATR
                    data['tr1'] = abs(data['High'] - data['Low'])
                    data['tr2'] = abs(data['High'] - data['Close'].shift())
                    data['tr3'] = abs(data['Low'] - data['Close'].shift())
                    data['TR'] = data[['tr1', 'tr2', 'tr3']].max(axis=1)
                    data['ATR'] = data['TR'].rolling(14).mean()
                    
                    # Additional indicators for longer timeframes
                    if timeframe in ["1d", "1wk", "1mo"]:
                        data['SMA20'] = data['Close'].rolling(20).mean()
                        data['SMA50'] = data['Close'].rolling(50).mean()
                        data['SMA200'] = data['Close'].rolling(200).mean()
                        
                        # RSI
                        delta = data['Close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        data['RSI'] = 100 - (100 / (1 + rs))
                        
                        # MACD
                        ema12 = data['Close'].ewm(span=12).mean()
                        ema26 = data['Close'].ewm(span=26).mean()
                        data['MACD'] = ema12 - ema26
                        data['MACD_Signal'] = data['MACD'].ewm(span=9).mean()
                        data['MACD_Histogram'] = data['MACD'] - data['MACD_Signal']
                    
                    # Convert to JSON-serializable format
                    result_data = {
                        'timestamps': list(data.index.strftime('%Y-%m-%d %H:%M:%S')),
                        'open': data['Open'].values.tolist(),
                        'high': data['High'].values.tolist(),
                        'low': data['Low'].values.tolist(),
                        'close': data['Close'].values.tolist(),
                        'volume': data['Volume'].values.tolist(),
                        'atr': data['ATR'].values.tolist()
                    }
                    
                    if timeframe in ["1d", "1wk", "1mo"]:
                        result_data.update({
                            'sma20': data['SMA20'].values.tolist(),
                            'sma50': data['SMA50'].values.tolist(),
                            'sma200': data['SMA200'].values.tolist(),
                            'rsi': data['RSI'].values.tolist(),
                            'macd': data['MACD'].values.tolist(),
                            'macd_signal': data['MACD_Signal'].values.tolist(),
                            'macd_histogram': data['MACD_Histogram'].values.tolist()
                        })
                    
                    ticker_data[timeframe] = result_data
                    print(f"[INFO] Historical data: {ticker} {timeframe} - {len(data)} candles")
                    
                except Exception as e:
                    print(f"[ERROR] Failed {timeframe} data for {ticker}: {e}")
                    continue
                    
            historical_data[ticker.split('-')[0]] = ticker_data
        
        return historical_data

    # ----------------------------
    # NEW ENHANCED DATA COLLECTION  
    # ----------------------------
    
    def get_volatility_regime(self):
        """Get current volatility regime for dynamic position sizing"""
        print("[INFO] Collecting volatility regime analysis...")
        
        try:
            # Get recent volatility data for BTC and ETH
            symbols = ['BTCUSDT', 'ETHUSDT']
            volatility_data = {}
            
            for symbol in symbols:
                url = "https://api.binance.com/api/v3/klines"
                params = {
                    'symbol': symbol,
                    'interval': '1h',
                    'limit': 168  # 7 days of hourly data
                }
                
                data = self.resilient_request(url, params)
                if not data:
                    continue
                    
                # Calculate hourly returns
                closes = [float(candle[4]) for candle in data]
                returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
                
                # Calculate rolling volatility (24h windows)
                window_size = 24
                volatilities = []
                for i in range(window_size, len(returns)):
                    window_returns = returns[i-window_size:i]
                    volatility = np.std(window_returns) * np.sqrt(24)  # Annualized
                    volatilities.append(volatility)
                
                current_volatility = volatilities[-1] if volatilities else 0
                avg_volatility = np.mean(volatilities) if volatilities else 0
                
                coin = symbol.replace('USDT', '')
                volatility_data[coin] = {
                    'current_volatility': current_volatility,
                    'average_volatility': avg_volatility,
                    'volatility_ratio': current_volatility / avg_volatility if avg_volatility > 0 else 1.0
                }
            
            # Calculate overall regime
            if volatility_data:
                # Use BTC as primary reference
                btc_ratio = volatility_data.get('BTC', {}).get('volatility_ratio', 1.0)
                eth_ratio = volatility_data.get('ETH', {}).get('volatility_ratio', 1.0)
                avg_ratio = (btc_ratio + eth_ratio) / 2
                
                # Classify regime
                if avg_ratio > 2.5:
                    regime = "EXTREME"
                    size_multiplier = 0.3
                    risk_state = "VERY_HIGH"
                elif avg_ratio > 1.8:
                    regime = "HIGH"
                    size_multiplier = 0.5
                    risk_state = "HIGH"
                elif avg_ratio > 1.3:
                    regime = "ELEVATED"
                    size_multiplier = 0.7
                    risk_state = "MEDIUM_HIGH"
                elif avg_ratio > 0.7:
                    regime = "NORMAL"
                    size_multiplier = 1.0
                    risk_state = "NORMAL"
                else:
                    regime = "LOW"
                    size_multiplier = 1.3
                    risk_state = "LOW"
                
                return {
                    'current_regime': regime,
                    'size_multiplier': size_multiplier,
                    'risk_state': risk_state,
                    'volatility_ratio': avg_ratio,
                    'btc_volatility': volatility_data.get('BTC', {}),
                    'eth_volatility': volatility_data.get('ETH', {})
                }
        
        except Exception as e:
            print(f"[ERROR] Volatility regime calculation failed: {e}")
        
        # Return default regime if calculation fails
        return {
            'current_regime': 'NORMAL',
            'size_multiplier': 1.0,
            'risk_state': 'UNKNOWN',
            'volatility_ratio': 1.0
        }
    
    def get_order_book_analysis(self):
        """Get advanced order book analysis for both BTC and ETH"""
        print("[INFO] Collecting order book analysis...")
        
        if not self.binance_api_key or not self.binance_secret:
            print("[WARN] ⚠️  Binance API keys not configured - Order book analysis unavailable")
            return None
        
        try:
            symbols = ['BTCUSDT', 'ETHUSDT']
            order_book_data = {}
            
            for symbol in symbols:
                url = "https://api.binance.com/api/v3/depth"
                params = {'symbol': symbol, 'limit': 100}
                
                data = self.resilient_request(url, params)
                if not data:
                    continue
                    
                bids = [(float(bid[0]), float(bid[1])) for bid in data.get('bids', [])]
                asks = [(float(ask[0]), float(ask[1])) for ask in data.get('asks', [])]
                
                if not bids or not asks:
                    continue
                    
                current_price = (bids[0][0] + asks[0][0]) / 2
                
                # Calculate weighted book depth
                bid_depth = sum(price * volume for price, volume in bids[:50])
                ask_depth = sum(price * volume for price, volume in asks[:50])
                total_depth = bid_depth + ask_depth
                
                imbalance_ratio = bid_depth / total_depth if total_depth > 0 else 0.5
                
                # Find significant walls
                avg_bid_size = np.mean([vol for _, vol in bids[:20]])
                avg_ask_size = np.mean([vol for _, vol in asks[:20]])
                
                bid_walls = [(price, vol) for price, vol in bids if vol > avg_bid_size * 10]
                ask_walls = [(price, vol) for price, vol in asks if vol > avg_ask_size * 10]
                
                # Calculate support/resistance from walls
                strong_support = min([price for price, vol in bid_walls], default=current_price * 0.99)
                strong_resistance = max([price for price, vol in ask_walls], default=current_price * 1.01)
                
                # Market maker vs retail analysis
                small_orders = sum(1 for _, vol in bids[:20] + asks[:20] if vol < 1.0)
                large_orders = sum(1 for _, vol in bids[:20] + asks[:20] if vol > 10.0)
                mm_dominance = large_orders / (small_orders + large_orders) if (small_orders + large_orders) > 0 else 0
                
                # Generate signal
                if imbalance_ratio > 0.7:
                    book_signal = "BULLISH"
                elif imbalance_ratio < 0.3:
                    book_signal = "BEARISH"
                else:
                    book_signal = "NEUTRAL"
                
                coin = symbol.replace('USDT', '')
                order_book_data[coin] = {
                    'current_price': current_price,
                    'imbalance_ratio': imbalance_ratio,
                    'bid_walls': len(bid_walls),
                    'ask_walls': len(ask_walls),
                    'strong_support': strong_support,
                    'strong_resistance': strong_resistance,
                    'mm_dominance': mm_dominance,
                    'book_signal': book_signal
                }
            
            return order_book_data if order_book_data else None
            
        except Exception as e:
            print(f"[ERROR] Order book analysis failed: {e}")
            return None

    def get_liquidation_heatmap(self):
        """Get liquidation heatmap for both BTC and ETH"""
        print("[INFO] Collecting liquidation heatmap...")
        
        if not self.binance_api_key or not self.binance_secret:
            print("[WARN] ⚠️  Binance API keys not configured - Liquidation heatmap unavailable")
            return None
        
        try:
            symbols = ['BTCUSDT', 'ETHUSDT']
            liquidation_data = {}
            
            for symbol in symbols:
                # Get current price
                ticker_resp = self.resilient_request("https://api.binance.com/api/v3/ticker/price", 
                                                   {'symbol': symbol})
                current_price = float(ticker_resp['price']) if ticker_resp else 0
                
                # Get funding rate for liquidation pressure
                funding_resp = self.resilient_request("https://fapi.binance.com/fapi/v1/premiumIndex", 
                                                    {'symbol': symbol})
                funding_rate = float(funding_resp.get('lastFundingRate', 0)) * 100 if funding_resp else 0
                
                # Get open interest
                oi_resp = self.resilient_request("https://fapi.binance.com/fapi/v1/openInterest", 
                                               {'symbol': symbol})
                open_interest = float(oi_resp.get('openInterest', 0)) if oi_resp else 0
                
                # Calculate liquidation zones (simplified estimation)
                leverage_levels = [10, 20, 50, 100]
                liquidation_zones = []
                
                for leverage in leverage_levels:
                    # Long liquidation (price moves down)
                    long_liq_price = current_price * (1 - 0.9/leverage)
                    # Short liquidation (price moves up)  
                    short_liq_price = current_price * (1 + 0.9/leverage)
                    
                    liquidation_zones.append({
                        'leverage': leverage,
                        'long_liquidation': long_liq_price,
                        'short_liquidation': short_liq_price
                    })
                
                # Estimate liquidation pressure based on funding
                if funding_rate > 0.05:
                    liq_pressure = "HIGH_LONG_LIQUIDATION_RISK"
                    pressure_score = 0.7
                elif funding_rate < -0.05:
                    liq_pressure = "HIGH_SHORT_LIQUIDATION_RISK"
                    pressure_score = -0.7
                elif abs(funding_rate) > 0.02:
                    liq_pressure = "MODERATE_LIQUIDATION_RISK"
                    pressure_score = 0.3 if funding_rate > 0 else -0.3
                else:
                    liq_pressure = "LOW_LIQUIDATION_RISK"
                    pressure_score = 0.0
                
                # Find nearby magnet zones
                nearby_long_liqs = [zone['long_liquidation'] for zone in liquidation_zones 
                                  if abs(zone['long_liquidation'] - current_price) / current_price < 0.05]
                nearby_short_liqs = [zone['short_liquidation'] for zone in liquidation_zones 
                                   if abs(zone['short_liquidation'] - current_price) / current_price < 0.05]
                
                coin = symbol.replace('USDT', '')
                liquidation_data[coin] = {
                    'current_price': current_price,
                    'funding_rate': funding_rate,
                    'open_interest': open_interest,
                    'liquidation_pressure': liq_pressure,
                    'pressure_score': pressure_score,
                    'nearby_long_liquidations': nearby_long_liqs,
                    'nearby_short_liquidations': nearby_short_liqs
                }
            
            return liquidation_data if liquidation_data else None
            
        except Exception as e:
            print(f"[ERROR] Liquidation heatmap failed: {e}")
            return None

    def get_economic_calendar(self):
        """Get economic calendar events from CoinMarketCal"""
        print("[INFO] Collecting economic calendar events...")
        
        if not self.coinmarketcal_key:
            print("[WARN] ⚠️  CoinMarketCal API key not configured - Economic calendar unavailable")
            return None
        
        try:
            url = "https://developers.coinmarketcal.com/v1/events"
            
            headers = {
                'x-api-key': self.coinmarketcal_key,
                'Accept': 'application/json',
                'Accept-Encoding': 'deflate, gzip',
                'User-Agent': 'Mozilla/5.0 (compatible; CryptoBot/1.0)'
            }
            
            end_date = datetime.now() + timedelta(days=7)
            params = {
                'dateRangeStart': datetime.now().strftime('%Y-%m-%d'),
                'dateRangeEnd': end_date.strftime('%Y-%m-%d'),
                'sortBy': 'created_desc',
                'max': 50
            }
            
            data = self.resilient_request(url, params, headers)
            if not data or 'body' not in data:
                return None
                
            events = data['body']
            if not isinstance(events, list):
                return None
            
            # Process events
            high_impact_events = []
            medium_impact_events = []
            crypto_specific_events = []
            
            now = datetime.now()
            
            for event in events:
                try:
                    title = event.get('title', {})
                    if isinstance(title, dict):
                        title_text = title.get('en', 'Unknown Event')
                    else:
                        title_text = str(title)
                    
                    date_str = event.get('date_event', '')
                    try:
                        event_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        event_date = event_date.replace(tzinfo=None)
                    except:
                        continue
                    
                    if event_date < now:
                        continue
                    
                    percentage = float(event.get('percentage', 0))
                    hot_score = float(event.get('hot_score', 0))
                    votes = int(event.get('votes', 0))
                    
                    impact_score = (percentage * 0.4) + (hot_score * 0.4) + (min(votes, 100) * 0.2)
                    
                    coins = event.get('coins', [])
                    is_crypto_specific = any('bitcoin' in str(coin).lower() or 'ethereum' in str(coin).lower() 
                                           for coin in coins) if coins else False
                    
                    event_data = {
                        'title': title_text,
                        'date': date_str,
                        'event_date': event_date,
                        'impact_score': impact_score,
                        'is_crypto_specific': is_crypto_specific,
                        'days_ahead': (event_date - now).days
                    }
                    
                    if impact_score > 70 or percentage > 80:
                        high_impact_events.append(event_data)
                    elif impact_score > 40 or percentage > 50:
                        medium_impact_events.append(event_data)
                        
                    if is_crypto_specific:
                        crypto_specific_events.append(event_data)
                        
                except Exception:
                    continue
            
            # Generate recommendation
            recommendation = "NORMAL_TRADING"
            if any(e['days_ahead'] <= 1 for e in high_impact_events):
                recommendation = "AVOID_TRADING_HIGH_VOLATILITY"
            elif any(e['days_ahead'] <= 2 for e in high_impact_events):
                recommendation = "REDUCE_POSITION_SIZE"
            elif len(medium_impact_events) > 3:
                recommendation = "MONITOR_CLOSELY"
            
            return {
                'total_events': len(events),
                'high_impact': len(high_impact_events),
                'medium_impact': len(medium_impact_events),
                'crypto_specific': len(crypto_specific_events),
                'recommendation': recommendation,
                'next_high_impact': high_impact_events[0] if high_impact_events else None
            }
            
        except Exception as e:
            print(f"[ERROR] Economic calendar failed: {e}")
            return None

    def get_multi_source_sentiment(self):
        """Get sentiment analysis from multiple sources"""
        print("[INFO] Collecting multi-source sentiment...")
        
        if not self.news_api_key:
            print("[WARN] ⚠️  News API key not configured - Limited sentiment analysis available")
        
        try:
            sentiment_scores = []
            
            # News sentiment
            try:
                if self.news_api_key:
                    news_url = "https://newsapi.org/v2/everything"
                    news_params = {
                        'q': 'bitcoin OR cryptocurrency',
                        'language': 'en',
                        'sortBy': 'publishedAt',
                        'pageSize': 20,
                        'apiKey': self.news_api_key
                    }
                    
                    news_data = self.resilient_request(news_url, news_params)
                    if news_data and 'articles' in news_data:
                        news_sentiment = self._analyze_news_sentiment(news_data['articles'])
                        sentiment_scores.append(('news', news_sentiment))
                
            except Exception as e:
                print(f"[WARN] News sentiment failed: {e}")
            
            # Market-based sentiment
            try:
                social_sentiment = self._analyze_market_sentiment()
                if social_sentiment is not None:
                    sentiment_scores.append(('social', social_sentiment))
            except Exception as e:
                print(f"[WARN] Social sentiment failed: {e}")
            
            # Fear & Greed as market sentiment
            try:
                fg_data = self.get_fear_greed_index()
                if fg_data and fg_data.get('index'):
                    fg_normalized = (fg_data['index'] - 50) / 50
                    sentiment_scores.append(('market', fg_normalized))
            except Exception as e:
                print(f"[WARN] Market sentiment failed: {e}")
            
            if not sentiment_scores:
                return None
            
            # Calculate weighted average sentiment
            avg_sentiment = sum(score for _, score in sentiment_scores) / len(sentiment_scores)
            
            if avg_sentiment > 0.3:
                sentiment_signal = "BULLISH"
            elif avg_sentiment < -0.3:
                sentiment_signal = "BEARISH"
            else:
                sentiment_signal = "NEUTRAL"
            
            return {
                'sources_analyzed': len(sentiment_scores),
                'average_sentiment': avg_sentiment,
                'sentiment_signal': sentiment_signal,
                'source_breakdown': dict(sentiment_scores)
            }
            
        except Exception as e:
            print(f"[ERROR] Multi-source sentiment failed: {e}")
            return None

    def _analyze_news_sentiment(self, articles):
        """Analyze sentiment from news articles"""
        if not articles:
            return 0.0
        
        try:
            positive_keywords = ['bull', 'bullish', 'surge', 'rally', 'gains', 'breakout', 'adoption', 'institutional']
            negative_keywords = ['bear', 'bearish', 'crash', 'dump', 'decline', 'regulatory', 'ban', 'hack']
            
            sentiment_scores = []
            
            for article in articles[:10]:
                title = article.get('title', '').lower()
                description = article.get('description', '').lower()
                text = f"{title} {description}"
                
                positive_count = sum(1 for word in positive_keywords if word in text)
                negative_count = sum(1 for word in negative_keywords if word in text)
                
                if positive_count > 0 or negative_count > 0:
                    score = (positive_count - negative_count) / (positive_count + negative_count)
                    sentiment_scores.append(score)
            
            return np.mean(sentiment_scores) if sentiment_scores else 0.0
            
        except Exception:
            return 0.0

    def _analyze_market_sentiment(self):
        """Analyze market-based sentiment indicators"""
        try:
            futures_data = self.get_futures_sentiment()
            if not futures_data:
                return None
            
            sentiment_indicators = []
            
            # BTC funding rate sentiment
            btc_funding = futures_data.get('BTC', {}).get('funding_rate', 0)
            if btc_funding:
                funding_sentiment = -btc_funding * 20
                sentiment_indicators.append(funding_sentiment)
            
            # Long/Short ratio sentiment (contrarian)
            btc_futures = futures_data.get('BTC', {})
            if btc_futures.get('long_ratio') and btc_futures.get('short_ratio'):
                ls_ratio = btc_futures['long_ratio'] / (btc_futures['short_ratio'] + 1e-6)
                if ls_ratio > 1.5:
                    ratio_sentiment = -0.3
                elif ls_ratio < 0.7:
                    ratio_sentiment = 0.3
                else:
                    ratio_sentiment = 0.0
                sentiment_indicators.append(ratio_sentiment)
            
            return np.mean(sentiment_indicators) if sentiment_indicators else 0.0
            
        except Exception:
            return None

    def get_whale_movements(self):
        """Get whale movement alerts and smart money tracking"""
        print("[INFO] Collecting whale movement data...")
        
        if not self.etherscan_api_key:
            print("[WARN] ⚠️  Etherscan API key not configured - Limited whale tracking available")
        
        try:
            whale_signals = []
            
            # Large trades detection
            large_trades_data = self._detect_large_trades()
            if large_trades_data:
                # Aggregate activity across BTC and ETH
                activities = [data.get('activity', 'UNKNOWN') for data in large_trades_data.values()]
                # Use the highest activity level
                if 'HIGH_WHALE_ACTIVITY' in activities:
                    overall_activity = 'HIGH_WHALE_ACTIVITY'
                    overall_sentiment = 0.2
                elif 'MODERATE_WHALE_ACTIVITY' in activities:
                    overall_activity = 'MODERATE_WHALE_ACTIVITY'
                    overall_sentiment = 0.1
                else:
                    overall_activity = 'LOW_WHALE_ACTIVITY'
                    overall_sentiment = 0.0
                
                large_trades_summary = {
                    'activity': overall_activity,
                    'sentiment': overall_sentiment,
                    'coins_analyzed': list(large_trades_data.keys()),
                    'total_large_trades': sum(data.get('large_trades_count', 0) for data in large_trades_data.values())
                }
                whale_signals.append(('large_trades', large_trades_summary))
            
            # Exchange flow analysis
            exchange_flows_data = self._analyze_exchange_flows()
            if exchange_flows_data:
                whale_signals.append(('exchange_flows', exchange_flows_data))
            
            if not whale_signals:
                return None
            
            # Aggregate whale sentiment
            total_sentiment = sum(data.get('sentiment', 0) for _, data in whale_signals)
            avg_sentiment = total_sentiment / len(whale_signals)
            
            if avg_sentiment > 0.3:
                whale_signal = "WHALES_ACCUMULATING"
            elif avg_sentiment < -0.3:
                whale_signal = "WHALES_DISTRIBUTING"
            else:
                whale_signal = "WHALE_NEUTRAL"
            
            return {
                'signals_detected': len(whale_signals),
                'whale_sentiment': avg_sentiment,
                'whale_signal': whale_signal,
                'breakdown': dict(whale_signals)  # Now returns {'large_trades': {'activity': '...', 'sentiment': 0.2}, 'exchange_flows': {'activity': '...', 'sentiment': 0.3}}
            }
            
        except Exception as e:
            print(f"[ERROR] Whale movements failed: {e}")
            return None

    def _detect_large_trades(self):
        """Detect large trades that might indicate whale activity"""
        try:
            # Get data for both BTC and ETH
            symbols = ['BTCUSDT', 'ETHUSDT']
            whale_data = {}
            
            for symbol in symbols:
                url = "https://api.binance.com/api/v3/aggTrades"
                params = {'symbol': symbol, 'limit': 500}
            
                data = self.resilient_request(url, params)
                if not data:
                    continue
                
                trade_sizes = []
                for trade in data:
                    price = float(trade['p'])
                    quantity = float(trade['q'])
                    value_usd = price * quantity
                    trade_sizes.append(value_usd)
                
                whale_threshold = np.percentile(trade_sizes, 95)
                large_trades = [size for size in trade_sizes if size > whale_threshold]
                
                if len(large_trades) > 0:
                    if len(large_trades) > len(trade_sizes) * 0.1:
                        activity = "HIGH_WHALE_ACTIVITY"
                        sentiment = 0.2
                    elif len(large_trades) > len(trade_sizes) * 0.05:
                        activity = "MODERATE_WHALE_ACTIVITY"
                        sentiment = 0.1
                    else:
                        activity = "LOW_WHALE_ACTIVITY"
                        sentiment = 0.0
                    
                    coin = symbol.replace('USDT', '')
                    whale_data[coin] = {
                        'activity': activity,
                        'large_trades_count': len(large_trades),
                        'whale_threshold': whale_threshold,
                        'sentiment': sentiment
                    }
            
            return whale_data if whale_data else None
            
        except Exception:
            return None

    def _analyze_exchange_flows(self):
        """Analyze exchange inflows/outflows"""
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            params = {'symbol': 'BTCUSDT'}
            
            data = self.resilient_request(url, params)
            if not data:
                return None
            
            volume_24h = float(data['volume'])
            price_change = float(data['priceChangePercent'])
            
            if volume_24h > 20000 and price_change > 2:
                activity = "POSSIBLE_ACCUMULATION"
                sentiment = 0.3
            elif volume_24h > 20000 and price_change < -2:
                activity = "POSSIBLE_DISTRIBUTION"
                sentiment = -0.3
            else:
                activity = "NORMAL_FLOWS"
                sentiment = 0.0
            
            return {
                'activity': activity,
                'volume_24h': volume_24h,
                'price_change': price_change,
                'sentiment': sentiment
            }
            
        except Exception:
            return None

    def _log_data_verbose(self, results):
        """Log all collected data points with actual values for debugging"""
        print("\n" + "="*80)
        print("📊 DETAILED DATA COLLECTION RESULTS")
        print("="*80)
        
        # Crypto Prices - USE SAME SOURCE AS AI PROMPT (technical indicators)
        tech = results.get("technical_indicators", {})
        print("\n💰 CRYPTO PRICES (from technical analysis - same as AI prompt):")
        btc_data = tech.get("BTC", {})
        eth_data = tech.get("ETH", {})
        
        if btc_data and btc_data.get("price"):
            print(f"  BTC: ${btc_data['price']:,.2f}")
        else:
            print("  BTC: ❌ MISSING")
            
        if eth_data and eth_data.get("price"):
            print(f"  ETH: ${eth_data['price']:,.2f}")
        else:
            print("  ETH: ❌ MISSING")
            
        # Technical Indicators
        print("\n📈 TECHNICAL ANALYSIS:")
        for coin in ["BTC", "ETH"]:
            coin_data = tech.get(coin, {})
            if coin_data:
                print(f"  {coin}:")
                print(f"    RSI: {coin_data.get('rsi14', 'N/A'):.1f}" if coin_data.get('rsi14') is not None else "    RSI: ❌ MISSING")
                print(f"    Signal: {coin_data.get('signal', 'N/A')}")
                print(f"    Support: ${coin_data.get('support', 'N/A'):,.0f}" if coin_data.get('support') is not None else "    Support: ❌ MISSING")
                print(f"    Resistance: ${coin_data.get('resistance', 'N/A'):,.0f}" if coin_data.get('resistance') is not None else "    Resistance: ❌ MISSING")
                print(f"    Trend: {coin_data.get('trend', 'N/A')}")
                print(f"    Volatility: {coin_data.get('volatility', 'N/A')}")
            else:
                print(f"  {coin}: ❌ MISSING")
        
        # Futures Data
        futures = results.get("futures", {})
        print("\n🔮 FUTURES SENTIMENT:")
        for coin in ["BTC", "ETH"]:
            coin_data = futures.get(coin, {})
            if coin_data:
                print(f"  {coin}:")
                funding = coin_data.get('funding_rate')
                if funding is not None:
                    print(f"    Funding Rate: {funding:.4f}%")
                else:
                    print("    Funding Rate: ❌ MISSING")
                    
                long_ratio = coin_data.get('long_ratio')
                if long_ratio is not None:
                    print(f"    Long Ratio: {long_ratio}%")
                else:
                    print("    Long Ratio: ❌ MISSING")
                    
                short_ratio = coin_data.get('short_ratio')
                if short_ratio is not None:
                    print(f"    Short Ratio: {short_ratio}%")
                else:
                    print("    Short Ratio: ❌ MISSING")
                    
                oi = coin_data.get('open_interest')
                if oi:
                    print(f"    Open Interest: ${oi:,.0f}")
                else:
                    print("    Open Interest: ❌ MISSING")
            else:
                print(f"  {coin}: ❌ MISSING")
        
        # Market Sentiment
        fear_greed = results.get("fear_greed", {})
        print("\n😱 MARKET SENTIMENT:")
        if fear_greed.get("index"):
            print(f"  Fear & Greed Index: {fear_greed['index']} ({fear_greed.get('sentiment', 'N/A')})")
        else:
            print("  Fear & Greed Index: ❌ MISSING")
            
        btc_dom = results.get("btc_dominance")
        if btc_dom:
            print(f"  BTC Dominance: {btc_dom:.2f}%")
        else:
            print("  BTC Dominance: ❌ MISSING")
            
        market_cap = results.get("market_cap")
        if market_cap and len(market_cap) == 2:
            cap, change = market_cap
            print(f"  Global Market Cap: ${cap/1e12:.2f}T ({change:+.2f}%)")
        else:
            print("  Global Market Cap: ❌ MISSING")
        
        # Trading Volumes
        volumes = results.get("volumes", {})
        print("\n📊 TRADING VOLUMES:")
        if volumes.get("btc_volume"):
            print(f"  BTC Volume: ${volumes['btc_volume']/1e9:.2f}B")
        else:
            print("  BTC Volume: ❌ MISSING")
            
        if volumes.get("eth_volume"):
            print(f"  ETH Volume: ${volumes['eth_volume']/1e9:.2f}B")
        else:
            print("  ETH Volume: ❌ MISSING")
        
        # Macroeconomic Data
        print("\n🏛️ MACROECONOMIC DATA:")
        m2 = results.get("m2_supply", {})
        if m2.get("m2_supply"):
            print(f"  M2 Money Supply: ${m2['m2_supply']/1e12:.1f}T (as of {m2.get('m2_date', 'N/A')})")
        else:
            print("  M2 Money Supply: ❌ MISSING")
            
        inflation = results.get("inflation", {})
        if inflation.get("inflation_rate") is not None:
            print(f"  Inflation Rate: {inflation['inflation_rate']:.2f}% (as of {inflation.get('inflation_date', 'N/A')})")
        else:
            print("  Inflation Rate: ❌ MISSING")
            
        rates = results.get("interest_rates", {})
        if rates.get("fed_rate") is not None:
            print(f"  Fed Funds Rate: {rates['fed_rate']:.2f}%")
        else:
            print("  Fed Funds Rate: ❌ MISSING")
            
        if rates.get("t10_yield") is not None:
            print(f"  10Y Treasury: {rates['t10_yield']:.2f}%")
        else:
            print("  10Y Treasury: ❌ MISSING")
        
        # Stock Indices
        indices = results.get("stock_indices", {})
        print("\n📈 STOCK INDICES:")
        for key, name in [("sp500", "S&P 500"), ("nasdaq", "NASDAQ"), ("dow_jones", "Dow Jones"), ("vix", "VIX")]:
            value = indices.get(key)
            change = indices.get(f"{key}_change")
            if value is not None:
                if change is not None:
                    print(f"  {name}: {value:,.2f} ({change:+.2f}%)")
                else:
                    print(f"  {name}: {value:,.2f}")
            else:
                print(f"  {name}: ❌ MISSING")
        
        # Commodities
        commodities = results.get("commodities", {})
        print("\n🥇 COMMODITIES:")
        for key, name in [("gold", "Gold"), ("silver", "Silver"), ("crude_oil", "Crude Oil"), ("natural_gas", "Natural Gas")]:
            value = commodities.get(key)
            if value is not None:
                if key in ["gold", "silver"]:
                    print(f"  {name}: ${value:,.2f}/oz")
                elif key == "crude_oil":
                    print(f"  {name}: ${value:,.2f}/barrel")
                elif key == "natural_gas":
                    print(f"  {name}: ${value:,.2f}/MMBtu")
            else:
                print(f"  {name}: ❌ MISSING")
        
        # Social Metrics
        social = results.get("social_metrics", {})
        print("\n📱 SOCIAL METRICS:")
        if social.get("forum_posts"):
            print(f"  Bitcoin Forum Posts: {social['forum_posts']:,}")
        else:
            print("  Bitcoin Forum Posts: ❌ MISSING")
            
        if social.get("forum_topics"):
            print(f"  Bitcoin Forum Topics: {social['forum_topics']:,}")
        else:
            print("  Bitcoin Forum Topics: ❌ MISSING")
            
        if social.get("btc_github_stars"):
            print(f"  Bitcoin GitHub Stars: {social['btc_github_stars']:,}")
        else:
            print("  Bitcoin GitHub Stars: ❌ MISSING")
            
        if social.get("eth_github_stars"):
            print(f"  Ethereum GitHub Stars: {social['eth_github_stars']:,}")
        else:
            print("  Ethereum GitHub Stars: ❌ MISSING")
            
        if social.get("btc_recent_commits"):
            print(f"  Bitcoin Recent Commits: {social['btc_recent_commits']}")
        else:
            print("  Bitcoin Recent Commits: ❌ MISSING")
            
        if social.get("eth_recent_commits"):
            print(f"  Ethereum Recent Commits: {social['eth_recent_commits']}")
        else:
            print("  Ethereum Recent Commits: ❌ MISSING")
        
        # Historical Data Summary
        historical = results.get("historical_data", {})
        print("\n📊 HISTORICAL DATA:")
        for coin in ["BTC", "ETH"]:
            coin_data = historical.get(coin, {})
            if coin_data:
                timeframes = list(coin_data.keys())
                print(f"  {coin}: {len(timeframes)} timeframes ({', '.join(timeframes)})")
            else:
                print(f"  {coin}: ❌ MISSING")
        
        # Enhanced Data Sources
        print("\n🔧 ENHANCED DATA SOURCES:")
        
        # Volatility Regime
        volatility = results.get("volatility_regime", {})
        if volatility:
            print(f"  Volatility Regime: {volatility.get('current_regime', 'N/A')} (multiplier: {volatility.get('size_multiplier', 1.0):.1f}x)")
        else:
            print("  Volatility Regime: ❌ MISSING")
        
        # Order Book Analysis
        order_book = results.get("order_book_analysis", {})
        if order_book:
            for coin in ["BTC", "ETH"]:
                coin_data = order_book.get(coin, {})
                if coin_data:
                    print(f"  {coin} Order Book: {coin_data.get('book_signal', 'N/A')} | Imbalance: {coin_data.get('imbalance_ratio', 0)*100:.1f}%")
                else:
                    print(f"  {coin} Order Book: ❌ MISSING")
        else:
            print("  Order Book Analysis: ❌ MISSING")
        
        # Liquidation Heatmap
        liquidation = results.get("liquidation_heatmap", {})
        if liquidation:
            for coin in ["BTC", "ETH"]:
                coin_data = liquidation.get(coin, {})
                if coin_data:
                    print(f"  {coin} Liquidation: {coin_data.get('liquidation_pressure', 'N/A')} | Funding: {coin_data.get('funding_rate', 0):.3f}%")
                else:
                    print(f"  {coin} Liquidation: ❌ MISSING")
        else:
            print("  Liquidation Heatmap: ❌ MISSING")
        
        # Economic Calendar
        economic = results.get("economic_calendar", {})
        if economic:
            print(f"  Economic Calendar: {economic.get('recommendation', 'N/A')} | High Impact: {economic.get('high_impact', 0)}")
        else:
            print("  Economic Calendar: ❌ MISSING")
        
        # Multi-Source Sentiment
        sentiment = results.get("multi_source_sentiment", {})
        if sentiment:
            print(f"  Multi-Source Sentiment: {sentiment.get('sentiment_signal', 'N/A')} | Sources: {sentiment.get('sources_analyzed', 0)}")
        else:
            print("  Multi-Source Sentiment: ❌ MISSING")
        
        # Whale Movements
        whale = results.get("whale_movements", {})
        if whale:
            print(f"  Whale Movements: {whale.get('whale_signal', 'N/A')} | Sentiment: {whale.get('whale_sentiment', 0):.2f}")
        else:
            print("  Whale Movements: ❌ MISSING")
        
        print("="*80)

    def collect_all_data(self):
        """Collect all market data with minimal CoinGecko calls to avoid rate limiting"""
        print("[INFO] Starting comprehensive data collection...")
        
        # Minimal CoinGecko calls - only essential data that can't be obtained elsewhere
        coingecko_tasks = {
            "btc_dominance": self.get_btc_dominance,
            "market_cap": self.get_global_market_cap,
        }
        
        # Other API calls can run in parallel (including Binance-based crypto and volumes)
        parallel_tasks = {
            "crypto": self.get_crypto_data,  # ✅ MOVED: Now uses Binance
            "volumes": self.get_trading_volumes,  # ✅ MOVED: Now uses Binance
            "futures": self.get_futures_sentiment,
            "fear_greed": self.get_fear_greed_index,
            "technical_indicators": self.get_technical_indicators,
            "historical_data": self.get_historical_price_data,
            "volatility_regime": self.get_volatility_regime
        }
        
        if self.config["indicators"].get("include_macroeconomic", True):
            parallel_tasks.update({
                "m2_supply": self.get_m2_money_supply,
                "inflation": self.get_inflation_data,
                "interest_rates": self.get_interest_rates
            })
        
        if self.config["indicators"].get("include_stock_indices", True):
            parallel_tasks["stock_indices"] = self.get_stock_indices
        
        if self.config["indicators"].get("include_commodities", True):
            parallel_tasks["commodities"] = self.get_commodity_prices
        
        if self.config["indicators"].get("include_social_metrics", True):
            parallel_tasks["social_metrics"] = self.get_crypto_social_metrics
        
        # NEW ENHANCED DATA SOURCES - WITH API KEY VALIDATION
        if self.config["indicators"].get("include_enhanced_data", True):
            enhanced_data_tasks = {}
            
            # Only add if API keys available
            if self.binance_api_key and self.binance_secret:
                enhanced_data_tasks.update({
                    "order_book_analysis": self.get_order_book_analysis,
                    "liquidation_heatmap": self.get_liquidation_heatmap
                })
            else:
                print("[WARN] ⚠️ Binance API keys missing - Order book and liquidation analysis disabled")
            
            if self.coinmarketcal_key:
                enhanced_data_tasks["economic_calendar"] = self.get_economic_calendar
            else:
                print("[WARN] ⚠️ CoinMarketCal API key missing - Economic calendar disabled")
            
            if self.news_api_key:
                enhanced_data_tasks["multi_source_sentiment"] = self.get_multi_source_sentiment
            else:
                print("[WARN] ⚠️ News API key missing - Full sentiment analysis disabled")
            
            if self.etherscan_api_key:
                enhanced_data_tasks["whale_movements"] = self.get_whale_movements
            else:
                print("[WARN] ⚠️ Etherscan API key missing - Whale tracking disabled")
            
            parallel_tasks.update(enhanced_data_tasks)
        
        results = {}
        
        # STEP 1: Run minimal CoinGecko calls sequentially to avoid rate limiting
        print("[INFO] Running minimal CoinGecko API calls sequentially...")
        for task_name, func in coingecko_tasks.items():
            try:
                results[task_name] = func()
                print(f"[INFO] ✅ Completed: {task_name}")
                # Add delay between CoinGecko calls
                time.sleep(2)
            except Exception as e:
                print(f"[ERROR] ❌ Task {task_name} failed: {e}")
                results[task_name] = None
        
        # STEP 2: Run other API calls in parallel (including Binance-based crypto and volumes)
        print("[INFO] Running other API calls in parallel (including Binance crypto/volumes)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(parallel_tasks)) as executor:
            future_to_task = {executor.submit(func): task_name for task_name, func in parallel_tasks.items()}
            
            for future in concurrent.futures.as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    results[task_name] = future.result()
                    print(f"[INFO] ✅ Completed: {task_name}")
                except Exception as e:
                    print(f"[ERROR] ❌ Task {task_name} failed: {e}")
                    results[task_name] = None
        
        # Count successful data points - ACCURATE COUNT
        data_points_collected = self._count_data_points(results)
        print(f"\n[INFO] 📊 Data collection complete: {data_points_collected}/54 data points")  # Updated from 53 to 54
        
        # Show missing data points for debugging
        if data_points_collected < 54:  # Updated from 53 to 54
            missing_points = []
            
            # Check each category
            crypto = results.get("crypto", {})
            if not crypto.get("btc"): missing_points.append("BTC price")
            if not crypto.get("eth"): missing_points.append("ETH price")
            
            tech = results.get("technical_indicators", {})
            for coin in ["BTC", "ETH"]:
                coin_data = tech.get(coin, {})
                if not coin_data.get('rsi14'): missing_points.append(f"{coin} RSI")
                if not coin_data.get('signal'): missing_points.append(f"{coin} signal")
                if not coin_data.get('support'): missing_points.append(f"{coin} support")
                if not coin_data.get('resistance'): missing_points.append(f"{coin} resistance")
                if not coin_data.get('trend'): missing_points.append(f"{coin} trend")
                if not coin_data.get('volatility'): missing_points.append(f"{coin} volatility")
            
            futures = results.get("futures", {})
            for coin in ["BTC", "ETH"]:
                coin_data = futures.get(coin, {})
                if not coin_data or coin_data.get('funding_rate') is None: missing_points.append(f"{coin} funding rate")
                if not coin_data or coin_data.get('long_ratio') is None: missing_points.append(f"{coin} long ratio")
                if not coin_data or coin_data.get('short_ratio') is None: missing_points.append(f"{coin} short ratio")
                if not coin_data or coin_data.get('open_interest') is None: missing_points.append(f"{coin} open interest")
            
            if not results.get("fear_greed", {}).get("index"): missing_points.append("Fear & Greed index")
            if not results.get("btc_dominance"): missing_points.append("BTC dominance")
            if not results.get("market_cap"): missing_points.append("Global market cap")
            
            volumes = results.get("volumes", {})
            if not volumes.get("btc_volume"): missing_points.append("BTC volume")
            if not volumes.get("eth_volume"): missing_points.append("ETH volume")
            
            if not results.get("m2_supply", {}).get("m2_supply"): missing_points.append("M2 money supply")
            if results.get("inflation", {}).get("inflation_rate") is None: missing_points.append("Inflation rate")
            
            rates = results.get("interest_rates", {})
            if rates.get("fed_rate") is None: missing_points.append("Fed funds rate")
            if rates.get("t10_yield") is None: missing_points.append("10Y Treasury yield")
            
            indices = results.get("stock_indices", {})
            for key, name in [("sp500", "S&P 500"), ("nasdaq", "NASDAQ"), ("dow_jones", "Dow Jones"), ("vix", "VIX")]:
                if indices.get(key) is None: missing_points.append(name)
            
            commodities = results.get("commodities", {})
            for key, name in [("gold", "Gold"), ("silver", "Silver"), ("crude_oil", "Crude Oil"), ("natural_gas", "Natural Gas")]:
                if commodities.get(key) is None: missing_points.append(name)
            
            social = results.get("social_metrics", {})
            if not social.get("forum_posts"): missing_points.append("Forum posts")
            if not social.get("forum_topics"): missing_points.append("Forum topics")
            if not social.get("btc_github_stars"): missing_points.append("BTC GitHub stars")
            if not social.get("eth_github_stars"): missing_points.append("ETH GitHub stars")
            if not social.get("btc_recent_commits"): missing_points.append("BTC recent commits")
            if not social.get("eth_recent_commits"): missing_points.append("ETH recent commits")
            
            historical = results.get("historical_data", {})
            if not historical.get("BTC"): missing_points.append("BTC historical data")
            if not historical.get("ETH"): missing_points.append("ETH historical data")
            
            # Check volatility regime
            if not results.get("volatility_regime"): missing_points.append("Volatility regime")
            
            # Check new enhanced data sources
            if not results.get("order_book_analysis"): missing_points.append("Order book analysis")
            if not results.get("liquidation_heatmap"): missing_points.append("Liquidation heatmap")
            if not results.get("economic_calendar"): missing_points.append("Economic calendar")
            if not results.get("multi_source_sentiment"): missing_points.append("Multi-source sentiment")
            if not results.get("whale_movements"): missing_points.append("Whale movements")
            
            if missing_points:
                print(f"[WARN] Missing data points: {', '.join(missing_points[:10])}")
                if len(missing_points) > 10:
                    print(f"[WARN] ... and {len(missing_points) - 10} more")
        
        # Validate data consistency
        validation_issues = self._validate_data_consistency(results)
        if validation_issues:
            print(f"\n[WARN] 🔍 Data validation found {len(validation_issues)} potential issues:")
            for issue in validation_issues[:5]:  # Show first 5 issues
                print(f"  • {issue}")
            if len(validation_issues) > 5:
                print(f"  • ... and {len(validation_issues) - 5} more issues")

        # Add verbose logging
        self._log_data_verbose(results)
        
        return results

    def _count_data_points(self, results):
        """Count the number of successful data points collected - ACCURATE COUNT"""
        count = 0
        
        # 1. Crypto Prices (2 points)
        crypto = results.get("crypto", {})
        if crypto.get("btc"): count += 1
        if crypto.get("eth"): count += 1
        
        # 2. Technical Indicators (12 points: 6 per coin)
        tech = results.get("technical_indicators", {})
        for coin in ["BTC", "ETH"]:
            coin_data = tech.get(coin, {})
            if coin_data:
                # Count individual technical indicators
                if coin_data.get('rsi14') is not None: count += 1
                if coin_data.get('signal'): count += 1
                if coin_data.get('support') is not None: count += 1
                if coin_data.get('resistance') is not None: count += 1
                if coin_data.get('trend'): count += 1
                if coin_data.get('volatility'): count += 1
        
        # 3. Futures Sentiment (8 points: 4 per coin)
        futures = results.get("futures", {})
        for coin in ["BTC", "ETH"]:
            coin_data = futures.get(coin, {})
            if coin_data:
                if coin_data.get('funding_rate') is not None: count += 1
                if coin_data.get('long_ratio') is not None: count += 1
                if coin_data.get('short_ratio') is not None: count += 1
                if coin_data.get('open_interest') is not None: count += 1
        
        # 4. Market Sentiment (3 points)
        if results.get("fear_greed", {}).get("index"): count += 1
        if results.get("btc_dominance"): count += 1
        if results.get("market_cap"): count += 1
        
        # 5. Trading Volumes (2 points)
        volumes = results.get("volumes", {})
        if volumes.get("btc_volume"): count += 1
        if volumes.get("eth_volume"): count += 1
        
        # 6. Macroeconomic Data (4 points)
        if results.get("m2_supply", {}).get("m2_supply"): count += 1
        if results.get("inflation", {}).get("inflation_rate") is not None: count += 1
        rates = results.get("interest_rates", {})
        if rates.get("fed_rate") is not None: count += 1
        if rates.get("t10_yield") is not None: count += 1
        
        # 7. Stock Indices (4 points)
        indices = results.get("stock_indices", {})
        for key in ["sp500", "nasdaq", "dow_jones", "vix"]:
            if indices.get(key) is not None: count += 1
        
        # 8. Commodities (4 points)
        commodities = results.get("commodities", {})
        for key in ["gold", "silver", "crude_oil", "natural_gas"]:
            if commodities.get(key) is not None: count += 1
        
        # 9. Social Metrics (6 points)
        social = results.get("social_metrics", {})
        if social.get("forum_posts"): count += 1
        if social.get("forum_topics"): count += 1
        if social.get("btc_github_stars"): count += 1
        if social.get("eth_github_stars"): count += 1
        if social.get("btc_recent_commits"): count += 1
        if social.get("eth_recent_commits"): count += 1
        
        # 10. Historical Data (2 points)
        historical = results.get("historical_data", {})
        if historical.get("BTC"): count += 1
        if historical.get("ETH"): count += 1
        
        # 11. Volatility Regime (1 point: market-wide) - NEW
        if results.get("volatility_regime"): count += 1
        
        # 12. NEW ENHANCED DATA SOURCES (9 points total)
        # Order Book Analysis (2 points: BTC + ETH)
        order_book = results.get("order_book_analysis", {})
        if order_book.get("BTC"): count += 1
        if order_book.get("ETH"): count += 1
        
        # Liquidation Heatmap (2 points: BTC + ETH)
        liquidation = results.get("liquidation_heatmap", {})
        if liquidation.get("BTC"): count += 1
        if liquidation.get("ETH"): count += 1
        
        # Economic Calendar (1 point: market-wide)
        if results.get("economic_calendar"): count += 1
        
        # Multi-Source Sentiment (1 point: market-wide)
        if results.get("multi_source_sentiment"): count += 1
        
        # Whale Movements (2 points: BTC + ETH)
        whale_data = results.get("whale_movements", {})
        if whale_data and whale_data.get('breakdown'):
            breakdown = whale_data.get('breakdown', {})
            if breakdown.get('large_trades'): count += 1
            if breakdown.get('exchange_flows'): count += 1
        
        return count

    def _validate_data_consistency(self, results):
        """Validate data consistency across sources"""
        validation_issues = []
        
        try:
            # Check price consistency (both now from Binance, but different endpoints)
            crypto_btc = results.get("crypto", {}).get("btc")
            tech_btc = results.get("technical_indicators", {}).get("BTC", {}).get("price")
            
            if crypto_btc and tech_btc:
                price_diff = abs(crypto_btc - tech_btc) / crypto_btc
                if price_diff > 0.01:  # 1% difference threshold (both from Binance)
                    validation_issues.append(f"BTC price inconsistency: Binance ticker ${crypto_btc:,.0f} vs Binance klines ${tech_btc:,.0f} ({price_diff*100:.1f}% diff)")
            
            # Check volume consistency
            volumes = results.get("volumes", {})
            if volumes.get("btc_volume") and volumes.get("eth_volume"):
                btc_vol = volumes["btc_volume"]
                eth_vol = volumes["eth_volume"] 
                vol_ratio = btc_vol / eth_vol if eth_vol > 0 else 0
                
                # BTC volume should typically be 1.5-4x ETH volume
                if vol_ratio < 1.0 or vol_ratio > 6.0:
                    validation_issues.append(f"Unusual BTC/ETH volume ratio: {vol_ratio:.1f}x (typical range: 1.5-4x)")
            
            # Check futures data consistency
            futures = results.get("futures", {})
            btc_funding = futures.get("BTC", {}).get("funding_rate")
            eth_funding = futures.get("ETH", {}).get("funding_rate") 
            
            if btc_funding is not None and eth_funding is not None:
                funding_diff = abs(btc_funding - eth_funding)
                if funding_diff > 0.1:  # 0.1% difference threshold
                    validation_issues.append(f"Large BTC/ETH funding rate divergence: {funding_diff:.3f}% difference")
            
            # Check sentiment consistency
            fear_greed = results.get("fear_greed", {}).get("index", 50)
            multi_sentiment = results.get("multi_source_sentiment", {})
            
            if multi_sentiment and multi_sentiment.get("average_sentiment") is not None:
                # Convert fear/greed to -1 to 1 scale
                fg_normalized = (fear_greed - 50) / 50
                multi_sent = multi_sentiment["average_sentiment"]
                
                # Check if they're pointing in opposite directions
                if (fg_normalized > 0.3 and multi_sent < -0.3) or (fg_normalized < -0.3 and multi_sent > 0.3):
                    validation_issues.append(f"Sentiment conflict: F&G {fear_greed} vs Multi-source {multi_sent:.2f}")
            
            return validation_issues
            
        except Exception as e:
            return [f"Validation check failed: {str(e)}"]

    def validate_market_data(self, market_data):
        """Validate that essential market data is present"""
        required_fields = {
            'crypto_prices': ['btc', 'eth'],
            'technical_indicators': ['BTC', 'ETH'],
            'sentiment': ['fear_greed']
        }
        
        missing_data = []
        warnings = []
        
        # Check crypto prices
        crypto = market_data.get("crypto", {})
        if not crypto.get("btc") or not crypto.get("eth"):
            missing_data.append("crypto_prices")
            warnings.append("Missing crypto price data (BTC/ETH)")
        
        # Check technical indicators
        technicals = market_data.get("technical_indicators", {})
        btc_tech = technicals.get("BTC", {})
        eth_tech = technicals.get("ETH", {})
        
        if not btc_tech.get("price") or not btc_tech.get("signal"):
            missing_data.append("btc_technical")
            warnings.append("Missing BTC technical analysis data")
            
        if not eth_tech.get("price") or not eth_tech.get("signal"):
            missing_data.append("eth_technical")
            warnings.append("Missing ETH technical analysis data")
        
        # Check sentiment data
        fear_greed = market_data.get("fear_greed", {})
        if not fear_greed.get("index"):
            missing_data.append("sentiment")
            warnings.append("Missing Fear & Greed index data")
        
        # Optional but important data warnings
        if not market_data.get("btc_dominance"):
            warnings.append("Missing BTC dominance data")
            
        if not market_data.get("market_cap"):
            warnings.append("Missing global market cap data")
        
        can_predict = len(missing_data) == 0
        
        return {
            'can_predict': can_predict,
            'missing_data': missing_data,
            'warnings': warnings,
            'data_completeness': len(required_fields) - len(missing_data),
            'total_data_points': self._count_data_points(market_data)
        }


# Utility function for external use
def create_data_collector(config):
    """Factory function to create a data collector instance"""
    return CryptoDataCollector(config)


if __name__ == "__main__":
    # Test the data collector
    print("Testing data collector...")
    
    # Mock config for testing
    test_config = {
        "api_keys": {
            "fred": "YOUR_FRED_API_KEY",
            "alphavantage": "YOUR_ALPHAVANTAGE_API_KEY"
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
            "include_social_metrics": True,
            "include_enhanced_data": True
        }
    }
    
    collector = CryptoDataCollector(test_config)
    results = collector.collect_all_data()
    
    print(f"\nData collection test complete!")
    print(f"Results keys: {list(results.keys())}")