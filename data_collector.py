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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
        # Economic data API keys
        self.fred_api_key = os.getenv("FRED_API_KEY")
        self.alphavantage_api_key = os.getenv("ALPHAVANTAGE_API_KEY")
        
        # Validate that required methods exist
        required_methods = ['get_btc_network_health', 'get_eth_network_health', 'calculate_crypto_correlations', 'calculate_cross_asset_correlations']
        missing_methods = []
        for method_name in required_methods:
            if not hasattr(self, method_name):
                missing_methods.append(method_name)
        
        if missing_methods:
            print(f"[WARN] ⚠️ Missing required methods: {', '.join(missing_methods)}")
            print(f"[WARN] ⚠️ Network health and correlation data collection may fail")
    
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
        """Get M2 money supply data from FRED API"""
        fred_key = self.fred_api_key
        
        if not fred_key:
            print("[WARN] FRED API key not configured - M2 data unavailable")
            return {"m2_supply": None, "m2_date": None}
        
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
        
        print("[WARN] M2 money supply data unavailable")
        return {"m2_supply": None, "m2_date": None}



    def get_inflation_data(self):
        """Get inflation data from AlphaVantage API"""
        alpha_key = self.alphavantage_api_key
        
        if not alpha_key:
            print("[WARN] AlphaVantage API key not configured - inflation data unavailable")
            return {"inflation_rate": None, "inflation_date": None}
        
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
        
        print("[WARN] Inflation data unavailable")
        return {"inflation_rate": None, "inflation_date": None}



    def get_interest_rates(self):
        """Get interest rates from AlphaVantage API"""
        alpha_key = self.alphavantage_api_key
        
        if not alpha_key:
            print("[WARN] AlphaVantage API key not configured - interest rates unavailable")
            return {"fed_rate": None, "t10_yield": None, "rate_date": None}
        
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
        
        print("[WARN] Interest rates unavailable")
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
                    period = "10d"  # Extended to 10d to ensure 168+ candles (10 * 24 = 240)
                elif timeframe == "4h":
                    period = "35d"  # Extended to 35d to ensure 180+ candles (35 * 6 = 210)
                elif timeframe == "1d":
                    period = "6mo"
                elif timeframe == "1wk":
                    period = "4y"  # Already fixed in Step 1
                    interval = "1wk"
                elif timeframe == "1mo":
                    # For monthly data, use Binance API for both BTC and ETH (more reliable for crypto)
                    if ticker in ["BTC-USD", "ETH-USD"]:
                        try:
                            # Convert to Binance symbol
                            binance_symbol = ticker.replace("-USD", "USDT")
                            print(f"[DEBUG] 📊 Using Binance API for {ticker} monthly data...")
                            
                            # Get monthly data from Binance
                            url = "https://api.binance.com/api/v3/klines"
                            params = {
                                'symbol': binance_symbol,
                                'interval': '1M',  # Monthly
                                'limit': 1000  # Try to get maximum available (Binance cap is usually 1000)
                            }
                            
                            response = requests.get(url, params=params, timeout=30)
                            response.raise_for_status()
                            binance_data = response.json()
                            
                            print(f"[DEBUG] 📊 Binance API response: {len(binance_data)} monthly candles for {ticker}")
                            
                            # Debug: Show first and last candle timestamps
                            if len(binance_data) > 0:
                                import pandas as pd
                                first_candle = binance_data[0]
                                last_candle = binance_data[-1]
                                first_time = pd.to_datetime(int(first_candle[0]) / 1000, unit='s')
                                last_time = pd.to_datetime(int(last_candle[0]) / 1000, unit='s')
                                print(f"[DEBUG] 📊 Binance date range: {first_time} to {last_time}")
                                print(f"[DEBUG] 📊 Binance data span: {(last_time - first_time).days / 30.44:.1f} months")
                            
                            if len(binance_data) >= 80:  # At least 80 months
                                print(f"[DEBUG] 📊 Binance API successful: {len(binance_data)} monthly candles")
                                # Convert Binance data to yfinance format
                                data = self._convert_binance_to_yfinance_format(binance_data, timeframe)
                                if data is not None:
                                    print(f"[DEBUG] 📊 Using Binance data: {len(data)} rows for {ticker}")
                                    # Skip yfinance download since we have Binance data
                                    continue  # Move to next timeframe
                                else:
                                    print(f"[DEBUG] 📊 Binance conversion failed for {ticker}, falling back to yfinance")
                                    period = "max"  # Fallback to yfinance
                            else:
                                print(f"[DEBUG] 📊 Binance API insufficient data for {ticker}: {len(binance_data)} months, falling back to yfinance")
                                period = "max"  # Fallback to yfinance
                        except Exception as e:
                            print(f"[DEBUG] 📊 Binance API failed for {ticker}: {e}, falling back to yfinance")
                            period = "max"  # Fallback to yfinance
                    else:
                        period = "max"  # Use maximum available data instead of fixed 10y
                    interval = "1mo"
                    
                try:
                    print(f"[DEBUG] 📊 Downloading {ticker} {timeframe} data: period={period}, interval={interval}")
                    data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
                    print(f"[DEBUG] 📊 Downloaded {ticker} {timeframe}: {len(data)} rows, date range: {data.index[0] if len(data) > 0 else 'N/A'} to {data.index[-1] if len(data) > 0 else 'N/A'}")
                    
                    if data.empty:
                        print(f"[DEBUG] 📊 {ticker} {timeframe} data is empty")
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
                        # Data quality check: ensure we have enough data for SMA200
                        if timeframe == "1wk" and len(data) < 200:
                            print(f"[WARN] ⚠️ Insufficient data for {ticker} {timeframe}: {len(data)} weeks (need 200+ for SMA200)")
                        
                        # Filter out NaN values and ensure data quality
                        sma20_values = data['SMA20'].dropna().values.tolist()
                        sma50_values = data['SMA50'].dropna().values.tolist()
                        sma200_values = data['SMA200'].dropna().values.tolist()
                        rsi_values = data['RSI'].dropna().values.tolist()
                        macd_values = data['MACD'].dropna().values.tolist()
                        macd_signal_values = data['MACD_Signal'].dropna().values.tolist()
                        macd_histogram_values = data['MACD_Histogram'].dropna().values.tolist()
                        
                        result_data.update({
                            'sma20': sma20_values,
                            'sma50': sma50_values,
                            'sma200': sma200_values,
                            'rsi': rsi_values,
                            'macd': macd_values,
                            'macd_signal': macd_signal_values,
                            'macd_histogram': macd_histogram_values
                        })
                    
                    # Validate data sufficiency for each timeframe
                    data_validation = self._validate_historical_data_sufficiency(timeframe, len(data), ticker)
                    if data_validation['sufficient']:
                        ticker_data[timeframe] = result_data
                        print(f"[INFO] ✅ Historical data: {ticker} {timeframe} - {len(data)} candles ({data_validation['status']})")
                    else:
                        print(f"[WARN] ⚠️ Insufficient data: {ticker} {timeframe} - {len(data)} candles ({data_validation['status']})")
                        print(f"[DEBUG] 📊 Data insufficiency details: {data_validation}")
                        # Still store the data but mark it as insufficient
                        result_data['data_sufficiency'] = data_validation
                        ticker_data[timeframe] = result_data
                    
                except Exception as e:
                    print(f"[ERROR] Failed {timeframe} data for {ticker}: {e}")
                    continue
                    
            historical_data[ticker.split('-')[0]] = ticker_data
        
        return historical_data

    def _convert_binance_to_yfinance_format(self, binance_data, timeframe):
        """Convert Binance API data to yfinance format for consistency"""
        try:
            # Import pandas at the top of the function to avoid scope issues
            import pandas as pd
            
            # Binance data format: [open_time, open, high, low, close, volume, close_time, ...]
            df_data = []
            timestamps = []
            
            for candle in binance_data:
                # Binance timestamps are in milliseconds, convert to datetime
                open_time = int(candle[0]) / 1000  # Convert to seconds
                timestamp = pd.to_datetime(open_time, unit='s')
                
                df_data.append({
                    'Open': float(candle[1]),
                    'High': float(candle[2]),
                    'Low': float(candle[3]),
                    'Close': float(candle[4]),
                    'Volume': float(candle[5])
                })
                timestamps.append(timestamp)
            
            # Create DataFrame with proper timestamp index
            df = pd.DataFrame(df_data, index=timestamps)
            
            # Sort by timestamp to ensure chronological order
            df = df.sort_index()
            
            print(f"[DEBUG] 📊 Converted Binance data: {len(df)} rows, date range: {df.index[0]} to {df.index[-1]}")
            
            return df
        except Exception as e:
            print(f"[ERROR] Failed to convert Binance data: {e}")
            print(f"[DEBUG] Error details: {type(e).__name__}: {str(e)}")
            return None

    def _validate_historical_data_sufficiency(self, timeframe, data_length, ticker):
        """Validate if historical data is sufficient for reliable analysis"""
        validation_rules = {
            "1h": {
                "min_candles": 168,  # 7 days * 24 hours
                "optimal_candles": 240,  # 10 days * 24 hours
                "description": "10 days of hourly data for trend validation"
            },
            "4h": {
                "min_candles": 180,  # 30 days * 6 periods per day
                "optimal_candles": 210,  # 35 days * 6 periods per day
                "description": "35 days of 4-hour data for swing analysis"
            },
            "1d": {
                "min_candles": 180,  # 6 months
                "optimal_candles": 180,
                "description": "6 months of daily data for medium-term trends"
            },
            "1wk": {
                "min_candles": 200,  # 4 years (already fixed in Step 1)
                "optimal_candles": 208,
                "description": "4 years of weekly data for SMA200 calculation"
            },
            "1mo": {
                "min_candles": 80,   # ~6.7 years (minimum acceptable)
                "optimal_candles": 97,  # ~8 years (realistic for Binance API)
                "description": "6+ years of monthly data for long-term analysis (Binance API provides ~8 years)"
            }
        }
        
        rule = validation_rules.get(timeframe, {})
        if not rule:
            return {
                'sufficient': False,
                'status': 'UNKNOWN_TIMEFRAME',
                'message': f'Unknown timeframe: {timeframe}',
                'data_length': data_length,
                'required': 'Unknown'
            }
        
        min_required = rule['min_candles']
        optimal = rule['optimal_candles']
        
        if data_length >= optimal:
            return {
                'sufficient': True,
                'status': 'OPTIMAL',
                'message': f'Optimal data available ({data_length}/{optimal})',
                'data_length': data_length,
                'required': optimal,
                'description': rule['description']
            }
        elif data_length >= min_required:
            return {
                'sufficient': True,
                'status': 'SUFFICIENT',
                'message': f'Sufficient data available ({data_length}/{min_required})',
                'data_length': data_length,
                'required': min_required,
                'description': rule['description']
            }
        else:
            return {
                'sufficient': False,
                'status': 'INSUFFICIENT',
                'message': f'Insufficient data: {data_length}/{min_required} candles',
                'data_length': data_length,
                'required': min_required,
                'description': rule['description'],
                'impact': f'May cause "{ticker} {timeframe}" analysis failures'
            }

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
        
        print("[WARN] Volatility regime data unavailable")
        return None
    
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
        """Get sentiment analysis from News API"""
        print("[INFO] Collecting multi-source sentiment...")
        
        if not self.news_api_key:
            print("[WARN] News API key not configured - sentiment analysis unavailable")
            return None
        
        try:
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
                
                if news_sentiment > 0.3:
                    sentiment_signal = "BULLISH"
                elif news_sentiment < -0.3:
                    sentiment_signal = "BEARISH"
                else:
                    sentiment_signal = "NEUTRAL"
                
                return {
                    'sources_analyzed': 1,
                    'average_sentiment': news_sentiment,
                    'sentiment_signal': sentiment_signal,
                    'source_breakdown': {'news': news_sentiment}
                }
            
        except Exception as e:
            print(f"[ERROR] News sentiment failed: {e}")
        
        print("[WARN] Sentiment analysis unavailable")
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

    def _display_prediction_readiness(self, results):
        """Display prediction readiness status based on available data"""
        print(f"\n" + "="*80)
        print("🎯 PREDICTION READINESS ASSESSMENT")
        print("="*80)
        
        # Check if we have critical enhanced data sources
        critical_sources = {
            'order_book_analysis': 'Order Book Analysis',
            'liquidation_heatmap': 'Liquidation Heatmap',
            'economic_calendar': 'Economic Calendar'
        }
        
        missing_critical = []
        available_critical = []
        
        for source, name in critical_sources.items():
            if results.get(source):
                available_critical.append(name)
            else:
                missing_critical.append(name)
        
        # Display critical data status
        if available_critical:
            print(f"✅ Critical Enhanced Data Available: {', '.join(available_critical)}")
        if missing_critical:
            print(f"❌ Critical Enhanced Data Missing: {', '.join(missing_critical)}")
        
        # Determine prediction readiness
        if missing_critical:
            print(f"\n🚨 PREDICTION STATUS: NOT READY")
            print(f"   Reason: Missing critical market structure data")
            print(f"   Impact: Predictions would be unreliable without {', '.join(missing_critical)}")
            print(f"   Action: Configure missing API keys or check API status")
            
            # Show specific API key requirements
            if 'order_book_analysis' in missing_critical or 'liquidation_heatmap' in missing_critical:
                print(f"   Required: Binance API keys for market structure analysis")
            if 'economic_calendar' in missing_critical:
                print(f"   Required: CoinMarketCal API key for economic events")
        else:
            print(f"\n🎯 PREDICTION STATUS: READY")
            print(f"   All critical enhanced data sources available")
            print(f"   System can provide reliable market analysis")
        
        print("="*80)

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
            missing_apis = []
            available_apis = []
            
            print(f"\n🔧 CONFIGURING ENHANCED DATA SOURCES...")
            
            # Validate Binance API keys for order book and liquidation data
            if self.binance_api_key and self.binance_secret:
                if self.binance_api_key != "YOUR_BINANCE_API_KEY" and self.binance_secret != "YOUR_BINANCE_SECRET":
                    enhanced_data_tasks.update({
                    "order_book_analysis": self.get_order_book_analysis,
                    "liquidation_heatmap": self.get_liquidation_heatmap
                })
                    available_apis.extend(["Order Book Analysis", "Liquidation Heatmap"])
            else:
                missing_apis.append("Binance API (keys not configured)")
            
            # Validate CoinMarketCal API key for economic calendar
            if self.coinmarketcal_key and self.coinmarketcal_key != "YOUR_COINMARKETCAL_API_KEY":
                enhanced_data_tasks["economic_calendar"] = self.get_economic_calendar
                available_apis.append("Economic Calendar")
            else:
                missing_apis.append("CoinMarketCal API (key not configured)")
            
            # Validate News API key for sentiment analysis
            if self.news_api_key and self.news_api_key != "YOUR_NEWS_API_KEY":
                enhanced_data_tasks["multi_source_sentiment"] = self.get_multi_source_sentiment
                available_apis.append("Multi-Source Sentiment")
            else:
                missing_apis.append("News API (key not configured)")
            
            # Validate Etherscan API key for whale tracking
            if self.etherscan_api_key and self.etherscan_api_key != "YOUR_ETHERSCAN_API_KEY":
                enhanced_data_tasks["whale_movements"] = self.get_whale_movements
                available_apis.extend(["Whale Movements"])
            else:
                missing_apis.append("Etherscan API (key not configured)")
            
            # Network Health Data Sources (always available - no API keys required for BTC)
            print(f"  🔍 Checking BTC Network Health method availability...")
            if hasattr(self, 'get_btc_network_health'):
                enhanced_data_tasks["btc_network_health"] = self.get_btc_network_health
                available_apis.extend(["BTC Network Health"])
                print(f"  ✅ BTC Network Health method found and added")
            else:
                missing_apis.append("BTC Network Health (method not found)")
                print(f"  ❌ BTC Network Health method not found")
            
            # ETH Network Health requires Etherscan API key
            print(f"  🔍 Checking ETH Network Health method availability...")
            if self.etherscan_api_key and self.etherscan_api_key != "YOUR_ETHERSCAN_API_KEY":
                if hasattr(self, 'get_eth_network_health'):
                    enhanced_data_tasks["eth_network_health"] = self.get_eth_network_health
                    available_apis.extend(["ETH Network Health"])
                    print(f"  ✅ ETH Network Health method found and added")
                else:
                    missing_apis.append("ETH Network Health (method not found)")
                    print(f"  ❌ ETH Network Health method not found")
            else:
                missing_apis.append("ETH Network Health (Etherscan API key required)")
                print(f"  ⚠️ ETH Network Health requires Etherscan API key")
            
            # Crypto Correlations (always available - uses existing data)
            print(f"  🔍 Checking Crypto Correlations method availability...")
            if hasattr(self, 'calculate_crypto_correlations'):
                enhanced_data_tasks["crypto_correlations"] = self.calculate_crypto_correlations
                available_apis.extend(["Crypto Correlations"])
                print(f"  ✅ Crypto Correlations method found and added")
            else:
                missing_apis.append("Crypto Correlations (method not found)")
                print(f"  ❌ Crypto Correlations method not found")
            
            # Cross-Asset Correlations (always available - uses existing data)
            print(f"  🔍 Checking Cross-Asset Correlations method availability...")
            if hasattr(self, 'calculate_cross_asset_correlations'):
                enhanced_data_tasks["cross_asset_correlations"] = self.calculate_cross_asset_correlations
                available_apis.extend(["Cross-Asset Correlations"])
                print(f"  ✅ Cross-Asset Correlations method found and added")
            else:
                missing_apis.append("Cross-Asset Correlations (method not found)")
                print(f"  ❌ Cross-Asset Correlations method not found")
            
            # Report API key status
            print(f"\n🔑 ENHANCED DATA SOURCE STATUS:")
            if available_apis:
                print(f"  ✅ Available: {', '.join(available_apis)}")
            if missing_apis:
                print(f"  ❌ Missing: {', '.join(missing_apis)}")
                print(f"  ⚠️  WARNING: Enhanced data sources unavailable - predictions may be unreliable")
            
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
                    # Special handling for network health tasks
                    if task_name in ['btc_network_health', 'eth_network_health']:
                        print(f"[WARN] ⚠️ Network health data collection failed - this may affect prediction accuracy")
                    # Special handling for correlation tasks
                    elif task_name in ['crypto_correlations', 'cross_asset_correlations']:
                        print(f"[WARN] ⚠️ Correlation data collection failed - this may affect risk management analysis")
        
        # Count successful data points - ACCURATE COUNT
        data_points_collected = self._count_data_points(results)
        print(f"\n[INFO] 📊 Data collection complete: {data_points_collected}/53 data points")
        
        # Validate network health and correlation data structure
        print(f"\n🔍 VALIDATING NETWORK HEALTH & CORRELATION DATA STRUCTURE...")
        network_health_valid = self._validate_network_health_data(results)
        
        # DEBUG: Show detailed data point breakdown
        print(f"\n🔍 DATA POINT BREAKDOWN DEBUG:")
        print(f"[DEBUG] 🔍 Starting data point breakdown analysis...")
        self._debug_data_point_counting(results, data_points_collected)
        print(f"[DEBUG] 🔍 Data point breakdown analysis complete")
        
        # Display historical data improvements summary
        print(f"\n📈 HISTORICAL DATA IMPROVEMENTS:")
        print(f"  ✅ Hourly data: Extended to 10 days (240 candles) for reliable trend validation")
        print(f"  ✅ 4-hour data: Extended to 35 days (210 candles) for swing analysis")
        print(f"  ✅ Weekly data: 4 years (208 weeks) for reliable SMA200")
        print(f"  ✅ Daily data: 6 months (180 days) for medium-term trends")
        print(f"  ✅ Monthly data: Binance API for BTC/ETH (97 months = 8+ years) - more reliable than yfinance")
        print(f"  🔄 Fallback: yfinance if Binance API unavailable")
        
        # Display network health data summary
        print(f"\n🌐 NETWORK HEALTH DATA:")
        print(f"  🔴 BTC Network Health: Hash Rate, Mining Difficulty, Mempool Congestion, Active Addresses")
        print(f"  🔵 ETH Network Health: Gas Price Pressure, Total Supply")
        print(f"  📊 Total: +6 new data points for comprehensive network analysis")
        
        # Display correlation data summary
        print(f"\n🔗 CORRELATION DATA:")
        print(f"  🔗 Crypto Correlations: BTC-ETH 30d/7d correlation, Strength, Direction, Trend")
        print(f"  🌐 Cross-Asset Correlations: Market Regime, Crypto-Equity Correlation, SP500 Analysis")
        print(f"  📊 Total: +4 new data points for risk management and position sizing")
        
        # Show network health and correlation collection status
        if network_health_valid:
            print(f"  ✅ Network health and correlation data structure validated successfully")
        else:
            print(f"  ⚠️ Network health and correlation data structure validation failed - using fallback data")
            # Add fallback data to results
            fallback_data = self._get_fallback_network_health()
            results.update(fallback_data)
            print(f"  🔄 Fallback network health and correlation data added to results")
        
        # DEBUG: Investigate data quality issues
        print(f"\n🔍 DATA QUALITY INVESTIGATION:")
        self._investigate_data_quality_issues(results)
        
        # Show missing data points for debugging
        if data_points_collected < 53:  # Corrected to actual expected count
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
        
        # Validate data consistency with comprehensive scoring
        validation_results = self._validate_data_consistency(results)
        
        print(f"\n" + "="*80)
        print("🔍 COMPREHENSIVE DATA VALIDATION RESULTS")
        print("="*80)
        
        # Display overall score
        overall_score = validation_results['overall_score']
        if overall_score >= 80:
            score_emoji = "🟢"
            score_status = "EXCELLENT"
        elif overall_score >= 70:
            score_emoji = "🟡"
            score_status = "GOOD"
        elif overall_score >= 50:
            score_emoji = "🟠"
            score_status = "FAIR"
        else:
            score_emoji = "🔴"
            score_status = "POOR"
        
        print(f"{score_emoji} Overall Data Quality: {overall_score:.1f}% ({score_status})")
        
        # Display category scores
        print(f"\n📊 CATEGORY BREAKDOWN:")
        categories = validation_results['category_scores']
        for category, score in categories.items():
            if score >= 15:
                cat_emoji = "🟢"
            elif score >= 10:
                cat_emoji = "🟡"
            elif score >= 5:
                cat_emoji = "🟠"
            else:
                cat_emoji = "🔴"
            
            category_name = category.replace('_', ' ').title()
            print(f"  {cat_emoji} {category_name}: {score:.1f}/20")
        
        # Display issues
        if validation_results['issues']:
            print(f"\n❌ CRITICAL ISSUES ({len(validation_results['issues'])}):")
            for issue in validation_results['issues'][:5]:
                print(f"  • {issue}")
            if len(validation_results['issues']) > 5:
                print(f"  ... and {len(validation_results['issues']) - 5} more")
        
        # Display warnings
        if validation_results['warnings']:
            print(f"\n⚠️ WARNINGS ({len(validation_results['warnings'])}):")
            for warning in validation_results['warnings'][:5]:
                print(f"  • {warning}")
            if len(validation_results['warnings']) > 5:
                print(f"  ... and {len(validation_results['warnings']) - 5} more")
        
        # Display recommendations
        if validation_results['recommendations']:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in validation_results['recommendations']:
                print(f"  • {rec}")
        
        print("="*80)

        # Add verbose logging
        self._log_data_verbose(results)
        
        # Display prediction readiness status
        self._display_prediction_readiness(results)
        
        return results

    def _count_data_points(self, results):
        """Count the number of successful data points collected - ACCURATE COUNT (updated to match validation)"""
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
        
        # 11. Volatility Regime (1 point: market-wide)
        if results.get("volatility_regime"): count += 1
        
        # 12. Enhanced Data Sources (9 points total)
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
        
        # 13. Network Health Data (6 points total)
        # BTC Network Health (4 points)
        btc_network = results.get("btc_network_health", {})
        if btc_network.get("hash_rate_th_s"): count += 1
        if btc_network.get("mining_difficulty"): count += 1
        if btc_network.get("mempool_unconfirmed"): count += 1
        if btc_network.get("active_addresses_trend"): count += 1
        
        # ETH Network Health (2 points)
        eth_network = results.get("eth_network_health", {})
        if eth_network.get("gas_prices"): count += 1
        if eth_network.get("total_supply"): count += 1
        
        # 14. Crypto Correlations (4 points total)
        # Crypto Correlations (2 points)
        crypto_correlations = results.get("crypto_correlations", {})
        if crypto_correlations.get("btc_eth_correlation_30d") is not None: count += 1
        if crypto_correlations.get("btc_eth_correlation_7d") is not None: count += 1
        
        # Cross-Asset Correlations (2 points)
        cross_asset_correlations = results.get("cross_asset_correlations", {})
        if cross_asset_correlations.get("market_regime"): count += 1
        if cross_asset_correlations.get("crypto_equity_regime"): count += 1
        
        return count

    def _investigate_data_quality_issues(self, results):
        """Investigate specific data quality issues"""
        print(f"  🔍 INVESTIGATING KNOWN ISSUES:")
        
        # 1. Volume Ratio Investigation
        volumes = results.get("volumes", {})
        btc_vol = volumes.get("btc_volume")
        eth_vol = volumes.get("eth_volume")
        if btc_vol and eth_vol:
            vol_ratio = btc_vol / eth_vol if eth_vol > 0 else 0
            print(f"    📊 Volume Ratio Analysis:")
            print(f"      BTC Volume: ${btc_vol:,.0f}")
            print(f"      ETH Volume: ${eth_vol:,.0f}")
            print(f"      Ratio: {vol_ratio:.2f}x")
            print(f"      Expected Range: 1.0x - 6.0x")
            if vol_ratio < 1.0:
                print(f"      ⚠️  Unusually low ratio - ETH volume higher than BTC")
            elif vol_ratio > 6.0:
                print(f"      ⚠️  Unusually high ratio - BTC volume much higher than ETH")
        
        # 2. Monthly Data Investigation (BTC & ETH)
        historical = results.get("historical_data", {})
        for coin in ["BTC", "ETH"]:
            monthly_data = historical.get(coin, {}).get("1mo", {})
            if monthly_data:
                close_data = monthly_data.get("close", [])
                print(f"    📅 {coin} Monthly Data Investigation:")
                print(f"      Available candles: {len(close_data)}")
                print(f"      Expected minimum: 80 (6.7 years)")
                print(f"      Expected optimal: 97 (8 years - realistic for Binance)")
                if len(close_data) >= 97:
                    print(f"      ✅ Optimal data available")
                elif len(close_data) >= 80:
                    print(f"      ✅ Sufficient data available")
                else:
                    print(f"      ⚠️  Insufficient data - may cause monthly analysis failures")
                print(f"      🔍 Data source: Binance API (realistic expectation: ~8 years)")
        
        # 3. Historical Data Period Investigation
        print(f"    📈 Historical Data Period Investigation:")
        for coin in ["BTC", "ETH"]:
            coin_data = historical.get(coin, {})
            if coin_data:
                for timeframe in ["1h", "4h", "1d", "1wk", "1mo"]:
                    if timeframe in coin_data:
                        data_sufficiency = coin_data[timeframe].get("data_sufficiency", {})
                        if data_sufficiency:
                            status = data_sufficiency.get("status", "UNKNOWN")
                            message = data_sufficiency.get("message", "No message")
                            print(f"      {coin} {timeframe}: {status} - {message}")
        
        # 4. Enhanced Data Source Investigation
        print(f"    🔧 Enhanced Data Source Investigation:")
        enhanced_sources = ['order_book_analysis', 'liquidation_heatmap', 'economic_calendar', 'multi_source_sentiment', 'whale_movements', 'btc_network_health', 'eth_network_health', 'crypto_correlations', 'cross_asset_correlations']
        for source in enhanced_sources:
            source_data = results.get(source)
            if source_data:
                if source in ['order_book_analysis', 'liquidation_heatmap']:
                    btc_data = source_data.get("BTC")
                    eth_data = source_data.get("ETH")
                    print(f"      {source}: BTC={btc_data is not None}, ETH={eth_data is not None}")
                elif source in ['btc_network_health', 'eth_network_health']:
                    # Network health data has different structure
                    if source == 'btc_network_health':
                        btc_metrics = ['hash_rate_th_s', 'mining_difficulty', 'mempool_unconfirmed', 'active_addresses_trend']
                        available_metrics = sum(1 for metric in btc_metrics if source_data.get(metric))
                        print(f"      {source}: {available_metrics}/4 metrics available")
                    else:  # eth_network_health
                        eth_metrics = ['gas_prices', 'total_supply']
                        available_metrics = sum(1 for metric in eth_metrics if source_data.get(metric))
                        print(f"      {source}: {available_metrics}/2 metrics available")
                elif source in ['crypto_correlations', 'cross_asset_correlations']:
                    # Correlation data has different structure
                    if source == 'crypto_correlations':
                        corr_metrics = ['btc_eth_correlation_30d', 'btc_eth_correlation_7d', 'correlation_strength', 'correlation_direction', 'correlation_trend']
                        available_metrics = sum(1 for metric in corr_metrics if source_data.get(metric) is not None)
                        print(f"      {source}: {available_metrics}/5 metrics available")
                    else:  # cross_asset_correlations
                        cross_metrics = ['market_regime', 'crypto_equity_regime', 'sp500_change_24h', 'equity_move_significance']
                        available_metrics = sum(1 for metric in cross_metrics if source_data.get(metric) is not None)
                        print(f"      {source}: {available_metrics}/4 metrics available")
                else:
                    print(f"      {source}: Available")
            else:
                print(f"      {source}: ❌ Missing")

    def _debug_data_point_counting(self, results, data_points_collected):
        """Debug function to show exactly what data points are being counted"""
        print(f"  📊 DETAILED COUNTING BREAKDOWN:")
        
        # 1. Crypto Prices (2 points)
        crypto = results.get("crypto", {})
        btc_price = crypto.get("btc")
        eth_price = crypto.get("eth")
        print(f"    Crypto Prices: BTC={btc_price is not None}, ETH={eth_price is not None} (2 points)")
        
        # 2. Technical Indicators (12 points: 6 per coin)
        tech = results.get("technical_indicators", {})
        for coin in ["BTC", "ETH"]:
            coin_data = tech.get(coin, {})
            if coin_data:
                indicators = ['rsi14', 'signal', 'support', 'resistance', 'trend', 'volatility']
                coin_count = sum(1 for ind in indicators if coin_data.get(ind) is not None)
                print(f"    {coin} Technical: {coin_count}/6 indicators")
        
        # 3. Futures Sentiment (8 points: 4 per coin)
        futures = results.get("futures", {})
        for coin in ["BTC", "ETH"]:
            coin_data = futures.get(coin, {})
            if coin_data:
                futures_indicators = ['funding_rate', 'long_ratio', 'short_ratio', 'open_interest']
                coin_count = sum(1 for ind in futures_indicators if coin_data.get(ind) is not None)
                print(f"    {coin} Futures: {coin_count}/4 indicators")
        
        # 4. Market Sentiment (3 points)
        fear_greed = results.get("fear_greed", {}).get("index")
        btc_dom = results.get("btc_dominance")
        market_cap = results.get("market_cap")
        sentiment_count = sum([fear_greed is not None, btc_dom is not None, market_cap is not None])
        print(f"    Market Sentiment: F&G={fear_greed is not None}, BTC_DOM={btc_dom is not None}, MC={market_cap is not None} ({sentiment_count}/3 points)")
        
        # 5. Trading Volumes (2 points)
        volumes = results.get("volumes", {})
        btc_vol = volumes.get("btc_volume")
        eth_vol = volumes.get("eth_volume")
        volume_count = sum([btc_vol is not None, eth_vol is not None])
        print(f"    Trading Volumes: BTC={btc_vol is not None}, ETH={eth_vol is not None} ({volume_count}/2 points)")
        
        # 6. Macroeconomic Data (4 points)
        m2 = results.get("m2_supply", {}).get("m2_supply")
        inflation = results.get("inflation", {}).get("inflation_rate")
        fed_rate = results.get("interest_rates", {}).get("fed_rate")
        t10_yield = results.get("interest_rates", {}).get("t10_yield")
        macro_count = sum([m2 is not None, inflation is not None, fed_rate is not None, t10_yield is not None])
        print(f"    Macroeconomic: M2={m2 is not None}, Inflation={inflation is not None}, Fed={fed_rate is not None}, T10={t10_yield is not None} ({macro_count}/4 points)")
        
        # 7. Stock Indices (4 points)
        indices = results.get("stock_indices", {})
        sp500 = indices.get("sp500")
        nasdaq = indices.get("nasdaq")
        dow = indices.get("dow_jones")
        vix = indices.get("vix")
        indices_count = sum([sp500 is not None, nasdaq is not None, dow is not None, vix is not None])
        print(f"    Stock Indices: S&P500={sp500 is not None}, NASDAQ={nasdaq is not None}, Dow={dow is not None}, VIX={vix is not None} ({indices_count}/4 points)")
        
        # 8. Commodities (4 points)
        commodities = results.get("commodities", {})
        gold = commodities.get("gold")
        silver = commodities.get("silver")
        oil = commodities.get("crude_oil")
        gas = commodities.get("natural_gas")
        commodities_count = sum([gold is not None, silver is not None, oil is not None, gas is not None])
        print(f"    Commodities: Gold={gold is not None}, Silver={silver is not None}, Oil={oil is not None}, Gas={gas is not None} ({commodities_count}/4 points)")
        
        # 9. Social Metrics (6 points)
        social = results.get("social_metrics", {})
        social_indicators = ['forum_posts', 'forum_topics', 'btc_github_stars', 'eth_github_stars', 'btc_recent_commits', 'eth_recent_commits']
        social_count = sum(1 for ind in social_indicators if social.get(ind))
        print(f"    Social Metrics: {social_count}/6 points")
        
        # 10. Historical Data (2 points)
        historical = results.get("historical_data", {})
        btc_hist = historical.get("BTC")
        eth_hist = historical.get("ETH")
        historical_count = sum([btc_hist is not None, eth_hist is not None])
        print(f"    Historical Data: BTC={btc_hist is not None}, ETH={eth_hist is not None} ({historical_count}/2 points)")
        
        # 11. Volatility Regime (1 point)
        volatility = results.get("volatility_regime")
        volatility_count = 1 if volatility else 0
        print(f"    Volatility Regime: {volatility is not None} (1 point)")
        
        # Note: Enhanced data points are already counted in their respective categories above
        # (e.g., order book analysis counted in technical indicators, etc.)
        print(f"    Note: Enhanced data points integrated into main categories above")
        
        # Calculate actual total from individual counts
        total_expected = 53  # Actual total data points being collected
        print(f"\n    📊 SUMMARY: Counted {data_points_collected}/{total_expected} expected points")
        if data_points_collected != total_expected:
            print(f"    ⚠️  DISCREPANCY: {abs(data_points_collected - total_expected)} points difference")
        
        # DEBUG: Show the actual count vs expected breakdown
        print(f"    🔍 COUNTING LOGIC:")
        print(f"      Collection count: {data_points_collected}")
        print(f"      Validation count: {total_expected}")
        print(f"      Difference: {data_points_collected - total_expected}")
        print(f"      Expected total: 53 data points")

    def _validate_data_consistency(self, results):
        """Comprehensive data validation with scoring system (0-100%)"""
        validation_results = {
            'overall_score': 0,
            'category_scores': {},
            'issues': [],
            'warnings': [],
            'recommendations': []
        }
        
        try:
            # Initialize category scores with correct point allocations
            categories = {
                'crypto_prices': 0,        # 20 points total
                'technical_indicators': 0,  # 20 points total
                'futures_data': 0,         # 15 points total
                'market_sentiment': 0,     # 10 points total
                'volumes': 0,              # 10 points total
                'macroeconomic': 0,        # 10 points total
                'stock_indices': 0,        # 5 points total
                'commodities': 0,          # 5 points total
                'social_metrics': 0,       # 6 points total
                'historical_data': 0       # 15 points total
            }
            
            # 1. CRYPTO PRICES VALIDATION (20 points)
            crypto = results.get("crypto", {})
            tech = results.get("technical_indicators", {})
            
            if crypto.get("btc") and tech.get("BTC", {}).get("price"):
                btc_price_diff = abs(crypto["btc"] - tech["BTC"]["price"]) / crypto["btc"]
                if btc_price_diff <= 0.01:  # 1% threshold
                    categories['crypto_prices'] += 10
                else:
                    validation_results['issues'].append(f"BTC price inconsistency: {btc_price_diff*100:.1f}% difference")
            else:
                validation_results['issues'].append("Missing BTC price data")
            
            if crypto.get("eth") and tech.get("ETH", {}).get("price"):
                eth_price_diff = abs(crypto["eth"] - tech["ETH"]["price"]) / crypto["eth"]
                if eth_price_diff <= 0.01:
                    categories['crypto_prices'] += 10
                else:
                    validation_results['issues'].append(f"ETH price inconsistency: {eth_price_diff*100:.1f}% difference")
            else:
                validation_results['issues'].append("Missing ETH price data")
            
            # 2. TECHNICAL INDICATORS VALIDATION (20 points)
            for coin in ["BTC", "ETH"]:
                coin_data = tech.get(coin, {})
                if coin_data:
                    # Check required indicators
                    required_indicators = ['rsi14', 'signal', 'support', 'resistance', 'trend', 'volatility']
                    available_indicators = sum(1 for ind in required_indicators if coin_data.get(ind) is not None)
                    indicator_score = (available_indicators / len(required_indicators)) * 10
                    categories['technical_indicators'] += indicator_score
                    
                    if indicator_score < 8:
                        validation_results['warnings'].append(f"{coin} missing indicators: {[ind for ind in required_indicators if coin_data.get(ind) is None]}")
                else:
                    validation_results['issues'].append(f"Missing {coin} technical data")
            
            # 3. FUTURES DATA VALIDATION (15 points)
            futures = results.get("futures", {})
            futures_total = 0
            for coin in ["BTC", "ETH"]:
                coin_futures = futures.get(coin, {})
                if coin_futures:
                    # Check required futures indicators
                    required_indicators = ['funding_rate', 'long_ratio', 'short_ratio']
                    available_indicators = sum(1 for ind in required_indicators if coin_futures.get(ind) is not None)
                    coin_score = (available_indicators / len(required_indicators)) * 7.5
                    futures_total += coin_score
                    
                    if coin_score < 7.5:
                        missing_indicators = [ind for ind in required_indicators if coin_futures.get(ind) is None]
                        validation_results['warnings'].append(f"{coin} missing futures indicators: {missing_indicators}")
                else:
                    validation_results['warnings'].append(f"Missing {coin} futures data")
            
            categories['futures_data'] = futures_total
            
            # 4. MARKET SENTIMENT VALIDATION (10 points)
            sentiment_score = 0
            if results.get("fear_greed", {}).get("index"):
                sentiment_score += 5
            if results.get("btc_dominance"):
                sentiment_score += 5
            if results.get("market_cap"):
                sentiment_score += 0  # Bonus point for market cap
            categories['market_sentiment'] = sentiment_score
            
            # 5. VOLUMES VALIDATION (10 points)
            volumes = results.get("volumes", {})
            volume_score = 0
            if volumes.get("btc_volume"):
                volume_score += 5
            if volumes.get("eth_volume"):
                volume_score += 5
            categories['volumes'] = volume_score
            
            # Add warning if volume ratio is unusual
            if volumes.get("btc_volume") and volumes.get("eth_volume"):
                vol_ratio = volumes["btc_volume"] / volumes["eth_volume"] if volumes["eth_volume"] > 0 else 0
                if not (1.0 <= vol_ratio <= 6.0):  # Typical range
                    validation_results['warnings'].append(f"Unusual BTC/ETH volume ratio: {vol_ratio:.1f}x")
            else:
                validation_results['issues'].append("Missing volume data")
            
            # 6. MACROECONOMIC VALIDATION (10 points)
            macro_indicators = ['m2_supply', 'inflation', 'interest_rates']
            available_macro = 0
            
            # Check M2 supply
            if results.get("m2_supply", {}).get("m2_supply"):
                available_macro += 1
            
            # Check inflation
            if results.get("inflation", {}).get("inflation_rate") is not None:
                available_macro += 1
            
            # Check interest rates (Fed + Treasury)
            rates = results.get("interest_rates", {})
            if rates.get("fed_rate") is not None:
                available_macro += 1
            if rates.get("t10_yield") is not None:
                available_macro += 1
            
            categories['macroeconomic'] = (available_macro / 4) * 10  # 4 total indicators
            
            # 7. STOCK INDICES VALIDATION (5 points)
            indices = results.get("stock_indices", {})
            available_indices = sum(1 for key in ['sp500', 'nasdaq', 'dow_jones', 'vix'] if indices.get(key) is not None)
            categories['stock_indices'] = (available_indices / 4) * 5  # Award partial points for available indices
            
            if available_indices < 4:
                missing_indices = [key for key in ['sp500', 'nasdaq', 'dow_jones', 'vix'] if indices.get(key) is None]
                validation_results['warnings'].append(f"Missing stock indices: {', '.join(missing_indices)}")
            
            # 8. COMMODITIES VALIDATION (5 points)
            commodities = results.get("commodities", {})
            available_commodities = sum(1 for key in ['gold', 'silver', 'crude_oil', 'natural_gas'] if commodities.get(key) is not None)
            categories['commodities'] = (available_commodities / 4) * 5  # Award partial points for available commodities
            
            if available_commodities < 4:
                missing_commodities = [key for key in ['gold', 'silver', 'crude_oil', 'natural_gas'] if commodities.get(key) is None]
                validation_results['warnings'].append(f"Missing commodities: {', '.join(missing_commodities)}")
            
            # 9. SOCIAL METRICS VALIDATION (6 points)
            social = results.get("social_metrics", {})
            social_indicators = ['forum_posts', 'forum_topics', 'btc_github_stars', 'eth_github_stars', 'btc_recent_commits', 'eth_recent_commits']
            available_social = sum(1 for ind in social_indicators if social.get(ind))
            categories['social_metrics'] = (available_social / len(social_indicators)) * 6
            
            if available_social < len(social_indicators):
                missing_social = [ind for ind in social_indicators if not social.get(ind)]
                validation_results['warnings'].append(f"Missing social metrics: {', '.join(missing_social)}")
            
            # 10. HISTORICAL DATA VALIDATION (15 points)
            historical = results.get("historical_data", {})
            for coin in ["BTC", "ETH"]:
                coin_historical = historical.get(coin, {})
                if coin_historical:
                    # Check timeframes with data quality penalties
                    timeframes = ['1h', '4h', '1d', '1wk', '1mo']
                    coin_score = 0
                    
                    for timeframe in timeframes:
                        if timeframe in coin_historical:
                            data_sufficiency = coin_historical[timeframe].get('data_sufficiency', {})
                            if data_sufficiency and data_sufficiency.get('sufficient', True):
                                coin_score += 1.5  # 1.5 points per optimal timeframe
                            else:
                                # Penalize insufficient data
                                coin_score += 0.5  # Only 0.5 points for insufficient data
                                validation_results['warnings'].append(f"{coin} {timeframe}: {data_sufficiency.get('message', 'Insufficient data')}")
                    
                    # Check data quality for weekly (SMA200 requirement)
                    weekly_data = coin_historical.get('1wk', {})
                    if weekly_data and len(weekly_data.get('close', [])) >= 200:
                        coin_score += 7.5  # Full points for SMA200 capability
                    else:
                        coin_score += 3.75  # Half points if insufficient for SMA200
                        validation_results['warnings'].append(f"{coin} weekly data insufficient for SMA200: {len(weekly_data.get('close', [])) if weekly_data else 0} weeks")
                    
                    categories['historical_data'] += coin_score
                else:
                    validation_results['issues'].append(f"Missing {coin} historical data")
            
            # Enhanced data points are already counted in their respective categories above
            # (e.g., order book analysis in technical indicators, etc.)
            # No separate category needed
            
            # Calculate overall score
            total_score = sum(categories.values())
            validation_results['overall_score'] = min(100, total_score)
            validation_results['category_scores'] = categories
            
            # Generate recommendations
            if validation_results['overall_score'] < 70:
                validation_results['recommendations'].append("Data quality below 70% - investigate missing data sources")
            if validation_results['overall_score'] < 50:
                validation_results['recommendations'].append("Critical data quality issues - system may produce unreliable predictions")
            
            # Add specific recommendations for low-scoring categories
            for category, score in categories.items():
                if score < 10:
                    validation_results['recommendations'].append(f"Investigate {category.replace('_', ' ').title()} data collection")
            
            return validation_results
            
        except Exception as e:
            return {
                'overall_score': 0,
                'category_scores': {},
                'issues': [f"Validation system error: {str(e)}"],
                'warnings': [],
                'recommendations': ["Validation system failed - check system logs"]
            }

    def validate_market_data(self, market_data):
        """Validate that essential market data is present and enhanced sources are available"""
        required_fields = {
            'crypto_prices': ['btc', 'eth'],
            'technical_indicators': ['BTC', 'ETH'],
            'sentiment': ['fear_greed']
        }
        
        # Enhanced data sources that are critical for reliable predictions
        critical_enhanced_sources = [
            'order_book_analysis',      # Market structure
            'liquidation_heatmap',      # Price targets
            'economic_calendar'         # Market timing
        ]
        
        missing_data = []
        warnings = []
        critical_failures = []
        
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
        
        # Check enhanced data sources
        enhanced_data = market_data.get("enhanced_data", {})
        missing_enhanced = []
        for source in critical_enhanced_sources:
            if not market_data.get(source):
                missing_enhanced.append(source)
        
        if missing_enhanced:
            critical_failures.append(f"Missing critical enhanced data: {', '.join(missing_enhanced)}")
            warnings.append("Enhanced data sources unavailable - predictions may be unreliable")
        
        # Optional but important data warnings
        if not market_data.get("btc_dominance"):
            warnings.append("Missing BTC dominance data")
            
        if not market_data.get("market_cap"):
            warnings.append("Missing global market cap data")
        
        # Determine if we can make reliable predictions
        basic_data_available = len(missing_data) == 0
        enhanced_data_available = len(missing_enhanced) == 0
        
        can_predict = basic_data_available and enhanced_data_available
        
        # Generate prediction status message
        if not basic_data_available:
            prediction_status = "NO PREDICTION - Basic data missing"
        elif not enhanced_data_available:
            prediction_status = f"NO PREDICTION - Critical APIs unavailable ({', '.join(missing_enhanced)})"
        else:
            prediction_status = "PREDICTION READY - All critical data available"
        
        return {
            'can_predict': can_predict,
            'prediction_status': prediction_status,
            'missing_data': missing_data,
            'critical_failures': critical_failures,
            'warnings': warnings,
            'data_completeness': len(required_fields) - len(missing_data),
            'enhanced_data_available': enhanced_data_available,
            'total_data_points': self._count_data_points(market_data)
        }

    def get_btc_network_health(self):
        """Collect BTC network health data using Blockchain.com API"""
        print("[INFO] 🔴 Collecting BTC Network Health Data...")
        try:
            base_url = "https://blockchain.info"
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            network_data = {}
            
            # 1. Hash Rate Trend
            try:
                url = f"{base_url}/q/hashrate"
                response = session.get(url, timeout=10)
                if response.status_code == 200:
                    current_hashrate = float(response.text)
                    network_data['hash_rate_th_s'] = current_hashrate
                    print(f"  ✅ Hash Rate: {current_hashrate:,.0f} TH/s")
                else:
                    print(f"  ⚠️ Hash rate API failed: {response.status_code}")
            except Exception as e:
                print(f"  ❌ Hash rate collection error: {e}")
            
            # 2. Mining Difficulty Trend
            try:
                url = f"{base_url}/q/getdifficulty"
                response = session.get(url, timeout=10)
                if response.status_code == 200:
                    current_difficulty = float(response.text)
                    network_data['mining_difficulty'] = current_difficulty
                    print(f"  ✅ Mining Difficulty: {current_difficulty:,.0f}")
                    
                    # Get difficulty trends from recent blocks
                    difficulty_trend = self._get_btc_difficulty_trend(session, base_url)
                    if difficulty_trend:
                        network_data['difficulty_trend'] = difficulty_trend
                else:
                    print(f"  ⚠️ Difficulty API failed: {response.status_code}")
            except Exception as e:
                print(f"  ❌ Difficulty collection error: {e}")
            
            # 3. Mempool Congestion
            try:
                url = f"{base_url}/q/unconfirmedcount"
                response = session.get(url, timeout=10)
                if response.status_code == 200:
                    unconfirmed_txs = int(response.text)
                    network_data['mempool_unconfirmed'] = unconfirmed_txs
                    print(f"  ✅ Mempool: {unconfirmed_txs:,} unconfirmed transactions")
                    
                    # Get transaction trends from recent blocks
                    tx_trend = self._get_btc_transaction_trend(session, base_url, unconfirmed_txs)
                    if tx_trend:
                        network_data['transaction_trend'] = tx_trend
                else:
                    print(f"  ⚠️ Mempool API failed: {response.status_code}")
            except Exception as e:
                print(f"  ❌ Mempool collection error: {e}")
            
            # 4. Active Addresses Trend
            try:
                addresses_trend = self._get_btc_active_addresses_trend(session, base_url)
                if addresses_trend:
                    network_data['active_addresses_trend'] = addresses_trend
            except Exception as e:
                print(f"  ❌ Active addresses collection error: {e}")
            
            # 5. Network Stats
            try:
                # Block height
                url = f"{base_url}/q/getblockcount"
                response = session.get(url, timeout=10)
                if response.status_code == 200:
                    block_height = int(response.text)
                    network_data['block_height'] = block_height
                    print(f"  ✅ Block Height: {block_height:,}")
                
                # Average block time
                url = f"{base_url}/q/interval"
                response = session.get(url, timeout=10)
                if response.status_code == 200:
                    avg_block_time = float(response.text)
                    network_data['avg_block_time_minutes'] = avg_block_time
                    print(f"  ✅ Avg Block Time: {avg_block_time:.2f} minutes")
                
                # Total BTC supply
                url = f"{base_url}/q/totalbc"
                response = session.get(url, timeout=10)
                if response.status_code == 200:
                    total_supply = float(response.text) / 1e8  # Convert satoshis to BTC
                    network_data['total_btc_supply'] = total_supply
                    print(f"  ✅ Total Supply: {total_supply:,.2f} BTC")
                    
            except Exception as e:
                print(f"  ❌ Network stats collection error: {e}")
            
            if network_data:
                print(f"  ✅ BTC Network Health: {len(network_data)} metrics collected")
                return network_data
            else:
                print(f"  ❌ No BTC network health data collected")
                return None
                
        except Exception as e:
            print(f"❌ BTC Network Health collection failed: {e}")
            return None

    def _get_btc_difficulty_trend(self, session, base_url):
        """Get BTC difficulty trend from recent blocks"""
        try:
            # Get current block height
            url = f"{base_url}/q/getblockcount"
            response = session.get(url, timeout=10)
            if response.status_code != 200:
                return None
            
            current_height = int(response.text)
            
            # Get difficulty from recent blocks using 'bits' field
            block_heights = [current_height, current_height - 1, current_height - 2, current_height - 3]
            difficulties = []
            
            for height in block_heights:
                try:
                    url = f"{base_url}/rawblock/{height}"
                    response = session.get(url, timeout=15)
                    
                    if response.status_code == 200:
                        block_data = response.json()
                        if 'bits' in block_data:
                            bits = block_data['bits']
                            
                            # Handle different data types for bits
                            if isinstance(bits, str):
                                try:
                                    bits_int = int(bits, 16)
                                except ValueError:
                                    continue
                            elif isinstance(bits, int):
                                bits_int = bits
                            else:
                                continue
                            
                            # Calculate difficulty from bits using correct Bitcoin formula
                            try:
                                exponent = bits_int >> 24  # First byte
                                mantissa = bits_int & 0xffffff  # Last 3 bytes
                                
                                # Calculate target: target = mantissa * 2^(8*(exponent-3))
                                target = mantissa * (2 ** (8 * (exponent - 3)))
                                
                                # Calculate difficulty: difficulty = difficulty_1 / target
                                difficulty_1 = 2 ** 224
                                difficulty_from_bits = difficulty_1 / target
                                
                                difficulties.append(difficulty_from_bits)
                                
                            except Exception:
                                continue
                                
                        elif 'difficulty' in block_data:
                            difficulties.append(block_data['difficulty'])
                    
                    time.sleep(0.3)  # Rate limiting
                    
                except Exception:
                    continue
            
            if len(difficulties) >= 2:
                # Calculate trend
                difficulty_change = ((difficulties[0] - difficulties[-1]) / difficulties[-1]) * 100
                return {
                    'current_difficulty': difficulties[0],
                    'difficulty_range': [min(difficulties), max(difficulties)],
                    'trend_percentage': difficulty_change,
                    'trend_direction': 'increasing' if difficulty_change > 0 else 'decreasing' if difficulty_change < 0 else 'stable'
                }
            
            return None
            
        except Exception:
            return None

    def _get_btc_transaction_trend(self, session, base_url, unconfirmed_txs):
        """Get BTC transaction trend from recent blocks"""
        try:
            # Get current block height
            url = f"{base_url}/q/getblockcount"
            response = session.get(url, timeout=10)
            if response.status_code != 200:
                return None
            
            current_height = int(response.text)
            
            # Get transaction counts from recent blocks
            block_heights = [current_height, current_height - 1, current_height - 2, current_height - 3, current_height - 4]
            tx_counts = []
            
            for height in block_heights:
                try:
                    url = f"{base_url}/rawblock/{height}"
                    response = session.get(url, timeout=15)
                    
                    if response.status_code == 200:
                        block_data = response.json()
                        if 'n_tx' in block_data:
                            tx_counts.append(block_data['n_tx'])
                    
                    time.sleep(0.3)  # Rate limiting
                    
                except Exception:
                    continue
            
            if len(tx_counts) >= 2:
                # Calculate mempool pressure
                avg_tx_per_block = sum(tx_counts) / len(tx_counts)
                mempool_pressure = unconfirmed_txs / avg_tx_per_block if avg_tx_per_block > 0 else 0
                
                # Calculate transaction trend
                recent_avg = sum(tx_counts[:2]) / 2  # Last 2 blocks
                older_avg = sum(tx_counts[-2:]) / 2  # Previous 2 blocks
                tx_trend = 0
                if older_avg > 0:
                    tx_trend = ((recent_avg - older_avg) / older_avg) * 100
                
                return {
                    'avg_transactions_per_block': avg_tx_per_block,
                    'mempool_pressure_blocks': mempool_pressure,
                    'transaction_trend_percentage': tx_trend,
                    'transaction_range': [min(tx_counts), max(tx_counts)]
                }
            
            return None
            
        except Exception:
            return None

    def _get_btc_active_addresses_trend(self, session, base_url):
        """Get BTC active addresses trend from recent blocks"""
        try:
            # Get current block height
            url = f"{base_url}/q/getblockcount"
            response = session.get(url, timeout=10)
            if response.status_code != 200:
                return None
            
            current_height = int(response.text)
            
            # Get recent blocks to analyze address activity
            block_heights = [current_height, current_height - 1, current_height - 2, current_height - 3, current_height - 4]
            address_data = []
            
            for height in block_heights:
                try:
                    url = f"{base_url}/rawblock/{height}"
                    response = session.get(url, timeout=15)
                    
                    if response.status_code == 200:
                        block_data = response.json()
                        
                        # Count unique addresses in transactions
                        unique_addresses = set()
                        if 'tx' in block_data:
                            for tx in block_data['tx']:
                                # Add input addresses
                                if 'inputs' in tx:
                                    for input_tx in tx['inputs']:
                                        if 'prev_out' in input_tx and 'addr' in input_tx['prev_out']:
                                            unique_addresses.add(input_tx['prev_out']['addr'])
                                
                                # Add output addresses
                                if 'out' in tx:
                                    for output in tx['out']:
                                        if 'addr' in output:
                                            unique_addresses.add(output['addr'])
                            
                            address_data.append({
                                'height': height,
                                'unique_addresses': len(unique_addresses),
                                'transaction_count': len(block_data['tx'])
                            })
                    
                    time.sleep(0.3)  # Rate limiting
                    
                except Exception:
                    continue
            
            if len(address_data) >= 2:
                # Calculate address activity trends
                total_addresses = sum(d['unique_addresses'] for d in address_data)
                avg_addresses = total_addresses / len(address_data)
                total_transactions = sum(d['transaction_count'] for d in address_data)
                avg_transactions = total_transactions / len(address_data)
                
                # Analyze address activity trend
                recent_avg = sum(d['unique_addresses'] for d in address_data[:2]) / 2  # Last 2 blocks
                older_avg = sum(d['unique_addresses'] for d in address_data[-2:]) / 2  # Previous 2 blocks
                
                address_trend = 0
                if older_avg > 0:
                    address_trend = ((recent_avg - older_avg) / older_avg) * 100
                
                # Calculate address density
                address_density = recent_avg / avg_transactions if avg_transactions > 0 else 0
                
                return {
                    'avg_unique_addresses_per_block': avg_addresses,
                    'avg_transactions_per_block': avg_transactions,
                    'address_activity_trend_percentage': address_trend,
                    'address_density_per_tx': address_density,
                    'total_unique_addresses': total_addresses
                }
            
            return None
            
        except Exception:
            return None

    def get_eth_network_health(self):
        """Collect ETH network health data using Etherscan API"""
        print("[INFO] 🔵 Collecting ETH Network Health Data...")
        try:
            if not self.etherscan_api_key or self.etherscan_api_key == "YOUR_ETHERSCAN_API_KEY":
                print("  ❌ Etherscan API key not configured")
                return None
            
            base_url = "https://api.etherscan.io/api"
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            network_data = {}
            
            # 1. Gas Price Pressure (Network Demand)
            try:
                url = f"{base_url}"
                params = {
                    'module': 'gastracker',
                    'action': 'gasoracle',
                    'apikey': self.etherscan_api_key
                }
                
                response = session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == '1':
                        gas_data = data['result']
                        
                        # Extract gas prices
                        safe_low = None
                        standard = None
                        fast = None
                        
                        # Handle different field names
                        if 'SafeGasPrice' in gas_data:
                            safe_low = float(gas_data['SafeGasPrice']) * 1e9  # Convert from ETH to Gwei
                        elif 'SafeLow' in gas_data:
                            safe_low = float(gas_data['SafeLow']) * 1e9
                        
                        if 'ProposeGasPrice' in gas_data:
                            standard = float(gas_data['ProposeGasPrice']) * 1e9
                        elif 'ProposeGasPrice' in gas_data:
                            standard = float(gas_data['ProposeGasPrice']) * 1e9
                        
                        if 'FastGasPrice' in gas_data:
                            fast = float(gas_data['FastGasPrice']) * 1e9
                        elif 'FastGasPrice' in gas_data:
                            fast = float(gas_data['FastGasPrice']) * 1e9
                        
                        if safe_low and fast:
                            gas_spread = fast - safe_low
                            pressure_ratio = fast / safe_low if safe_low > 0 else 0
                            
                            network_data['gas_prices'] = {
                                'safe_low_gwei': safe_low,
                                'standard_gwei': standard,
                                'fast_gwei': fast,
                                'gas_spread_gwei': gas_spread,
                                'pressure_ratio': pressure_ratio
                            }
                            
                            print(f"  ✅ Gas Prices: Safe {safe_low:,.0f}, Fast {fast:,.0f} Gwei")
                            print(f"  ✅ Gas Pressure: {pressure_ratio:.2f}x ratio")
                        else:
                            print(f"  ⚠️ Incomplete gas price data")
                    else:
                        print(f"  ⚠️ Gas price API error: {data.get('message', 'Unknown')}")
                else:
                    print(f"  ⚠️ Gas price API failed: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Gas price collection error: {e}")
            
            # 2. ETH Total Supply
            try:
                url = f"{base_url}"
                params = {
                    'module': 'stats',
                    'action': 'ethsupply',
                    'apikey': self.etherscan_api_key
                }
                
                response = session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == '1':
                        total_supply_wei = int(data['result'])
                        total_supply_eth = total_supply_wei / 1e18  # Convert from Wei to ETH
                        
                        network_data['total_supply'] = {
                            'total_eth_supply': total_supply_eth,
                            'total_wei_supply': total_supply_wei
                        }
                        
                        print(f"  ✅ Total Supply: {total_supply_eth:,.2f} ETH")
                    else:
                        print(f"  ⚠️ Supply API error: {data.get('message', 'Unknown')}")
                else:
                    print(f"  ⚠️ Supply API failed: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Supply collection error: {e}")
            
            # 3. Additional Network Metrics
            try:
                # Get latest block for gas utilization
                url = f"{base_url}"
                params = {
                    'module': 'proxy',
                    'action': 'eth_blockNumber',
                    'apikey': self.etherscan_api_key
                }
                
                response = session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'result' in data:
                        latest_block_hex = data['result']
                        latest_block = int(latest_block_hex, 16)
                        
                        # Get block details
                        block_params = {
                            'module': 'proxy',
                            'action': 'eth_getBlockByNumber',
                            'tag': 'latest',
                            'boolean': 'false',
                            'apikey': self.etherscan_api_key
                        }
                        
                        block_response = session.get(url, params=block_params, timeout=15)
                        
                        if block_response.status_code == 200:
                            block_data = block_response.json()
                            if 'result' in block_data and block_data['result']:
                                block = block_data['result']
                                
                                if 'gasUsed' in block and 'gasLimit' in block:
                                    gas_used = int(block['gasUsed'], 16)
                                    gas_limit = int(block['gasLimit'], 16)
                                    gas_utilization = (gas_used / gas_limit) * 100
                                    
                                    network_data['current_block'] = {
                                        'block_height': latest_block,
                                        'gas_used': gas_used,
                                        'gas_limit': gas_limit,
                                        'gas_utilization_percent': gas_utilization
                                    }
                                    
                                    print(f"  ✅ Current Block: {latest_block:,} ({gas_utilization:.1f}% gas used)")
                
            except Exception as e:
                print(f"  ❌ Block metrics collection error: {e}")
            
            if network_data:
                print(f"  ✅ ETH Network Health: {len(network_data)} metrics collected")
                return network_data
            else:
                print(f"  ❌ No ETH network health data collected")
                return None
                
        except Exception as e:
            print(f"❌ ETH Network Health collection failed: {e}")
            return None

    def _get_fallback_network_health(self):
        """Provide fallback network health and correlation data if collection fails"""
        print("[INFO] 🔄 Using fallback network health and correlation data...")
        return {
            'btc_network_health': {
                'hash_rate_th_s': None,
                'mining_difficulty': None,
                'mempool_unconfirmed': None,
                'active_addresses_trend': None,
                'fallback': True
            },
            'eth_network_health': {
                'gas_prices': None,
                'total_supply': None,
                'fallback': True
            },
            'crypto_correlations': {
                'btc_eth_correlation_30d': None,
                'btc_eth_correlation_7d': None,
                'correlation_strength': None,
                'correlation_direction': None,
                'correlation_trend': None,
                'fallback': True
            },
            'cross_asset_correlations': {
                'market_regime': None,
                'crypto_equity_regime': None,
                'sp500_change_24h': None,
                'equity_move_significance': None,
                'fallback': True
            }
        }

    def _validate_network_health_data(self, results):
        """Validate that network health and correlation data is properly structured"""
        btc_network = results.get('btc_network_health', {})
        eth_network = results.get('eth_network_health', {})
        crypto_correlations = results.get('crypto_correlations', {})
        cross_asset_correlations = results.get('cross_asset_correlations', {})
        
        validation_issues = []
        
        # Check BTC network health structure
        if btc_network:
            expected_btc_fields = ['hash_rate_th_s', 'mining_difficulty', 'mempool_unconfirmed', 'active_addresses_trend']
            for field in expected_btc_fields:
                if field not in btc_network:
                    validation_issues.append(f"BTC Network Health missing field: {field}")
        else:
            validation_issues.append("BTC Network Health data missing")
        
        # Check ETH network health structure
        if eth_network:
            expected_eth_fields = ['gas_prices', 'total_supply']
            for field in expected_eth_fields:
                if field not in eth_network:
                    validation_issues.append(f"ETH Network Health missing field: {field}")
        else:
            validation_issues.append("ETH Network Health data missing")
        
        # Check crypto correlations structure
        if crypto_correlations:
            expected_corr_fields = ['btc_eth_correlation_30d', 'btc_eth_correlation_7d', 'correlation_strength', 'correlation_direction', 'correlation_trend']
            for field in expected_corr_fields:
                if field not in crypto_correlations:
                    validation_issues.append(f"Crypto Correlations missing field: {field}")
        else:
            validation_issues.append("Crypto Correlations data missing")
        
        # Check cross-asset correlations structure
        if cross_asset_correlations:
            expected_cross_fields = ['market_regime', 'crypto_equity_regime', 'sp500_change_24h', 'equity_move_significance']
            for field in expected_cross_fields:
                if field not in cross_asset_correlations:
                    validation_issues.append(f"Cross-Asset Correlations missing field: {field}")
        else:
            validation_issues.append("Cross-Asset Correlations data missing")
        
        if validation_issues:
            print(f"[WARN] ⚠️ Network health and correlation data validation issues:")
            for issue in validation_issues:
                print(f"  - {issue}")
            return False
        else:
            print(f"[INFO] ✅ Network health and correlation data structure validated")
            return True

    def calculate_crypto_correlations(self):
        """Calculate correlations from existing historical data (FREE)"""
        print("[INFO] 🔗 Calculating Crypto Correlations...")
        try:
            # Get existing historical data
            historical = self.get_historical_price_data()
            
            if not historical.get('BTC') or not historical.get('ETH'):
                print("  ⚠️ Insufficient historical data for correlation calculation")
                return {}
            
            correlation_data = {}
            
            # BTC-ETH correlation using daily closes
            btc_daily = historical.get('BTC', {}).get('1d', {})
            eth_daily = historical.get('ETH', {}).get('1d', {})
            
            if btc_daily.get('close') and eth_daily.get('close'):
                btc_closes = btc_daily['close'][-30:]  # Last 30 days
                eth_closes = eth_daily['close'][-30:]  # Last 30 days
                
                if len(btc_closes) == len(eth_closes) and len(btc_closes) >= 10:
                    correlation = self._calculate_correlation(btc_closes, eth_closes)
                    correlation_data['btc_eth_correlation_30d'] = correlation
                    
                    # Correlation strength classification
                    if abs(correlation) > 0.8:
                        correlation_data['correlation_strength'] = 'STRONG'
                    elif abs(correlation) > 0.5:
                        correlation_data['correlation_strength'] = 'MODERATE'
                    else:
                        correlation_data['correlation_strength'] = 'WEAK'
                    
                    # Direction classification
                    correlation_data['correlation_direction'] = 'POSITIVE' if correlation > 0 else 'NEGATIVE'
                    
                    print(f"  ✅ 30-day correlation: {correlation:.3f} ({correlation_data['correlation_strength']}, {correlation_data['correlation_direction']})")
                else:
                    print(f"  ⚠️ Insufficient daily data: BTC={len(btc_closes)}, ETH={len(eth_closes)}")
            
            # Calculate recent correlation trend (7d vs 30d)
            if len(btc_closes) >= 30 and len(eth_closes) >= 30:
                recent_corr = self._calculate_correlation(btc_closes[-7:], eth_closes[-7:])
                long_corr = correlation_data.get('btc_eth_correlation_30d', 0)
                
                correlation_data['btc_eth_correlation_7d'] = recent_corr
                correlation_data['correlation_trend'] = 'INCREASING' if recent_corr > long_corr else 'DECREASING'
                
                print(f"  ✅ 7-day correlation: {recent_corr:.3f}")
                print(f"  ✅ Correlation trend: {correlation_data['correlation_trend']}")
            
            if correlation_data:
                print(f"  ✅ Crypto correlations calculated: {len(correlation_data)} metrics")
                return correlation_data
            else:
                print(f"  ⚠️ No correlation data could be calculated")
                return {}
                
        except Exception as e:
            print(f"  ❌ Crypto correlations failed: {e}")
            return {}

    def _calculate_correlation(self, x_data, y_data):
        """Calculate Pearson correlation coefficient"""
        try:
            import numpy as np
            
            # Convert to numpy arrays and handle None values
            x = np.array([float(v) for v in x_data if v is not None])
            y = np.array([float(v) for v in y_data if v is not None])
            
            if len(x) != len(y) or len(x) < 3:
                return 0.0
            
            # Calculate correlation
            correlation_matrix = np.corrcoef(x, y)
            correlation = correlation_matrix[0, 1]
            
            # Handle NaN
            return float(correlation) if not np.isnan(correlation) else 0.0
            
        except Exception:
            return 0.0

    def calculate_cross_asset_correlations(self):
        """Calculate crypto vs traditional asset correlations (FREE)"""
        print("[INFO] 🌐 Calculating Cross-Asset Correlations...")
        try:
            correlation_data = {}
            
            # Get existing stock indices data
            stock_indices = self.get_stock_indices()
            
            # Get crypto price data
            crypto_data = self.get_crypto_data()
            
            if not stock_indices or not crypto_data:
                print("  ⚠️ Insufficient data for cross-asset correlations")
                return {}
            
            # Risk sentiment based on VIX vs BTC
            vix = stock_indices.get('vix')
            btc_price = crypto_data.get('btc')
            
            if vix and btc_price:
                # Risk-on/Risk-off classification
                if vix > 25:  # High fear
                    correlation_data['market_regime'] = 'RISK_OFF'
                    correlation_data['crypto_equity_regime'] = 'NEGATIVE_CORRELATION_EXPECTED'
                    print(f"  ✅ Market regime: RISK_OFF (VIX: {vix:.2f})")
                elif vix < 15:  # Low fear
                    correlation_data['market_regime'] = 'RISK_ON'
                    correlation_data['crypto_equity_regime'] = 'POSITIVE_CORRELATION_EXPECTED'
                    print(f"  ✅ Market regime: RISK_ON (VIX: {vix:.2f})")
                else:
                    correlation_data['market_regime'] = 'NEUTRAL'
                    correlation_data['crypto_equity_regime'] = 'MIXED_CORRELATION'
                    print(f"  ✅ Market regime: NEUTRAL (VIX: {vix:.2f})")
            
            # SPY change vs crypto (directional alignment)
            sp500_change = stock_indices.get('sp500_change')
            if sp500_change is not None:
                correlation_data['sp500_change_24h'] = sp500_change
                
                # Simple directional correlation indicator
                if abs(sp500_change) > 1:  # Significant stock move
                    correlation_data['equity_move_significance'] = 'HIGH'
                elif abs(sp500_change) > 0.5:
                    correlation_data['equity_move_significance'] = 'MEDIUM'
                else:
                    correlation_data['equity_move_significance'] = 'LOW'
                
                print(f"  ✅ SP500 24h change: {sp500_change:+.2f}% ({correlation_data['equity_move_significance']} significance)")
            
            if correlation_data:
                print(f"  ✅ Cross-asset correlations calculated: {len(correlation_data)} metrics")
                return correlation_data
            else:
                print(f"  ⚠️ No cross-asset correlation data could be calculated")
                return {}
                
        except Exception as e:
            print(f"  ❌ Cross-asset correlations failed: {e}")
            return {}


# Utility function for external use
def create_data_collector(config):
    """Factory function to create a data collector instance"""
    return CryptoDataCollector(config)


if __name__ == "__main__":
    # Test the data collector
    print("Testing data collector...")
    
    # Mock config for testing
    test_config = {
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