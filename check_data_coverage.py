#!/usr/bin/env python3

import json
from data_collector import CryptoDataCollector

def check_data_coverage():
    """Compare current data collection with user requirements"""
    
    # User's required data points
    required_data = {
        "Price Data (CoinGecko & Binance)": [
            "BTC price (USD)",
            "ETH price (USD)", 
            "BTC trading volume (24h)",
            "ETH trading volume (24h)"
        ],
        "Futures & Derivatives Data (Binance)": [
            "BTC & ETH Funding Rates",
            "Long/Short Account Ratios",
            "Open Interest Values",
            "Long ratio percentage",
            "Short ratio percentage"
        ],
        "Market Structure Data (CoinGecko)": [
            "BTC Dominance (percentage)",
            "Global Market Cap (total USD)",
            "Market Cap Change (24h percentage)"
        ],
        "Sentiment Indicators (Alternative.me)": [
            "Fear & Greed Index (0-100 scale)",
            "Fear & Greed Classification (text)"
        ],
        "Technical Analysis Data": [
            "OHLCV Data (Open, High, Low, Close, Volume)",
            "Current prices for BTC/ETH",
            "Moving Averages: SMA7, SMA14, SMA50",
            "RSI (14-period) for both assets",
            "Dynamic support levels",
            "Dynamic resistance levels",
            "Average True Range (ATR)",
            "Volatility classification (high/medium/low)",
            "Trend direction (bullish/bearish/neutral)",
            "RSI momentum zones",
            "Volume trends (increasing/decreasing/stable)",
            "Signal strength (BUY/SELL/STRONG BUY/STRONG SELL/NEUTRAL)",
            "Signal confidence (0-10 scale)",
            "Risk levels (1-10 scale)"
        ],
        "Historical Data (yfinance)": [
            "1-hour candles (2 days of data)",
            "4-hour candles (7 days of data)", 
            "Daily candles (30 days of data)",
            "Timestamps",
            "OHLCV data",
            "Calculated ATR values"
        ],
        "Macroeconomic Indicators": [
            "M2 Money Supply (total USD)",
            "M2 Supply Date (last update)",
            "CPI Inflation Rate (year-over-year %)",
            "Monthly inflation trends",
            "Inflation date (last update)",
            "Federal Funds Rate",
            "10-Year Treasury Yield (^TNX)",
            "5-Year Treasury Yield (^FVX)",
            "Rate dates (last updates)"
        ],
        "Stock Market Context (yfinance)": [
            "S&P 500 (^GSPC) - price & 24h change",
            "Dow Jones (^DJI) - price & 24h change",
            "NASDAQ (^IXIC) - price & 24h change",
            "VIX Volatility Index (^VIX) - current level"
        ],
        "Commodity Prices (yfinance)": [
            "Gold (GC=F) - current price",
            "Silver (SI=F) - current price", 
            "Crude Oil (CL=F) - current price",
            "Natural Gas (NG=F) - current price"
        ],
        "Social & Development Metrics": [
            "BitcoinTalk forum stats (posts, topics)",
            "Bitcoin Core stars (bitcoin/bitcoin)",
            "Ethereum stars (ethereum/go-ethereum)",
            "Recent commits count for both projects"
        ]
    }
    
    print("=" * 80)
    print("📊 DATA COVERAGE ANALYSIS")
    print("=" * 80)
    
    # Create data collector and collect sample data
    config = {
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
    
    print("\n🔄 Collecting data sample...")
    collector = CryptoDataCollector(config)
    data = collector.collect_all_data()
    
    print(f"\n📋 Raw data categories collected:")
    for category, content in data.items():
        if content:
            item_count = len(content) if isinstance(content, dict) else 1
            print(f"  • {category}: {item_count} items")
        else:
            print(f"  • {category}: ❌ FAILED")
    
    print(f"\n🔍 DETAILED COVERAGE CHECK:")
    print("-" * 80)
    
    coverage_summary = {"covered": 0, "missing": 0, "extras": 0}
    
    for category, requirements in required_data.items():
        print(f"\n📂 {category}")
        print("=" * len(category))
        
        for requirement in requirements:
            status = check_requirement_coverage(requirement, data)
            if status == "✅":
                coverage_summary["covered"] += 1
                print(f"  ✅ {requirement}")
            elif status == "⚠️":
                coverage_summary["covered"] += 0.5
                print(f"  ⚠️ {requirement} (partial)")
            else:
                coverage_summary["missing"] += 1
                print(f"  ❌ {requirement}")
    
    # Check for extra data we're collecting
    print(f"\n📈 ADDITIONAL DATA COLLECTED:")
    print("=" * 30)
    
    extras = find_extra_data(data, required_data)
    for extra in extras:
        coverage_summary["extras"] += 1
        print(f"  + {extra}")
    
    # Summary
    total_required = sum(len(reqs) for reqs in required_data.values())
    coverage_pct = (coverage_summary["covered"] / total_required) * 100
    
    print(f"\n📊 COVERAGE SUMMARY:")
    print("=" * 20)
    print(f"✅ Covered: {coverage_summary['covered']}/{total_required} ({coverage_pct:.1f}%)")
    print(f"❌ Missing: {coverage_summary['missing']}")
    print(f"➕ Extra: {coverage_summary['extras']}")
    
    if coverage_pct >= 90:
        print(f"\n🎉 EXCELLENT COVERAGE! Most requirements met.")
    elif coverage_pct >= 75:
        print(f"\n✅ GOOD COVERAGE! Minor gaps to address.")
    else:
        print(f"\n⚠️ COVERAGE GAPS! Need to address missing data points.")
    
    return data, coverage_summary

def check_requirement_coverage(requirement, data):
    """Check if a specific requirement is covered by collected data"""
    req_lower = requirement.lower()
    
    # Price Data checks
    if "btc price" in req_lower:
        return "✅" if data.get("crypto", {}).get("btc") else "❌"
    elif "eth price" in req_lower:
        return "✅" if data.get("crypto", {}).get("eth") else "❌"
    elif "btc trading volume" in req_lower:
        return "✅" if data.get("volumes", {}).get("btc_volume") else "❌"
    elif "eth trading volume" in req_lower:
        return "✅" if data.get("volumes", {}).get("eth_volume") else "❌"
    
    # Futures Data checks
    elif "funding rates" in req_lower:
        btc_funding = data.get("futures", {}).get("BTC", {}).get("funding_rate")
        eth_funding = data.get("futures", {}).get("ETH", {}).get("funding_rate")
        return "✅" if btc_funding and eth_funding else "❌"
    elif "long/short account ratios" in req_lower or "long ratio" in req_lower or "short ratio" in req_lower:
        btc_ratios = data.get("futures", {}).get("BTC", {})
        return "✅" if btc_ratios.get("long_ratio") and btc_ratios.get("short_ratio") else "❌"
    elif "open interest" in req_lower:
        btc_oi = data.get("futures", {}).get("BTC", {}).get("open_interest")
        return "✅" if btc_oi else "❌"
    
    # Market Structure checks
    elif "btc dominance" in req_lower:
        return "✅" if data.get("btc_dominance") else "❌"
    elif "global market cap" in req_lower:
        return "✅" if data.get("market_cap") else "❌"
    elif "market cap change" in req_lower:
        market_cap_data = data.get("market_cap")
        return "✅" if market_cap_data and len(market_cap_data) > 1 else "❌"
    
    # Sentiment checks
    elif "fear & greed index" in req_lower:
        return "✅" if data.get("fear_greed", {}).get("index") else "❌"
    elif "fear & greed classification" in req_lower:
        return "✅" if data.get("fear_greed", {}).get("sentiment") else "❌"
    
    # Technical Analysis checks
    elif any(x in req_lower for x in ["ohlcv", "current prices", "moving averages", "rsi", "support", "resistance", "atr", "volatility", "trend", "signal"]):
        tech = data.get("technical_indicators", {})
        btc_tech = tech.get("BTC", {})
        eth_tech = tech.get("ETH", {})
        return "✅" if btc_tech and eth_tech else "❌"
    
    # Historical Data checks
    elif any(x in req_lower for x in ["1-hour candles", "4-hour candles", "daily candles", "timestamps"]):
        hist = data.get("historical_data", {})
        return "✅" if hist.get("BTC") and hist.get("ETH") else "❌"
    
    # Macroeconomic checks
    elif "m2 money supply" in req_lower:
        return "✅" if data.get("m2_supply", {}).get("m2_supply") else "❌"
    elif "inflation" in req_lower:
        return "✅" if data.get("inflation", {}).get("inflation_rate") else "❌"
    elif "federal funds rate" in req_lower:
        return "✅" if data.get("interest_rates", {}).get("fed_rate") else "❌"
    elif "treasury yield" in req_lower:
        rates = data.get("interest_rates", {})
        return "✅" if rates.get("t10_yield") or rates.get("t5_yield") else "❌"
    
    # Stock Market checks
    elif any(x in req_lower for x in ["s&p 500", "dow jones", "nasdaq", "vix"]):
        indices = data.get("stock_indices", {})
        return "✅" if any(indices.get(k) for k in ["sp500", "dow_jones", "nasdaq", "vix"]) else "❌"
    
    # Commodity checks
    elif any(x in req_lower for x in ["gold", "silver", "crude oil", "natural gas"]):
        commodities = data.get("commodities", {})
        return "✅" if any(commodities.get(k) for k in ["gold", "silver", "crude_oil", "natural_gas"]) else "❌"
    
    # Social metrics checks
    elif "bitcointalk" in req_lower or "forum" in req_lower:
        return "✅" if data.get("social_metrics", {}).get("forum_posts") else "❌"
    elif "github" in req_lower or "stars" in req_lower or "commits" in req_lower:
        social = data.get("social_metrics", {})
        return "✅" if social.get("btc_github_stars") or social.get("eth_github_stars") else "❌"
    
    return "⚠️"  # Partial or uncertain match

def find_extra_data(data, required_data):
    """Find additional data points we're collecting beyond requirements"""
    extras = []
    
    # Check for additional timeframes in historical data
    hist = data.get("historical_data", {})
    if hist:
        for coin, timeframes in hist.items():
            if isinstance(timeframes, dict):
                for tf in timeframes.keys():
                    if tf in ["1wk", "1mo"]:  # These are extra beyond the 1h, 4h, 1d requirement
                        extras.append(f"Additional {tf} historical data for {coin}")
    
    # Check for additional technical indicators
    tech = data.get("technical_indicators", {})
    if tech:
        for coin, indicators in tech.items():
            if isinstance(indicators, dict):
                extra_indicators = []
                for key in indicators.keys():
                    if key not in ["price", "rsi14", "signal", "support", "resistance", "atr", "volatility", "trend"]:
                        extra_indicators.append(key)
                if extra_indicators:
                    extras.append(f"Extra {coin} indicators: {', '.join(extra_indicators)}")
    
    # Check for additional social metrics beyond requirements
    social = data.get("social_metrics", {})
    if social:
        extra_social = []
        for key in social.keys():
            if key not in ["forum_posts", "forum_topics", "btc_github_stars", "eth_github_stars", "btc_recent_commits", "eth_recent_commits"]:
                extra_social.append(key)
        if extra_social:
            extras.append(f"Extra social metrics: {', '.join(extra_social)}")
    
    return extras

if __name__ == "__main__":
    try:
        data, summary = check_data_coverage()
        
        print(f"\n💾 Saving detailed analysis...")
        with open("data_coverage_analysis.json", "w") as f:
            json.dump({
                "summary": summary,
                "sample_data_structure": {k: type(v).__name__ for k, v in data.items()},
                "timestamp": "2024-01-20"
            }, f, indent=2)
        
        print(f"✅ Analysis saved to data_coverage_analysis.json")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}") 