#!/usr/bin/env python3

import json
from data_collector import create_data_collector
from config import load_config

def test_data_collection():
    print("Testing data collection...")
    
    # Load config
    config = load_config()
    
    # Create collector
    collector = create_data_collector(config)
    
    # Collect data
    print("Collecting data...")
    data = collector.collect_all_data()
    
    # Count data points
    data_points = collector._count_data_points(data)
    print(f"\nData points collected: {data_points}/54")
    
    # Show what data is available
    print("\nAvailable data sources:")
    for key, value in data.items():
        status = "✅" if value is not None else "❌"
        print(f"  {status} {key}")
    
    # Check specific data that AI predictor needs
    print("\nChecking AI predictor requirements:")
    
    # Super High Priority data
    print("\n🔥 SUPER HIGH PRIORITY:")
    economic_cal = data.get("economic_calendar")
    print(f"  Economic Calendar: {'✅' if economic_cal else '❌'}")
    
    volatility_regime = data.get("volatility_regime")
    print(f"  Volatility Regime: {'✅' if volatility_regime else '❌'}")
    
    # High Priority data
    print("\n🚨 HIGH PRIORITY:")
    liquidation_map = data.get("liquidation_heatmap")
    print(f"  Liquidation Heatmap: {'✅' if liquidation_map else '❌'}")
    
    rates_data = data.get("interest_rates", {})
    t10_yield = rates_data.get("t10_yield") if rates_data else None
    print(f"  10Y Treasury Yield: {'✅' if t10_yield is not None else '❌'}")
    
    # Medium Priority data
    print("\n⚠️ MEDIUM PRIORITY:")
    order_book = data.get("order_book_analysis")
    print(f"  Order Book Analysis: {'✅' if order_book else '❌'}")
    
    volumes = data.get("volumes", {})
    btc_volume = volumes.get("btc_volume") if volumes else None
    eth_volume = volumes.get("eth_volume") if volumes else None
    print(f"  Trading Volumes: {'✅' if btc_volume and eth_volume else '❌'}")
    
    whale_data = data.get("whale_movements")
    print(f"  Whale Movements: {'✅' if whale_data else '❌'}")
    
    # Low Priority data
    print("\n🟢 LOW PRIORITY:")
    fear_greed = data.get("fear_greed", {})
    fg_index = fear_greed.get("index") if fear_greed else None
    print(f"  Fear & Greed: {'✅' if fg_index else '❌'}")
    
    multi_sentiment = data.get("multi_source_sentiment")
    print(f"  Multi-Source Sentiment: {'✅' if multi_sentiment else '❌'}")
    
    technicals = data.get("technical_indicators", {})
    btc_tech = technicals.get("BTC", {}) if technicals else {}
    eth_tech = technicals.get("ETH", {}) if technicals else {}
    print(f"  Technical Indicators: {'✅' if btc_tech and eth_tech else '❌'}")
    
    # Additional Context
    print("\n🔴 ADDITIONAL CONTEXT:")
    futures = data.get("futures", {})
    btc_futures = futures.get("BTC", {}) if futures else {}
    eth_futures = futures.get("ETH", {}) if futures else {}
    print(f"  Futures Data: {'✅' if btc_futures and eth_futures else '❌'}")
    
    btc_dominance = data.get("btc_dominance")
    print(f"  BTC Dominance: {'✅' if btc_dominance else '❌'}")
    
    # Macroeconomic data
    print("\n🔵 MACROECONOMIC:")
    m2_data = data.get("m2_supply", {})
    m2_supply = m2_data.get("m2_supply") if m2_data else None
    print(f"  M2 Money Supply: {'✅' if m2_supply else '❌'}")
    
    inflation_data = data.get("inflation", {})
    inflation_rate = inflation_data.get("inflation_rate") if inflation_data else None
    print(f"  Inflation Rate: {'✅' if inflation_rate is not None else '❌'}")
    
    stock_indices = data.get("stock_indices", {})
    sp500 = stock_indices.get("sp500") if stock_indices else None
    print(f"  Stock Indices: {'✅' if sp500 is not None else '❌'}")
    
    commodities = data.get("commodities", {})
    gold = commodities.get("gold") if commodities else None
    print(f"  Commodities: {'✅' if gold is not None else '❌'}")
    
    social_metrics = data.get("social_metrics", {})
    forum_posts = social_metrics.get("forum_posts") if social_metrics else None
    print(f"  Social Metrics: {'✅' if forum_posts else '❌'}")
    
    # Historical data
    print("\n🕐 HISTORICAL CONTEXT:")
    historical = data.get("historical_data", {})
    btc_historical = historical.get("BTC") if historical else None
    eth_historical = historical.get("ETH") if historical else None
    print(f"  Historical Data: {'✅' if btc_historical and eth_historical else '❌'}")
    
    # Check for missing API keys
    print("\n🔑 API KEY STATUS:")
    config = load_config()
    api_keys = config.get("api_keys", {})
    
    required_keys = {
        "openai": "OpenAI API Key",
        "fred": "FRED API Key", 
        "alphavantage": "Alpha Vantage API Key"
    }
    
    enhanced_keys = {
        "COINMARKETCAL_API_KEY": "CoinMarketCal API Key",
        "NEWS_API_KEY": "News API Key",
        "BINANCE_API_KEY": "Binance API Key",
        "BINANCE_SECRET": "Binance Secret",
        "ETHERSCAN_API_KEY": "Etherscan API Key",
        "POLYGON_API_KEY": "Polygon API Key"
    }
    
    print("Required API Keys:")
    for key, name in required_keys.items():
        value = api_keys.get(key)
        status = "✅" if value and value != f"YOUR_{key.upper()}_API_KEY" else "❌"
        print(f"  {status} {name}")
    
    print("\nEnhanced Data API Keys:")
    import os
    for key, name in enhanced_keys.items():
        value = os.getenv(key)
        status = "✅" if value else "❌"
        print(f"  {status} {name}")
    
    return data

if __name__ == "__main__":
    test_data_collection() 