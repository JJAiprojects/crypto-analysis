#!/usr/bin/env python3

import os
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from data_collector import CryptoDataCollector

# Load .env file
load_dotenv()

class DataAnalysisGrok:
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY not configured")
        
        self.url = "https://api.x.ai/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def collect_market_data(self):
        """Collect all market data using the existing data collector"""
        print("[INFO] Collecting comprehensive market data...")
        
        try:
            # Load configuration with all environment variables
            config = {
                "api_keys": {
                    "xai": os.getenv("XAI_API_KEY"),
                    "openai": os.getenv("OPENAI_API_KEY"),
                    "fred": os.getenv("FRED_API_KEY"),
                    "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY"),
                    "coinmarketcal": os.getenv("COINMARKETCAL_API_KEY"),
                    "newsapi": os.getenv("NEWS_API_KEY"),
                    "binance_api": os.getenv("BINANCE_API_KEY"),
                    "binance_secret": os.getenv("BINANCE_SECRET"),
                    "etherscan": os.getenv("ETHERSCAN_API_KEY"),
                    "polygon": os.getenv("POLYGON_API_KEY")
                },
                "telegram": {
                    "enabled": True,
                    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
                    "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
                    "test": {
                        "enabled": True,
                        "bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN"),
                        "chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID")
                    }
                },
                "indicators": {
                    "include_macroeconomic": True,
                    "include_stock_indices": True,
                    "include_commodities": True,
                    "include_social_metrics": True,
                    "include_enhanced_data": True
                },
                "minimum_data_points": 46
            }
            
            # Use existing data collector
            collector = CryptoDataCollector(config)
            market_data = collector.collect_all_data()
            
            print(f"[INFO] ✅ Data collection completed")
            print(f"[INFO] Data points collected: {self._count_data_points(market_data)}")
            
            return market_data
            
        except Exception as e:
            print(f"[ERROR] Data collection failed: {e}")
            return None
    
    def _count_data_points(self, data):
        """Count the number of valid data points collected"""
        count = 0
        
        # 1. Crypto Prices (2 points)
        crypto = data.get("crypto", {})
        if crypto.get("btc"): count += 1
        if crypto.get("eth"): count += 1
        
        # 2. Technical Indicators (12 points: 6 per coin)
        tech = data.get("technical_indicators", {})
        for coin in ["BTC", "ETH"]:
            coin_data = tech.get(coin, {})
            if coin_data:
                if coin_data.get('rsi14') is not None: count += 1
                if coin_data.get('signal'): count += 1
                if coin_data.get('support') is not None: count += 1
                if coin_data.get('resistance') is not None: count += 1
                if coin_data.get('trend'): count += 1
                if coin_data.get('volatility'): count += 1
        
        # 3. Futures Sentiment (8 points: 4 per coin)
        futures = data.get("futures", {})
        for coin in ["BTC", "ETH"]:
            coin_data = futures.get(coin, {})
            if coin_data:
                if coin_data.get('funding_rate') is not None: count += 1
                if coin_data.get('long_short_ratio') is not None: count += 1
                if coin_data.get('open_interest') is not None: count += 1
                if coin_data.get('basis') is not None: count += 1
        
        # 4. Fear & Greed (1 point)
        if data.get("fear_greed", {}).get("index"): count += 1
        
        # 5. BTC Dominance (1 point)
        if data.get("btc_dominance") is not None: count += 1
        
        # 6. Global Market Cap (1 point)
        if data.get("market_cap"): count += 1
        
        # 7. Trading Volumes (2 points)
        volumes = data.get("volumes", {})
        if volumes.get("btc_volume"): count += 1
        if volumes.get("eth_volume"): count += 1
        
        # 8. Technical Analysis (6 points: 3 per coin)
        for coin in ["BTC", "ETH"]:
            coin_data = tech.get(coin, {})
            if coin_data:
                if coin_data.get('sma_20') is not None: count += 1
                if coin_data.get('sma_50') is not None: count += 1
                if coin_data.get('macd') is not None: count += 1
        
        # 9. Support/Resistance (4 points: 2 per coin)
        for coin in ["BTC", "ETH"]:
            coin_data = tech.get(coin, {})
            if coin_data:
                if coin_data.get('support') is not None: count += 1
                if coin_data.get('resistance') is not None: count += 1
        
        # 10. Historical Data (4 points: 2 per coin)
        historical = data.get("historical_data", {})
        for coin in ["BTC", "ETH"]:
            coin_data = historical.get(coin, {})
            if coin_data:
                if coin_data.get('1h'): count += 1
                if coin_data.get('4h'): count += 1
        
        # 11. Macroeconomic Data (4 points)
        if data.get("inflation", {}).get("cpi"): count += 1
        if data.get("interest_rates", {}).get("t10_yield"): count += 1
        if data.get("stock_indices", {}).get("sp500"): count += 1
        if data.get("commodities", {}).get("gold"): count += 1
        
        # 12. Enhanced Data Sources (if available)
        if data.get("order_book_analysis"): count += 1
        if data.get("liquidation_heatmap"): count += 1
        if data.get("economic_calendar"): count += 1
        if data.get("multi_source_sentiment"): count += 1
        if data.get("whale_movements"): count += 1
        if data.get("volatility_regime"): count += 1
        if data.get("m2_supply"): count += 1
        
        return count
    
    def analyze_data_quality(self, market_data):
        """Ask Grok to analyze the data quality and suggest improvements"""
        print("[INFO] Analyzing data quality with Grok...")
        
        # Create a comprehensive summary of the data
        data_summary = self._create_data_summary(market_data)
        
        # Create the analysis prompt
        system_prompt = """You are a senior data scientist and quantitative analyst specializing in cryptocurrency markets. 

Your task is to analyze the quality and completeness of market data being used for crypto trading predictions.

Please provide a detailed analysis covering:

1. DATA COVERAGE ASSESSMENT
   - What percentage of critical market data is captured?
   - Which key data sources are missing or incomplete?
   - Are there any significant gaps in the data collection?

2. DATA QUALITY EVALUATION
   - How reliable and accurate is each data source?
   - Are there any potential biases or limitations?
   - How fresh and timely is the data?

3. MISSING CRITICAL DATA
   - What additional data sources would significantly improve prediction accuracy?
   - Which market indicators are most important but currently missing?
   - What alternative data sources should be considered?

4. IMPROVEMENT RECOMMENDATIONS
   - Specific data sources to add
   - Data collection frequency improvements
   - Quality control measures
   - Priority order for implementation

5. CONFIDENCE ASSESSMENT
   - How confident can we be in predictions with current data?
   - What would be the expected accuracy improvement with suggested additions?

Be specific, actionable, and prioritize recommendations by impact vs. implementation difficulty."""

        user_prompt = f"""Please analyze this cryptocurrency market data collection:

{data_summary}

Focus on identifying what additional data would most improve prediction accuracy and how to implement those improvements."""

        payload = {
            "model": "grok-4",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 6000,
            "temperature": 0.7
        }
        
        try:
            print("[INFO] Sending data analysis request to Grok...")
            response = requests.post(self.url, headers=self.headers, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            analysis = result["choices"][0]["message"]["content"]
            return analysis
            
        except Exception as e:
            print(f"[ERROR] Data analysis failed: {e}")
            return f"Data analysis failed: {str(e)}"
    
    def _create_data_summary(self, market_data):
        """Create a comprehensive summary of the collected data"""
        summary = []
        
        # Basic market data
        crypto = market_data.get("crypto", {})
        summary.append(f"CRYPTO PRICES:")
        summary.append(f"  BTC: ${crypto.get('btc', 'N/A'):,}" if crypto.get('btc') else "  BTC: N/A")
        summary.append(f"  ETH: ${crypto.get('eth', 'N/A'):,}" if crypto.get('eth') else "  ETH: N/A")
        
        # Technical indicators
        tech = market_data.get("technical_indicators", {})
        summary.append(f"\nTECHNICAL INDICATORS:")
        for coin in ["BTC", "ETH"]:
            coin_data = tech.get(coin, {})
            if coin_data:
                summary.append(f"  {coin}: RSI={coin_data.get('rsi14', 'N/A')}, Signal={coin_data.get('signal', 'N/A')}, Trend={coin_data.get('trend', 'N/A')}")
        
        # Market sentiment
        fear_greed = market_data.get("fear_greed", {})
        summary.append(f"\nMARKET SENTIMENT:")
        summary.append(f"  Fear & Greed Index: {fear_greed.get('index', 'N/A')} ({fear_greed.get('sentiment', 'N/A')})")
        summary.append(f"  BTC Dominance: {market_data.get('btc_dominance', 'N/A')}%")
        
        # Volumes
        volumes = market_data.get("volumes", {})
        summary.append(f"\nTRADING VOLUMES:")
        summary.append(f"  BTC 24h Volume: ${volumes.get('btc_volume', 0)/1e9:.1f}B" if volumes.get('btc_volume') else "  BTC 24h Volume: N/A")
        summary.append(f"  ETH 24h Volume: ${volumes.get('eth_volume', 0)/1e9:.1f}B" if volumes.get('eth_volume') else "  ETH 24h Volume: N/A")
        
        # Futures data
        futures = market_data.get("futures", {})
        summary.append(f"\nFUTURES DATA:")
        for coin in ["BTC", "ETH"]:
            coin_data = futures.get(coin, {})
            if coin_data:
                summary.append(f"  {coin}: Funding={coin_data.get('funding_rate', 'N/A')}%, OI=${coin_data.get('open_interest', 0)/1e9:.1f}B" if coin_data.get('open_interest') else f"  {coin}: Funding={coin_data.get('funding_rate', 'N/A')}%")
        
        # Macroeconomic data
        summary.append(f"\nMACROECONOMIC DATA:")
        inflation = market_data.get("inflation", {})
        rates = market_data.get("interest_rates", {})
        stocks = market_data.get("stock_indices", {})
        summary.append(f"  CPI Inflation: {inflation.get('cpi', 'N/A')}%")
        summary.append(f"  10Y Treasury: {rates.get('t10_yield', 'N/A')}%")
        summary.append(f"  S&P 500: {stocks.get('sp500', 'N/A'):,}" if stocks.get('sp500') else "  S&P 500: N/A")
        
        # Enhanced data sources
        summary.append(f"\nENHANCED DATA SOURCES:")
        enhanced_sources = [
            ("Order Book Analysis", market_data.get("order_book_analysis")),
            ("Liquidation Heatmap", market_data.get("liquidation_heatmap")),
            ("Economic Calendar", market_data.get("economic_calendar")),
            ("Multi-Source Sentiment", market_data.get("multi_source_sentiment")),
            ("Whale Movements", market_data.get("whale_movements")),
            ("Volatility Regime", market_data.get("volatility_regime")),
            ("M2 Money Supply", market_data.get("m2_supply"))
        ]
        
        for name, data in enhanced_sources:
            status = "✅ Available" if data else "❌ Missing"
            summary.append(f"  {name}: {status}")
        
        # Data points count
        data_points = self._count_data_points(market_data)
        summary.append(f"\nDATA POINTS SUMMARY:")
        summary.append(f"  Total Data Points: {data_points}/54")
        summary.append(f"  Coverage: {(data_points/54)*100:.1f}%")
        
        return "\n".join(summary)
    
    def run_analysis(self):
        """Run the complete data analysis workflow"""
        print("=" * 60)
        print("🔍 GROK DATA QUALITY ANALYSIS")
        print("=" * 60)
        
        # Step 1: Collect data
        market_data = self.collect_market_data()
        if not market_data:
            print("[ERROR] Failed to collect market data")
            return
        
        # Step 2: Analyze with Grok
        analysis = self.analyze_data_quality(market_data)
        
        # Step 3: Display results
        print("\n" + "=" * 60)
        print("📊 GROK DATA ANALYSIS RESULTS")
        print("=" * 60)
        print(analysis)
        
        # Step 4: Save results
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"grok_data_analysis_{timestamp}.txt"
        
        with open(filename, "w") as f:
            f.write("GROK DATA QUALITY ANALYSIS\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")
            f.write(analysis)
        
        print(f"\n[INFO] ✅ Analysis saved to: {filename}")

if __name__ == "__main__":
    try:
        analyzer = DataAnalysisGrok()
        analyzer.run_analysis()
    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}") 