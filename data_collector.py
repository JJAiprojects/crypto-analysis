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

class CryptoDataCollector:
    def __init__(self, config):
        self.config = config
    
    def resilient_request(self, url, params=None, headers=None, max_retries=None, timeout=None):
        """Make resilient API requests with retries and error handling"""
        if max_retries is None:
            max_retries = self.config["api"]["max_retries"]
        if timeout is None:
            timeout = self.config["api"]["timeout"]
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    print(f"[WARN] Rate limited, waiting {retry_after}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(retry_after)
                    continue
                    
                # Check for other common status codes
                if response.status_code == 403:
                    print(f"[ERROR] Access forbidden: {url}")
                    return None
                elif response.status_code == 404:
                    print(f"[ERROR] Endpoint not found: {url}")
                    return None
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
                    return data
                except json.JSONDecodeError as e:
                    print(f"[ERROR] Invalid JSON response from {url}: {e}")
                    return None
                
            except requests.exceptions.RequestException as e:
                backoff = self.config["api"]["backoff_factor"] ** attempt
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
                
                if fed_data and treasury_data:
                    return {
                        "fed_rate": float(fed_data["data"][0]["value"]),
                        "t10_yield": float(treasury_data["data"][0]["value"]),
                        "rate_date": fed_data["data"][0]["date"]
                    }
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
        """Get basic crypto price data"""
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "bitcoin,ethereum", "vs_currencies": "usd"}
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        
        data = self.resilient_request(url, params=params, headers=headers)
        if data:
            return {
                "btc": data["bitcoin"]["usd"], 
                "eth": data["ethereum"]["usd"]
            }
        return {"btc": None, "eth": None}

    def get_futures_sentiment(self):
        """Get futures market sentiment data"""
        base_url = "https://fapi.binance.com"
        symbols = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
        data = {}
        
        def get_funding(symbol):
            url = f"{base_url}/fapi/v1/premiumIndex"
            result = self.resilient_request(url, {"symbol": symbol})
            return float(result["lastFundingRate"]) * 100 if result else None
            
        def get_ratio(symbol):
            url = f"{base_url}/futures/data/topLongShortAccountRatio"
            result = self.resilient_request(url, {"symbol": symbol, "period": "1d", "limit": 1})
            if result and len(result) > 0:
                return float(result[0]["longAccount"]), float(result[0]["shortAccount"])
            return None, None
            
        def get_oi(symbol):
            url = f"{base_url}/futures/data/openInterestHist"
            result = self.resilient_request(url, {"symbol": symbol, "period": "5m", "limit": 1})
            return float(result[0]["sumOpenInterestValue"]) if result and len(result) > 0 else None
        
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
            data = self.resilient_request("https://api.coingecko.com/api/v3/global")
            if data:
                return data["data"]["market_cap_percentage"]["btc"]
        except Exception as e:
            print(f"[ERROR] BTC Dominance: {e}")
        return None

    def get_global_market_cap(self):
        """Get global crypto market cap"""
        try:
            data = self.resilient_request("https://api.coingecko.com/api/v3/global")
            if data:
                return (
                    data["data"]["total_market_cap"]["usd"], 
                    data["data"]["market_cap_change_percentage_24h_usd"]
                )
        except Exception as e:
            print(f"[ERROR] Global Market Cap: {e}")
        return None, None

    def get_trading_volumes(self):
        """Get trading volumes"""
        try:
            data = self.resilient_request(
                "https://api.coingecko.com/api/v3/coins/markets", 
                params={"vs_currency": "usd", "ids": "bitcoin,ethereum"}
            )
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
                if symbol != "ETHUSDT":  # Don't delay after the last symbol
                    time.sleep(0.5)
                
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
                    data = yf.download(ticker, period=period, interval=interval, progress=False)
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
    # Main Data Collection
    # ----------------------------
    def _log_data_verbose(self, results):
        """Log all collected data points with actual values for debugging"""
        print("\n" + "="*80)
        print("📊 DETAILED DATA COLLECTION RESULTS")
        print("="*80)
        
        # Crypto Prices
        crypto = results.get("crypto", {})
        print("\n💰 CRYPTO PRICES:")
        if crypto.get("btc"):
            print(f"  BTC: ${crypto['btc']:,.2f}")
        else:
            print("  BTC: ❌ MISSING")
            
        if crypto.get("eth"):
            print(f"  ETH: ${crypto['eth']:,.2f}")
        else:
            print("  ETH: ❌ MISSING")
            
        # Technical Indicators
        tech = results.get("technical_indicators", {})
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
        
        print("\n" + "="*80)
        
        # Accurate data count
        total_collected = self._count_data_points(results)
        total_possible = 47
        missing_count = total_possible - total_collected
        
        print(f"📊 DATA SUMMARY: {total_collected}/{total_possible} data points collected")
        
        if missing_count > 0:
            print(f"⚠️  {missing_count} data points missing - check API keys and network connectivity")
        else:
            print("✅ All data points collected successfully!")
        
        print("="*80 + "\n")

    def collect_all_data(self):
        """Collect all market data in parallel"""
        print("[INFO] Starting comprehensive data collection...")
        
        data_tasks = {
            "crypto": self.get_crypto_data,
            "futures": self.get_futures_sentiment,
            "fear_greed": self.get_fear_greed_index,
            "btc_dominance": self.get_btc_dominance,
            "market_cap": self.get_global_market_cap,
            "volumes": self.get_trading_volumes,
            "technical_indicators": self.get_technical_indicators,
            "historical_data": self.get_historical_price_data
        }
        
        if self.config["indicators"].get("include_macroeconomic", True):
            data_tasks.update({
                "m2_supply": self.get_m2_money_supply,
                "inflation": self.get_inflation_data,
                "interest_rates": self.get_interest_rates
            })
        
        if self.config["indicators"].get("include_stock_indices", True):
            data_tasks["stock_indices"] = self.get_stock_indices
        
        if self.config["indicators"].get("include_commodities", True):
            data_tasks["commodities"] = self.get_commodity_prices
        
        if self.config["indicators"].get("include_social_metrics", True):
            data_tasks["social_metrics"] = self.get_crypto_social_metrics
        
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(data_tasks)) as executor:
            future_to_task = {executor.submit(func): task_name for task_name, func in data_tasks.items()}
            
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
        print(f"\n[INFO] 📊 Data collection complete: {data_points_collected}/47 data points")
        
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
        
        return count

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
            "include_social_metrics": True
        }
    }
    
    collector = CryptoDataCollector(test_config)
    results = collector.collect_all_data()
    
    print(f"\nData collection test complete!")
    print(f"Results keys: {list(results.keys())}") 