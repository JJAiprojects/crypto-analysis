#!/usr/bin/env python3

import os
import json
import time
import requests
from datetime import datetime, timezone
from openai import OpenAI
from telegram_utils import send_telegram_message

class AIPredictor:
    def __init__(self, config):
        self.config = config
        
        # Initialize AI provider configuration
        self.ai_provider_config = config.get("ai_provider", {
            "primary": "xai",
            "fallback": "openai",
            "enabled": {
                "xai": True,
                "openai": False
            }
        })
        
        # Get API keys
        self.xai_key = os.getenv("XAI_API_KEY") or config["api_keys"].get("xai")
        self.openai_key = os.getenv("OPENAI_API_KEY") or config["api_keys"].get("openai")
        
        # Initialize clients
        self.xai_client = None
        self.openai_client = None
        
        # Setup primary provider
        self.primary_provider = self.ai_provider_config.get("primary", "xai")
        self.fallback_provider = self.ai_provider_config.get("fallback", "openai")
        
        # Initialize enabled providers
        if self.ai_provider_config.get("enabled", {}).get("xai", True) and self.xai_key and self.xai_key != "YOUR_XAI_API_KEY":
            print("[INFO] ✅ xAI Grok client ready (direct HTTP)")
            self.xai_client = True  # Just mark as available
        
        if self.ai_provider_config.get("enabled", {}).get("openai", False) and self.openai_key and self.openai_key != "YOUR_OPENAI_API_KEY":
            try:
                self.openai_client = OpenAI(api_key=self.openai_key)
                print("[INFO] ✅ OpenAI client initialized")
            except Exception as e:
                print(f"[WARN] Failed to initialize OpenAI client: {e}")
        
        # Validate at least one provider is available
        if not self.xai_client and not self.openai_client:
            raise ValueError("No AI provider configured. Please set XAI_API_KEY or OPENAI_API_KEY")
        
        print(f"[INFO] Primary AI provider: {self.primary_provider}")
        if self.fallback_provider != self.primary_provider:
            print(f"[INFO] Fallback AI provider: {self.fallback_provider}")

    def create_comprehensive_prompt(self, market_data):
        """Create comprehensive AI prompt using all 50+ data points with 8-step decision framework"""
        
        # Extract all data safely
        crypto = market_data.get("crypto", {})
        technicals = market_data.get("technical_indicators", {})
        futures = market_data.get("futures", {})
        fear_greed = market_data.get("fear_greed", {})
        historical = market_data.get("historical_data", {})
        
        # Enhanced data sources
        order_book = market_data.get("order_book_analysis", {})
        liquidation_map = market_data.get("liquidation_heatmap", {})
        economic_cal = market_data.get("economic_calendar", {})
        multi_sentiment = market_data.get("multi_source_sentiment", {})
        whale_data = market_data.get("whale_movements", {})
        
        # Extract missing data safely (NEW)
        volatility_regime = market_data.get("volatility_regime", {})
        m2_data = market_data.get("m2_supply", {})
        
        # Network health and correlation data
        btc_network = market_data.get("btc_network_health", {})
        eth_network = market_data.get("eth_network_health", {})
        crypto_correlations = market_data.get("crypto_correlations", {})
        cross_asset_correlations = market_data.get("cross_asset_correlations", {})
        cftc_data = market_data.get("cftc_positioning", {})
        

        
        # Macroeconomic data
        inflation_data = market_data.get("inflation", {})
        rates_data = market_data.get("interest_rates", {})
        stock_indices = market_data.get("stock_indices", {})
        commodities = market_data.get("commodities", {})
        social_metrics = market_data.get("social_metrics", {})
        
        # Market structure
        btc_dominance = market_data.get("btc_dominance", 0)
        market_cap_data = market_data.get("market_cap", (0, 0))
        volumes = market_data.get("volumes", {})
        
        # Debug: Check volumes data structure
        print(f"[DEBUG] Volumes data structure: {type(volumes)}")
        print(f"[DEBUG] Volumes content: {volumes}")
        if isinstance(volumes, dict):
            print(f"[DEBUG] BTC volume type: {type(volumes.get('btc_volume'))}")
            print(f"[DEBUG] BTC volume value: {volumes.get('btc_volume')}")
            print(f"[DEBUG] ETH volume type: {type(volumes.get('eth_volume'))}")
            print(f"[DEBUG] ETH volume value: {volumes.get('eth_volume')}")
        
        # BTC and ETH specific data
        btc_data = technicals.get("BTC", {})
        eth_data = technicals.get("ETH", {})
        btc_futures = futures.get("BTC", {})
        eth_futures = futures.get("ETH", {})
        
        # Safety check: Ensure price data is numeric
        if btc_data and isinstance(btc_data.get('price'), dict):
            print(f"[WARN] BTC price data is dict, not numeric: {type(btc_data.get('price'))}")
            print(f"[DEBUG] BTC price data content: {btc_data.get('price')}")
        if eth_data and isinstance(eth_data.get('price'), dict):
            print(f"[WARN] ETH price data is dict, not numeric: {type(eth_data.get('price'))}")
            print(f"[DEBUG] ETH price data content: {eth_data.get('price')}")
        
        # Debug: Print data types for troubleshooting
        if btc_data:
            print(f"[DEBUG] BTC data types - price: {type(btc_data.get('price'))}, atr: {type(btc_data.get('atr'))}")
        if eth_data:
            print(f"[DEBUG] ETH data types - price: {type(eth_data.get('price'))}, atr: {type(eth_data.get('atr'))}")
        
        # Pre-calculate ATR percentages to avoid division errors in f-strings
        btc_atr_percentage = "N/A"
        eth_atr_percentage = "N/A"
        
        try:
            if btc_data and btc_data.get('atr') and btc_data.get('price'):
                btc_atr = self._safe_get_numeric(btc_data, 'atr', 0)
                btc_price = self._safe_get_numeric(btc_data, 'price', 1)
                # Double-check that we got numeric values
                if isinstance(btc_atr, (int, float)) and isinstance(btc_price, (int, float)) and btc_price > 0:
                    btc_atr_percentage = f"{(btc_atr / btc_price) * 100:.1f}"
                else:
                    print(f"[WARN] BTC price or ATR not numeric: atr={type(btc_atr)}, price={type(btc_price)}")
                    btc_atr_percentage = "N/A"
        except Exception as e:
            print(f"[WARN] BTC ATR percentage calculation failed: {e}")
            btc_atr_percentage = "N/A"
            
        try:
            if eth_data and eth_data.get('atr') and eth_data.get('price'):
                eth_atr = self._safe_get_numeric(eth_data, 'atr', 0)
                eth_price = self._safe_get_numeric(eth_data, 'price', 1)
                # Double-check that we got numeric values
                if isinstance(eth_atr, (int, float)) and isinstance(eth_price, (int, float)) and eth_price > 0:
                    eth_atr_percentage = f"{(eth_atr / eth_price) * 100:.1f}"
                else:
                    print(f"[WARN] ETH price or ATR not numeric: atr={type(eth_atr)}, price={type(eth_price)}")
                    eth_atr_percentage = "N/A"
        except Exception as e:
            print(f"[WARN] ETH ATR percentage calculation failed: {e}")
            eth_atr_percentage = "N/A"
        
        # Count actual data points being used
        data_points_used = self._count_available_data(market_data)
        
        # Check data quality and add warnings to prompt
        data_quality_warnings = []
        critical_sources = ['order_book_analysis', 'liquidation_heatmap', 'economic_calendar']
        
        for source in critical_sources:
            if not market_data.get(source):
                data_quality_warnings.append(f"⚠️ {source.replace('_', ' ').title()} data unavailable")
        
        # Check for correlation data availability
        correlation_sources = ['crypto_correlations', 'cross_asset_correlations']
        for source in correlation_sources:
            if not market_data.get(source):
                data_quality_warnings.append(f"⚠️ {source.replace('_', ' ').title()} data unavailable")
        
        # Check for CFTC data availability
        if not cftc_data:
            data_quality_warnings.append(f"⚠️ CFTC Positioning data unavailable")
        
        # Check for network health data availability
        if not btc_network:
            data_quality_warnings.append(f"⚠️ BTC Network Health data unavailable")
        if not eth_network:
            data_quality_warnings.append(f"⚠️ ETH Network Health data unavailable")
        
        # Create comprehensive data completeness tracker
        data_completeness_tracker = self._create_data_completeness_tracker(market_data)
        
        data_quality_header = ""
        if data_quality_warnings:
            data_quality_header = f"""

🚨 DATA QUALITY WARNINGS:
{chr(10).join(data_quality_warnings)}

⚠️ CRITICAL: You are working with incomplete market structure data. 
   - Order book analysis unavailable: Cannot assess smart money flow
   - Liquidation heatmap unavailable: Cannot identify price targets
   - Economic calendar unavailable: Cannot assess market timing risks
   - CFTC positioning unavailable: Cannot assess institutional sentiment
   - Network health unavailable: Cannot assess fundamental network strength
   - Correlation data unavailable: Cannot assess BTC-ETH relationship and cross-asset dynamics

⚠️ RECOMMENDATION: If these warnings appear, DO NOT make trading predictions.
   Instead, explain why predictions would be unreliable and what data is needed.
"""
        
        # Add data completeness tracker to header
        data_quality_header += f"""

📊 DATA COMPLETENESS TRACKER ({data_points_used}/65 points):
{data_completeness_tracker}

⚠️ DATA COMPLETENESS RULES:
- ✅ Available: Data point successfully collected and usable
- ❌ Missing: Data point failed to collect or unavailable
- <50 points: INSUFFICIENT_DATA - Recommend FLAT POSITION
- 50-59 points: LIMITED_ANALYSIS - Reduce confidence by 10-15%
- 60+ points: SUFFICIENT_DATA - Normal analysis possible

🚨 DATA COMPLETENESS ALERT:
"""
        
        # Add specific alerts based on data completeness
        if data_points_used < 50:
            data_quality_header += f"""
🚨 INSUFFICIENT_DATA - FLAT POSITION RECOMMENDED
   - Only {data_points_used}/65 data points available
   - Missing critical market structure data
   - Cannot provide reliable trading analysis
   - RECOMMENDATION: FLAT POSITION - Wait for better data
"""
        elif data_points_used < 60:
            data_quality_header += f"""
⚠️ LIMITED_ANALYSIS - REDUCE CONFIDENCE
   - Only {data_points_used}/65 data points available
   - Some critical data missing
   - Reduce confidence by 10-15%
   - RECOMMENDATION: Conservative position sizing
"""
        else:
            data_quality_header += f"""
✅ SUFFICIENT_DATA - NORMAL ANALYSIS
   - {data_points_used}/65 data points available
   - Sufficient data for reliable analysis
   - Normal confidence levels appropriate
"""
        
        prompt = f"""You are a professional crypto trader with 15+ years experience.{data_quality_header}

⚠️ CRITICAL: Follow the 8-STEP ENHANCED DECISION FRAMEWORK internally. Output only the final CONCISE trading outlook.

🚨 DATA COMPLETENESS RULE: If data completeness <50% (<32/65 points), output "INSUFFICIENT_DATA - FLAT POSITION" and skip analysis.

MARKET DATA HIERARCHY ({data_points_used}/65 indicators):
=========================================================

🔥 SUPER HIGH PRIORITY (Absolute Override - Can Force Flat Position):
• Economic Calendar: {economic_cal.get('recommendation', 'N/A') if economic_cal else 'API_KEY_MISSING'} | High Impact: {economic_cal.get('high_impact', 0) if economic_cal else 0} | Next: {economic_cal.get('next_high_impact', {}).get('title', 'None')[:30] if economic_cal and economic_cal.get('next_high_impact') else 'None'}
• Volatility Regime: {volatility_regime.get('current_regime', 'N/A')} | Size Multiplier: {volatility_regime.get('size_multiplier', 1.0):.1f}x | Risk: {volatility_regime.get('risk_state', 'N/A')}
• CFTC Positioning: {cftc_data.get('institutional_sentiment', 'N/A')} | Commercial: {cftc_data.get('commercial_signal', 'N/A')} | Contrarian: {cftc_data.get('contrarian_signal', 'N/A')} | Smart Money: {f"{cftc_data.get('smart_money_net', 0):+,.0f}" if cftc_data.get('smart_money_net') is not None else 'N/A'}

🚨 HIGH PRIORITY (Override Traditional S/R & Price Targets):
• Liquidation BTC: {liquidation_map.get('BTC', {}).get('liquidation_pressure', 'N/A') if liquidation_map else 'API_KEY_MISSING'} | Funding: {f"{liquidation_map.get('BTC', {}).get('funding_rate', 0):.3f}" if liquidation_map and liquidation_map.get('BTC') and liquidation_map.get('BTC', {}).get('funding_rate') is not None else 'N/A'}% | Zones: {len(liquidation_map.get('BTC', {}).get('nearby_long_liquidations', []))} / {len(liquidation_map.get('BTC', {}).get('nearby_short_liquidations', []))}
• Liquidation ETH: {liquidation_map.get('ETH', {}).get('liquidation_pressure', 'N/A') if liquidation_map else 'API_KEY_MISSING'} | Funding: {f"{liquidation_map.get('ETH', {}).get('funding_rate', 0):.3f}" if liquidation_map and liquidation_map.get('ETH') and liquidation_map.get('ETH', {}).get('funding_rate') is not None else 'N/A'}% | Zones: {len(liquidation_map.get('ETH', {}).get('nearby_long_liquidations', []))} / {len(liquidation_map.get('ETH', {}).get('nearby_short_liquidations', []))}
• Bond Market: 10Y Treasury: {f"{rates_data.get('t10_yield'):.2f}" if rates_data.get('t10_yield') is not None else 'N/A'}% | Risk-Off: {'BREACHED' if rates_data.get('t10_yield') is not None and rates_data.get('t10_yield') > 4.5 else 'NORMAL'} | Impact: {self._assess_treasury_impact(rates_data.get('t10_yield'))}

⚠️ MEDIUM PRIORITY (Entry Timing & Smart Money Flow):
• Order Book BTC: {order_book.get('BTC', {}).get('book_signal', 'N/A') if order_book else 'API_KEY_MISSING'} | Imbalance: {f"{order_book.get('BTC', {}).get('imbalance_ratio', 0)*100:.1f}" if order_book and order_book.get('BTC') and order_book.get('BTC', {}).get('imbalance_ratio') is not None else 'N/A'}% | MM: {f"{order_book.get('BTC', {}).get('mm_dominance', 0)*100:.1f}" if order_book and order_book.get('BTC') and order_book.get('BTC', {}).get('mm_dominance') is not None else 'N/A'}%
• Order Book ETH: {order_book.get('ETH', {}).get('book_signal', 'N/A') if order_book else 'API_KEY_MISSING'} | Imbalance: {f"{order_book.get('ETH', {}).get('imbalance_ratio', 0)*100:.1f}" if order_book and order_book.get('ETH') and order_book.get('ETH', {}).get('imbalance_ratio') is not None else 'N/A'}% | MM: {f"{order_book.get('ETH', {}).get('mm_dominance', 0)*100:.1f}" if order_book and order_book.get('ETH') and order_book.get('ETH', {}).get('mm_dominance') is not None else 'N/A'}%
• Volume BTC: ${f"{volumes.get('btc_volume', 0)/1e9:.1f}" if volumes.get('btc_volume') else 'N/A'}B | Trend: {btc_data.get('volume_trend', 'N/A')} | Signal: {self._analyze_volume_signal('BTC', volumes, btc_data)}
• Volume ETH: ${f"{volumes.get('eth_volume', 0)/1e9:.1f}" if volumes.get('eth_volume') else 'N/A'}B | Trend: {eth_data.get('volume_trend', 'N/A')} | Signal: {self._analyze_volume_signal('ETH', volumes, eth_data)}
• Whale: {whale_data.get('whale_signal', 'N/A') if whale_data else 'API_KEY_MISSING'} | Sentiment: {f"{whale_data.get('whale_sentiment', 0):.2f}" if whale_data and whale_data.get('whale_sentiment') is not None else 'N/A'} | Signals: {whale_data.get('signals_detected', 0) if whale_data else 0}
• Smart Money: {whale_data.get('breakdown', {}).get('large_trades', {}).get('activity', 'N/A') if whale_data and whale_data.get('breakdown') and whale_data.get('breakdown', {}).get('large_trades') else 'N/A'} | Flows: {whale_data.get('breakdown', {}).get('exchange_flows', {}).get('activity', 'N/A') if whale_data and whale_data.get('breakdown') and whale_data.get('breakdown', {}).get('exchange_flows') else 'N/A'}
• BTC Network: Hash: {f"{btc_network.get('hash_rate_th_s', 0)/1e12:.1f}" if btc_network and btc_network.get('hash_rate_th_s') else 'N/A'} TH/s | Diff: {f"{btc_network.get('mining_difficulty', 0)/1e12:.1f}" if btc_network and btc_network.get('mining_difficulty') else 'N/A'}T | Mempool: {f"{btc_network.get('mempool_unconfirmed', 0):,}" if btc_network and btc_network.get('mempool_unconfirmed') is not None else 'N/A'} tx | Addr: {f"{btc_network.get('active_addresses_trend', {}).get('total_unique_addresses', 0):,}" if btc_network and btc_network.get('active_addresses_trend') is not None else 'N/A'}
• ETH Network: Gas: {f"{eth_network.get('gas_prices', {}).get('pressure_ratio', 0):.2f}" if eth_network and eth_network.get('gas_prices', {}).get('pressure_ratio') is not None else 'N/A'}x | Supply: {f"{eth_network.get('total_supply', {}).get('total_eth_supply', 0)/1e6:.1f}" if eth_network and eth_network.get('total_supply') else 'N/A'}M ETH | Block: {f"{eth_network.get('current_block', {}).get('block_height', 0):,}" if eth_network and eth_network.get('current_block', {}).get('block_height') is not None else 'N/A'}
• Crypto Correlations: BTC-ETH 30d: {f"{crypto_correlations.get('btc_eth_correlation_30d', 0):.3f}" if crypto_correlations and crypto_correlations.get('btc_eth_correlation_30d') is not None else 'N/A'} | Strength: {crypto_correlations.get('correlation_strength', 'N/A')} | Direction: {crypto_correlations.get('correlation_direction', 'N/A')} | Trend: {crypto_correlations.get('correlation_trend', 'N/A')}
• Cross-Asset Correlations: Market Regime: {cross_asset_correlations.get('market_regime', 'N/A')} | Crypto-Equity: {cross_asset_correlations.get('crypto_equity_regime', 'N/A')} | SP500 Change: {f"{cross_asset_correlations.get('sp500_change_24h', 0):+.2f}" if cross_asset_correlations and cross_asset_correlations.get('sp500_change_24h') is not None else 'N/A'}%

🟢 LOW PRIORITY (Traditional Analysis - Confirmation Only):
• Fear & Greed: {fear_greed.get('index', 'N/A')} ({fear_greed.get('sentiment', 'N/A')})
• Multi-Sentiment: {multi_sentiment.get('sentiment_signal', 'N/A') if multi_sentiment else 'LIMITED_DATA'} | Sources: {multi_sentiment.get('sources_analyzed', 0) if multi_sentiment else 0} | Score: {f"{multi_sentiment.get('average_sentiment'):.2f}" if multi_sentiment and multi_sentiment.get('average_sentiment') is not None else 'N/A'}
• BTC: {btc_data.get('trend', 'N/A')} | ${f"{btc_data.get('price'):,}" if btc_data.get('price') else 'N/A'} | RSI: {f"{btc_data.get('rsi14'):.1f}" if btc_data.get('rsi14') is not None else 'N/A'} | {btc_data.get('signal', 'N/A')}
• ETH: {eth_data.get('trend', 'N/A')} | ${f"{eth_data.get('price'):,}" if eth_data.get('price') else 'N/A'} | RSI: {f"{eth_data.get('rsi14'):.1f}" if eth_data.get('rsi14') is not None else 'N/A'} | {eth_data.get('signal', 'N/A')}
• S&P 500: {f"{stock_indices.get('sp500'):,.0f}" if stock_indices.get('sp500') is not None else 'N/A'} | VIX: {f"{stock_indices.get('vix'):.1f}" if stock_indices.get('vix') is not None else 'N/A'}
• Market Cap: ${market_cap_data[0] if market_cap_data[0] else 0:,.0f} USD ({market_cap_data[1] if market_cap_data[1] else 0:+.1f}% 24h)
• BTC S/R (PRIMARY): ${f"{btc_data.get('support'):,}" if btc_data.get('support') else 'N/A'} / ${f"{btc_data.get('resistance'):,}" if btc_data.get('resistance') else 'N/A'} (Pivot method - USE THESE)
• ETH S/R (PRIMARY): ${f"{eth_data.get('support'):,}" if eth_data.get('support') else 'N/A'} / ${f"{eth_data.get('resistance'):,}" if eth_data.get('resistance') else 'N/A'} (Pivot method - USE THESE)

⚠️ S/R USAGE RULES:
- PRIMARY: Use pivot point levels (support/resistance) for entries and targets
- REFERENCE: ATR levels for volatility context only
- REFERENCE: SMA levels for trend context only
- RISK: Use ATR for stop loss calculations
- NEVER: Override pivot levels with ATR/SMA unless liquidation clusters present

🔧 TECHNICAL PRECISION:
- **Volatility Ratio:** Current ATR / 24h Avg ATR | >1.5 = HIGH, >2.0 = EXTREME
- BTC: ATR: ${f"{btc_data.get('atr'):,.0f}" if btc_data.get('atr') else 'N/A'} ({btc_atr_percentage}%) | SMA7/14/50: ${f"{btc_data.get('sma7'):,.0f}" if btc_data.get('sma7') else 'N/A'}/${f"{btc_data.get('sma14'):,.0f}" if btc_data.get('sma14') else 'N/A'}/${f"{btc_data.get('sma50'):,.0f}" if btc_data.get('sma50') else 'N/A'}
- BTC Levels: ATR S/R: ${f"{btc_data.get('atr_support'):,.0f}" if btc_data.get('atr_support') else 'N/A'}/${f"{btc_data.get('atr_resistance'):,.0f}" if btc_data.get('atr_resistance') else 'N/A'} | SMA S/R: ${f"{btc_data.get('sma_support'):,.0f}" if btc_data.get('sma_support') else 'N/A'}/${f"{btc_data.get('sma_resistance'):,.0f}" if btc_data.get('sma_resistance') else 'N/A'} | Vol: {btc_data.get('volume_trend', 'N/A')}
- ETH: ATR: ${f"{eth_data.get('atr'):,.0f}" if eth_data.get('atr') else 'N/A'} ({eth_atr_percentage}%) | SMA7/14/50: ${f"{eth_data.get('sma7'):,.0f}" if eth_data.get('sma7') else 'N/A'}/${f"{eth_data.get('sma14'):,.0f}" if eth_data.get('sma14') else 'N/A'}/${f"{eth_data.get('sma50'):,.0f}" if eth_data.get('sma50') else 'N/A'}
- ETH Levels: ATR S/R: ${f"{eth_data.get('atr_support'):,.0f}" if eth_data.get('atr_support') else 'N/A'}/${f"{eth_data.get('atr_resistance'):,.0f}" if eth_data.get('atr_resistance') else 'N/A'} | SMA S/R: ${f"{eth_data.get('sma_support'):,.0f}" if eth_data.get('sma_support') else 'N/A'}/${f"{eth_data.get('sma_resistance'):,.0f}" if eth_data.get('sma_resistance') else 'N/A'} | Vol: {eth_data.get('volume_trend', 'N/A')}

🔴 ADDITIONAL CONTEXT:
• Funding: BTC {f"{btc_futures.get('funding_rate'):.3f}" if btc_futures.get('funding_rate') is not None else 'N/A'}% | ETH {f"{eth_futures.get('funding_rate'):.3f}" if eth_futures.get('funding_rate') is not None else 'N/A'}%
• Long/Short: BTC {f"{btc_futures.get('long_ratio'):.0f}" if btc_futures.get('long_ratio') is not None else 'N/A'}/{f"{btc_futures.get('short_ratio'):.0f}" if btc_futures.get('short_ratio') is not None else 'N/A'} | ETH {f"{eth_futures.get('long_ratio'):.0f}" if eth_futures.get('long_ratio') is not None else 'N/A'}/{f"{eth_futures.get('short_ratio'):.0f}" if eth_futures.get('short_ratio') is not None else 'N/A'}

• BTC Dom: {btc_dominance:.1f}% | Inflation: {f"{inflation_data.get('inflation_rate'):.1f}" if inflation_data.get('inflation_rate') is not None else 'N/A'}% | Fed: {f"{rates_data.get('fed_rate'):.2f}" if rates_data.get('fed_rate') is not None else 'N/A'}%

🔵 MACRO & MARKET:
• M2: ${f"{m2_data.get('m2_supply', 0)/1e12:.1f}" if m2_data.get('m2_supply') else 'N/A'}T | Date: {m2_data.get('m2_date', 'N/A')}
• Indices: NASDAQ {f"{stock_indices.get('nasdaq'):,.0f}" if stock_indices.get('nasdaq') is not None else 'N/A'} | Dow {f"{stock_indices.get('dow_jones'):,.0f}" if stock_indices.get('dow_jones') is not None else 'N/A'}
• Metals: Gold ${f"{commodities.get('gold'):,.0f}" if commodities.get('gold') is not None else 'N/A'}/oz | Silver ${f"{commodities.get('silver'):,.2f}" if commodities.get('silver') is not None else 'N/A'}/oz
• Energy: Oil ${f"{commodities.get('crude_oil'):,.1f}" if commodities.get('crude_oil') is not None else 'N/A'}/bbl | Gas ${f"{commodities.get('natural_gas'):,.2f}" if commodities.get('natural_gas') is not None else 'N/A'}/MMBtu | Signal: {self._assess_energy_signal(commodities)}
• Social: Posts: {f"{social_metrics.get('forum_posts', 0):,}" if social_metrics.get('forum_posts') else 'N/A'} | BTC GH: {f"{social_metrics.get('btc_github_stars', 0):,}" if social_metrics.get('btc_github_stars') else 'N/A'} | ETH GH: {f"{social_metrics.get('eth_github_stars', 0):,}" if social_metrics.get('eth_github_stars') else 'N/A'}

🕐 HISTORICAL CONTEXT:
==============================================

🔵 BTC Multi-Timeframe:
- Daily: SMA20: ${self._safe_get_historical_value(historical, 'BTC', '1d', 'sma20'):,.0f} | SMA50: ${self._safe_get_historical_value(historical, 'BTC', '1d', 'sma50'):,.0f} | SMA200: ${self._safe_get_historical_value(historical, 'BTC', '1d', 'sma200'):,.0f}
- Weekly: Price vs SMA200: {self._get_sma_position(historical, 'BTC')}
- MACD: {self._get_macd_signal(historical, 'BTC', '1d')}
- Momentum: {self._analyze_momentum_state(historical.get('BTC', {}))}

📊 ETH Multi-Timeframe:  
- Daily: SMA20: ${self._safe_get_historical_value(historical, 'ETH', '1d', 'sma20'):,.0f} | SMA50: ${self._safe_get_historical_value(historical, 'ETH', '1d', 'sma50'):,.0f} | SMA200: ${self._safe_get_historical_value(historical, 'ETH', '1d', 'sma200'):,.0f}
- Weekly: Price vs SMA200: {self._get_sma_position(historical, 'ETH')}
- MACD: {self._get_macd_signal(historical, 'ETH', '1d')}
- Momentum: {self._analyze_momentum_state(historical.get('ETH', {}))}

⚡ CRITICAL OVERRIDES:
- Long-term Trend: {self._determine_longterm_trend(historical)}
- Resistance Confluence: {self._find_historical_resistance_levels(historical)}
- Momentum Alignment: {self._check_momentum_alignment(historical)}

⚠️ FORMATTING:
- Prices: Whole numbers only ($106,384 not $106,384.79)
- Use commas for thousands ($106,384, $2,454)
- Percentages: 1 decimal (0.8%, 1.2%)
- Confidence: Whole numbers (70%, 75%)

📊 DATA HANDLING:
- "N/A" values: Ignore completely, do not fabricate
- Missing sources: Reduce confidence by 10-15% per missing source
- Limited data: Flag as "LIMITED_ANALYSIS", reduce position size
- API failures: Use available data only, never assume missing values



🎯 PROBABILISTIC FORECASTING:
- Confidence = win probability estimates
- High (75-85%): Strong signal alignment, higher win rate
- Medium (60-74%): Mixed signals, moderate win rate  
- Low (45-59%): Weak signals, lower win rate
- Very low (<45%): Avoid trading, wait for better setup

ENHANCED 8-STEP INTERNAL ANALYSIS FRAMEWORK (Do NOT output these steps):
========================================================================

PRIORITY-BASED OVERRIDE LOGIC:
• 🔥 SUPER HIGH: Economic Events + Volatility Regimes = Can FORCE FLAT POSITION regardless of all other signals
• 🚨 HIGH: Liquidation Clusters = REPLACE traditional support/resistance as primary price targets
• ⚠️ MEDIUM: Order Book + Whales = GATE execution (only trade if these align with direction)
• 🟢 LOW: Traditional TA + Sentiment = Confirmation only, NEVER override higher priority signals

📋 RULE REFERENCE SYSTEM (Use for confidence adjustments):

STEP 0: CONFLICT RESOLUTION HIERARCHY:
- [R0.1] SUPER HIGH vs HIGH: Economic Events and Volatility override everything → FORCE FLAT if conflict
- [R0.2] HIGH PRIORITY: If Liquidation vs Bond Market contradict → Use MOST RECENT liquidation data, discount bond impact by 50%  
- [R0.3] MEDIUM PRIORITY: If Order Book vs Whale Movements contradict → Require 70%+ conviction on BOTH or reduce to SIDEWAYS
- [R0.4] Traditional TA conflicts with higher priorities → Ignore traditional signals completely
- [R0.5] When in doubt, choose FLAT position over conflicted trade

STEP 0.5: SIDEWAYS MARKET DETECTION & TREND VALIDATION:
- [R0.6] Check sideways consolidation: Price range <1% and RSI 40-60 over last 3h
- [R0.7] Check mixed signals: If high-priority signals conflict by >50%, flag as potential sideways
- [R0.8] BREAKOUT POTENTIAL: If sideways, check volume >1.5x 3-hour average and price within 0.5% of support/resistance
- [R0.9] IF BREAKOUT POTENTIAL: Flag for conditional breakout setup in Step 7
- [R0.10] IF SIDEWAYS: Set bias to "SIDEWAYS" and proceed to Step 7
- [R0.11] IF TRENDING: Continue with normal analysis flow
- [R0.12] TREND VALIDATION: Check last 2-3 candles for momentum changes:
  * Minimum threshold: >0.5% move required
  * Confirmation: 2 consecutive 1-hour candles in same direction with volume >10% above 3-hour average
  * Apply individually to BTC and ETH
  * If threshold met but no confirmation → Flag as potential noise
- [R0.13] REVERSAL ALERT: If >2 consecutive opposite candles with confirmation → Flag for bias adjustment
- [R0.14] RULE: SIDEWAYS covers both consolidation patterns and mixed/uncertain signals

📊 TERMINOLOGY:
- Volatility Ratio: Current ATR / Average ATR (last 24h) - measures relative volatility
- Mixed Signals >50%: When more than half of high-priority signals conflict
- Adaptive Thresholds: Signal strength requirements that adjust to market volatility
- Noise Filtering: Ignoring small price movements that don't confirm larger trends

STEP 1: Economic Event Override Check + Bond Market Check + CFTC Institutional Override
- [R1.1] If Economic Calendar shows "AVOID_TRADING" OR high-impact event in next 24h → FORCE FLAT POSITION
- [R1.2] If 10Y Treasury > 4.5% → REDUCE RISK APPETITE (smaller positions, higher stop losses)
- [R1.3] If 10Y Treasury > 5.0% → CONSIDER FLAT POSITION (bonds competing with risk assets)
- [R1.4] If Volatility Regime = "EXTREME" → Reduce position size by regime multiplier regardless of setup quality
- [R1.5] CFTC INSTITUTIONAL OVERRIDE RULES:
  * If CFTC shows "STRONG_REVERSAL_RISK" → Reduce position size by 50% regardless of other signals
  * If Smart Money vs Dumb Money ratio > 2.0 → Follow institutional direction with high confidence
  * If Commercial hedgers show strong directional bias → Weight macro trend heavily
  * If Positioning Extreme = "VERY_HIGH" → Consider flat position (contrarian opportunity)
  * [BACKTESTING] Adjust confidence +5% if CFTC signal matched last 3 similar setups

STEP 2: Liquidation Magnet Analysis (OVERRIDE TRADITIONAL S/R)
- [R2.1] Check if liquidation clusters exist within 5% of current price
- [R2.2] IF LIQUIDATION CLUSTERS FOUND: Use ONLY liquidation levels, ignore traditional S/R completely
- [R2.3] IF NO LIQUIDATION CLUSTERS: Use traditional S/R but flag as "WEAKER SIGNALS"
- [R2.4] Priority order: 1) Liquidation clusters, 2) Pivot point S/R (script-calculated), 3) ATR/SMA reference levels
- [R2.5] MANDATORY: If liquidation pressure = "HIGH" → Liquidation targets become ONLY valid targets
- [R2.6] RULE: Never mix liquidation and traditional levels in same trade plan

STEP 3: Smart Money & Entry Timing Gate + Volume Confirmation + Adaptive Thresholds
- [R3.1] Check Order Book imbalance with adaptive thresholds:
  * Low Volatility: >60% = strong signal, 50-60% = moderate, <50% = weak
  * Medium Volatility: >75% = strong signal, 65-75% = moderate, <65% = weak
  * High/Extreme Volatility: >85% = strong signal, 75-85% = moderate, <75% = weak
- [R3.2] Check Whale Movement signal with same adaptive thresholds:
  * Low Volatility: >60% alignment required
  * Medium Volatility: >75% alignment required
  * High/Extreme Volatility: >85% alignment required
- [R3.3] VOLUME GATE: Only execute if volume confirms price signal (no weak volume signals)
- [R3.4] EXECUTION GATE: Only execute if BOTH order book AND whale signals AND volume support trade direction
- [R3.5] RULE: Don't fight smart money flow OR weak volume, adapt thresholds to market conditions
- [BACKTESTING] Adjust confidence +5% if smart money signals matched last 3 similar setups

STEP 4: Technical Analysis WITH Historical Validation + Multi-timeframe Filter
- [R4.1] RSI, pivot point support/resistance (if not overridden by liquidations), trend direction
- [R4.2] BTC/ETH signals for directional bias
- [R4.3] HISTORICAL CHECK: Confirm signals align with multi-timeframe momentum
- [R4.4] WEEKLY/MONTHLY TREND: Only trade WITH long-term trend unless strong reversal signals
- [R4.5] OPTIONAL 4H FILTER: Check 4-hour SMA20 direction vs 1-hour trend for both BTC and ETH
  * If aligned: +5% confidence (capped at 85%) for respective coin
  * If misaligned: -5% confidence and flag "Trend Divergence Warning" for respective coin
- [R4.6] RULE: Technical signals must pass historical momentum filter, 4h filter is advisory only
- [BACKTESTING] Adjust confidence +5% if technical signals matched last 3 similar setups

STEP 5: MACRO TREND + SENTIMENT + NETWORK HEALTH + SOCIAL ANALYSIS
- [R5.1] Fear & Greed, BTC dominance, S&P 500/VIX for overall market bias
- [R5.2] Multi-source sentiment for crowd positioning
- [R5.3] Social metrics: Forum activity spikes (>20% = sentiment shift), GitHub stars, developer activity
- [R5.4] NETWORK HEALTH ANALYSIS:
  * BTC Hash Rate: High = strong security, bullish long-term
  * BTC Mining Difficulty: Increasing = network growth, positive signal
  * BTC Mempool: High congestion = network demand, potential price pressure
  * BTC Active Addresses: Increasing = adoption growth, bullish
  * ETH Gas Pressure: High = network demand, positive for ETH
  * ETH Total Supply: Monitor for supply changes affecting price
- [R5.5] RULE: Use for position sizing confidence, not trade direction. Network health confirms long-term trend strength.

STEP 5.5: CORRELATION & CROSS-ASSET ANALYSIS
- [R5.6] BTC-ETH Correlation Analysis:
  * High correlation (>0.7): Similar position sizing and timing for both
  * Low correlation (<0.3): Independent positioning allowed
  * Negative correlation: Consider inverse positioning for diversification
  * Correlation trend: Increasing = more synchronized markets, decreasing = divergence opportunity
- [R5.7] Cross-Asset Correlation Analysis:
  * Market Regime: RISK_ON vs RISK_OFF determines crypto-equity relationship
  * VIX Analysis: High VIX = risk-off, crypto may decouple from equities
  * SP500 Correlation: Strong equity moves may influence crypto direction
  * Commodity Correlations: Gold/Oil moves may signal macro shifts
- [R5.8] RULE: Use correlations for position sizing and risk management, not primary trade direction

STEP 6: Sentiment Risk Assessment
- [R6.1] Check funding rates and long/short ratios for overcrowded trades
- [R6.2] High funding = crowded positioning = reversal risk
- [R6.3] Social sentiment extremes = potential reversal signals
- [R6.4] RULE: Avoid trading in same direction as extreme crowd positioning

STEP 7: Enhanced Execution Planning + Conditional Breakout Setup + Correlation-Based Diversification
- [R7.1] Entry zones: Use liquidation clusters if present, else pivot point S/R
- [R7.2] Stop loss: Place beyond next liquidation cluster or pivot point S/R level
- [R7.3] Take profit: Target liquidation clusters as magnetic price targets
- [R7.4] MINIMUM 1:2 R/R, but adjust for liquidation cluster distances
- [R7.5] CORRELATION-BASED DIVERSIFICATION:
  * High BTC-ETH correlation (>0.7): Similar position sizing and timing for both coins
  * Low correlation (<0.3): Independent positioning allowed, diversify entry timing
  * Negative correlation: Consider inverse positioning for portfolio diversification
  * Cross-asset regime check: If RISK_OFF → Reduce crypto exposure, if RISK_ON → Normal sizing
- [R7.6] CONDITIONAL BREAKOUT: If breakout potential flagged in Step 0.5, create additional breakout plan:
  * Entry: On breakout confirmation (candle close > resistance or < support by 1% with volume spike)
  * SL: Beyond the opposite level (1% below support for long, 1% above resistance for short)
  * TP: Next liquidation cluster or 2% move
  * Confidence: Reduce by 10% due to uncertainty
- [R7.7] RULE: Liquidation-aware stop/target placement with correlation-based diversification

STEP 8: DYNAMIC RISK MANAGEMENT & POSITION SIZING
- [R8.1] **Position Size Rules:**
  * Normal conditions: 100% (full position)
  * Volatility Regime HIGH: 75% | EXTREME: 50%
  * Economic Calendar high risk: -25%
  * Fighting Whale signals: -25%
  * CFTC STRONG_REVERSAL_RISK: -50% (institutional override)
  * CFTC Smart Money ratio <0.5: -25% (fighting institutions)

- [R8.2] **Reversal Detection (3-candle check):**
  * BTC >1% opposite movement: Reduce to 50%
  * ETH >1% opposite movement: Reduce to 50%

- [R8.3] **ATR Volatility Trigger (1h ATR >2% increase):**
  * BTC ATR spike: -25% | ETH ATR spike: -25%
  * BOTH ATRs spike: -25% each (correlation risk)

- [R8.4] **Confidence Calculation:**
  * Base: Average of signal strengths (order book, volume, RSI, liquidation, whale, CFTC)
  * Adjustment: +5% if all high-priority aligned, -5% if >50% misaligned
  * CFTC Boost: +10% if aligned, -10% if misaligned
  * [BACKTESTING] Adjust confidence +5% if signal matched last 3 similar setups
  * Cap: Maximum 85% (market uncertainty)

- [R8.5] **Position Size Output:** Individual percentages (100%, 75%, 50%, 25%) per coin

⚠️ REMINDER: Follow the above ENHANCED DECISION FRAMEWORK (Steps 1-8). Do not skip any steps.

POSITION SIZE INSTRUCTION:
Position Size represents the recommended position size for each coin individually (not portfolio allocation).
- Standard: 100% | Reduced risk: 75% | High risk: 50% | Extreme risk: 25%
- Reversal detection: 50% if >1% opposite movement in last 3 candles
Present in each execution plan as percentage of intended trade size for that specific coin.

CRITICAL DECISION TREE:
======================
0. Data <50% (<32/65 points)? → If YES: Output "INSUFFICIENT_DATA - FLAT POSITION"
1. Sideways Market? → If YES: Output "SIDEWAYS - No Entry, Monitor for breakout"
2. Economic Events = FLAT? → If YES: Output "FLAT - Major events pending"
3. Extreme Volatility? → If YES: Reduce size by regime multiplier  
4. Near Liquidation Clusters? → If YES: Use clusters as primary targets, ignore pivot point S/R
5. Order Book + Whales Aligned? → If NO: Lower confidence or avoid
6. Pivot point signals confirm? → If YES: Execute with priority-based sizing
7. Risk management applied? → Always adjust for volatility regime and event risk

OUTPUT PRIORITY: Economic Events > Liquidation Targets > Entry Timing > Pivot Point TA

📋 RULE REFERENCE SUMMARY:
- [R0.1-R0.14] Conflict Resolution & Sideways Detection
- [R1.1-R1.5] Economic & CFTC Overrides  
- [R2.1-R2.6] Liquidation Analysis
- [R3.1-R3.5] Smart Money & Volume Gates
- [R4.1-R4.6] Technical & Historical Validation
- [R5.1-R5.8] Macro, Network Health & Correlations
- [R6.1-R6.4] Sentiment Risk Assessment
- [R7.1-R7.7] Execution Planning & Diversification
- [R8.1-R8.5] Risk Management & Position Sizing

PRIORITY-INTEGRATED TIMEFRAME LOGIC:
- SUPER HIGH: Economic Events pending → Extend timeframe by 2x (wait for clarity)
- HIGH: Liquidation Targets 2-6h, Bond Market 12-48h
  * VOLATILITY: >0.6 → 2-4h, >0.9 with volume >2x → 1-2h
- MEDIUM: Smart Money 4-12h
- LOW: Pivot Point TA 6-24h
- VOLATILITY: "EXTREME" → Cut all timeframes by 50%
- CONFLICT: Use SHORTEST from highest priority signal
FINAL RULE: Priority level determines base timeframe, volatility regime adjusts duration

REQUIRED OUTPUT FORMAT (CONCISE ONLY):
=====================================

<b>━━━ 📊 EXECUTIVE SUMMARY ━━━</b>
- Fear & Greed: [value] ([sentiment])
- Market Bias: [BULLISH/BEARISH/SIDEWAYS]
- Trend Prediction: [TRENDING/SIDEWAYS]
- Primary Driver: [key factor driving direction]
- Risk Level: [High/Medium/Low] 
- Position Crowding: [BTC/ETH crowding assessment]
- Trend Divergence: [BTC/ETH divergence warnings if any]

<b>━━━ 🎯 BTC EXECUTION PLAN - [BIAS] ━━━</b>
💰 Current: $[price]
⏱️ Timeframe: [X-Yh] ([breakout/swing/trend/reversal] setup)
📊 Position Size: [X]% (of intended trade size)
📍 <b>Entry: $[low]-$[high]</b>
🛑 <b>SL: $[price] ([X]%)</b>
🎯 <b>TP 1: $[price] ([X]%)</b> 
🎯 <b>TP 2: $[price] ([X]%)</b>
⚖️ Risk/Reward: [X:X]
📊 Confidence: [XX]% ([key reasoning])

<b>━━━ 🎯 ETH EXECUTION PLAN - [BIAS] ━━━</b>
💰 Current: $[price]
⏱️ Timeframe: [X-Yh] ([breakout/swing/trend/reversal] setup)
📊 Position Size: [X]% (of intended trade size)
📍 <b>Entry: $[low]-$[high]</b>
🛑 <b>SL: $[price] ([X]%)</b>
🎯 <b>TP 1: $[price] ([X]%)</b>
🎯 <b>TP 2: $[price] ([X]%)</b>
⚖️ Risk/Reward: [X:X]
📊 Confidence: [XX]% ([key reasoning])

<b>━━━ ⚠️ RISK NOTES ━━━</b>
- Correlation Risk: [BTC-ETH positioning notes]
- Volatility Regime: [regime] - position sizing adjusted
- Macro Risk: [traditional market alignment]
- CFTC Risk: [Institutional positioning risk]
- Data Quality: [Limited analysis warnings if applicable]
- Social Sentiment: [Forum/GitHub activity insights]
- Win Probability: [Confidence-based win rate estimate]

[IF SIDEWAYS DETECTED, REPLACE EXECUTION PLANS WITH:]
<b>━━━ ⏸️ MARKET STATUS: SIDEWAYS ━━━</b>
- No Entry - Monitor for breakout or signal alignment
- Key Levels: Support $[X], Resistance $[Y]
- Breakout Watch: Volume >1.5x average near levels
- Confidence: [XX]% (sideways uncertainty)
- Correlation: [BTC-ETH correlation during sideways]
- CFTC: [Institutional positioning during sideways]

[IF BREAKOUT POTENTIAL DETECTED, ADD ADDITIONAL PLAN:]
<b>━━━ 🎯 CONDITIONAL BREAKOUT SETUP ━━━</b>
💰 Current: $[price]
⏱️ Setup: Breakout Pending
📍 <b>Entry: On breakout >$[resistance] or <$[support] (1% with volume spike)</b>
🛑 <b>SL: $[opposite_level] (1% beyond opposite level)</b>
🎯 <b>TP: $[target] (2% move or next liquidation cluster)</b>
⚖️ Risk/Reward: [X:X]
📊 Confidence: [XX]% (breakout uncertainty)

<b>━━━ 🚀 BREAKOUT WATCH ━━━</b>
- Breakout Type: [Support/Resistance] breakout potential
- Trigger Level: $[X] with volume >1.5x average
- Entry: On breakout confirmation (1% move beyond level)
- SL: [X]% below/above breakout level
- TP: [X]% move in breakout direction
- Confidence: [XX]% (breakout uncertainty reduces confidence)

⚠️ FINAL REMINDER: Keep total output under 600 words. Be concise, actionable, and precise.
Focus on Executive Summary, Execution Plans, and Risk Notes.

STOP HERE. Keep under 600 words total. Be precise and actionable."""
        
        return prompt

    def _count_available_data(self, market_data):
        """Count available data points for the prompt - MATCHES data_collector._count_data_points exactly"""
        count = 0
        
        # 1. Crypto Prices (2 points)
        crypto = market_data.get("crypto", {})
        if crypto.get("btc"): count += 1
        if crypto.get("eth"): count += 1
        
        # 2. Technical Indicators (12 points: 6 per coin)
        tech = market_data.get("technical_indicators", {})
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
        futures = market_data.get("futures", {})
        for coin in ["BTC", "ETH"]:
            coin_data = futures.get(coin, {})
            if coin_data:
                if coin_data.get('funding_rate') is not None: count += 1
                if coin_data.get('long_ratio') is not None: count += 1
                if coin_data.get('short_ratio') is not None: count += 1
                if coin_data.get('open_interest') is not None: count += 1
        
        # 4. Market Sentiment (3 points)
        if market_data.get("fear_greed", {}).get("index"): count += 1
        if market_data.get("btc_dominance"): count += 1
        if market_data.get("market_cap"): count += 1
        
        # 5. Trading Volumes (2 points)
        volumes = market_data.get("volumes", {})
        if volumes.get("btc_volume"): count += 1
        if volumes.get("eth_volume"): count += 1
        
        # 6. Macroeconomic Data (4 points)
        if market_data.get("m2_supply", {}).get("m2_supply"): count += 1
        if market_data.get("inflation", {}).get("inflation_rate") is not None: count += 1
        rates = market_data.get("interest_rates", {})
        if rates.get("fed_rate") is not None: count += 1
        if rates.get("t10_yield") is not None: count += 1
        
        # 7. Stock Indices (4 points)
        indices = market_data.get("stock_indices", {})
        for key in ["sp500", "nasdaq", "dow_jones", "vix"]:
            if indices.get(key) is not None: count += 1
        
        # 8. Commodities (4 points)
        commodities = market_data.get("commodities", {})
        for key in ["gold", "silver", "crude_oil", "natural_gas"]:
            if commodities.get(key) is not None: count += 1
        
        # 9. Social Metrics (6 points)
        social = market_data.get("social_metrics", {})
        if social.get("forum_posts"): count += 1
        if social.get("forum_topics"): count += 1
        if social.get("btc_github_stars"): count += 1
        if social.get("eth_github_stars"): count += 1
        if social.get("btc_recent_commits"): count += 1
        if social.get("eth_recent_commits"): count += 1
        
        # 10. Historical Data (2 points)
        historical = market_data.get("historical_data", {})
        if historical.get("BTC"): count += 1
        if historical.get("ETH"): count += 1
        
        # 11. Volatility Regime (1 point: market-wide) - NEW
        if market_data.get("volatility_regime"): count += 1
        
        # 12. NEW ENHANCED DATA SOURCES (9 points total)
        # Order Book Analysis (2 points: BTC + ETH)
        order_book = market_data.get("order_book_analysis", {})
        if order_book.get("BTC"): count += 1
        if order_book.get("ETH"): count += 1
        
        # Liquidation Heatmap (2 points: BTC + ETH)
        liquidation = market_data.get("liquidation_heatmap", {})
        if liquidation.get("BTC"): count += 1
        if liquidation.get("ETH"): count += 1
        
        # Economic Calendar (1 point: market-wide)
        if market_data.get("economic_calendar"): count += 1
        
        # Multi-Source Sentiment (1 point: market-wide)
        if market_data.get("multi_source_sentiment"): count += 1
        
        # Whale Movements (2 points: BTC + ETH)
        whale_data = market_data.get("whale_movements", {})
        if whale_data and whale_data.get('breakdown'):
            breakdown = whale_data.get('breakdown', {})
            if breakdown.get('large_trades'): count += 1
            if breakdown.get('exchange_flows'): count += 1
        
        # 13. Network Health Data (6 points total)
        # BTC Network Health (4 points)
        btc_network = market_data.get("btc_network_health", {})
        if btc_network.get("hash_rate_th_s"): count += 1
        if btc_network.get("mining_difficulty"): count += 1
        if btc_network.get("mempool_unconfirmed"): count += 1
        if btc_network.get("active_addresses_trend"): count += 1
        
        # ETH Network Health (2 points)
        eth_network = market_data.get("eth_network_health", {})
        if eth_network.get("gas_prices"): count += 1
        if eth_network.get("total_supply"): count += 1
        
        # 14. Crypto Correlations (4 points total)
        # Crypto Correlations (2 points)
        crypto_correlations = market_data.get("crypto_correlations", {})
        if crypto_correlations.get("btc_eth_correlation_30d") is not None: count += 1
        if crypto_correlations.get("btc_eth_correlation_7d") is not None: count += 1
        
        # Cross-Asset Correlations (2 points)
        cross_asset_correlations = market_data.get("cross_asset_correlations", {})
        if cross_asset_correlations.get("market_regime"): count += 1
        if cross_asset_correlations.get("crypto_equity_regime"): count += 1
        
        # 15. CFTC Positioning Data (8 points total)
        cftc_positioning = market_data.get("cftc_positioning", {})
        if cftc_positioning.get("institutional_sentiment"): count += 1
        if cftc_positioning.get("commercial_signal"): count += 1
        if cftc_positioning.get("leveraged_positioning_pct") is not None: count += 1
        if cftc_positioning.get("contrarian_signal"): count += 1
        if cftc_positioning.get("smart_money_net") is not None: count += 1
        if cftc_positioning.get("overall_cftc_sentiment"): count += 1
        if cftc_positioning.get("positioning_extreme"): count += 1
        if cftc_positioning.get("open_interest"): count += 1
        
        return count

    # ============================================================================
    # NEW HELPER FUNCTIONS - ADD HERE
    # ============================================================================
    
    def _safe_get_numeric(self, data, key, default=0):
        """Safely extract numeric value from data, handling dict/None cases"""
        try:
            if data is None:
                print(f"[WARN] Data is None for key {key}, using default {default}")
                return default
            value = data.get(key, default)
            if isinstance(value, (int, float)):
                return value
            elif isinstance(value, dict):
                print(f"[WARN] Expected numeric value for {key}, got dict: {value}")
                return default
            elif value is None:
                return default
            else:
                return float(value)
        except (ValueError, TypeError, AttributeError) as e:
            print(f"[WARN] Could not convert {key} value '{value}' to numeric, using default {default}. Error: {e}")
            return default

    def _analyze_momentum_state(self, coin_historical):
        """Analyze momentum across timeframes"""
        if not coin_historical:
            return "UNKNOWN"
        
        try:
            # Check if daily RSI is trending up/down
            daily_rsi = coin_historical.get('1d', {}).get('rsi', [])
            
            # Handle both list and None cases
            if not daily_rsi or not isinstance(daily_rsi, list) or len(daily_rsi) < 5:
                return "INSUFFICIENT_RSI_DATA"
            
            # Safely get recent RSI values
            recent_rsi = daily_rsi[-5:]
            
            # Ensure all values are numbers
            try:
                last_rsi = float(recent_rsi[-1]) if recent_rsi[-1] is not None else 50
                first_rsi = float(recent_rsi[0]) if recent_rsi[0] is not None else 50
            except (ValueError, TypeError):
                return "INVALID_RSI_DATA"
            
            if last_rsi > first_rsi:
                return "BUILDING" if last_rsi < 70 else "OVEREXTENDED"
            else:
                return "WEAKENING" if last_rsi > 30 else "OVERSOLD"
                
        except (IndexError, TypeError, KeyError, AttributeError):
            return "UNKNOWN"

    def _determine_longterm_trend(self, historical):
        """Determine long-term trend from weekly/monthly data"""
        try:
            btc_weekly = historical.get('BTC', {}).get('1wk', {})
            eth_weekly = historical.get('ETH', {}).get('1wk', {})
            
            if not btc_weekly or not eth_weekly:
                return "MISSING_WEEKLY_DATA"
            
            # Safely extract weekly data
            btc_close = btc_weekly.get('close', [])
            btc_sma200 = btc_weekly.get('sma200', [])
            eth_close = eth_weekly.get('close', [])
            eth_sma200 = eth_weekly.get('sma200', [])
            
            # Check if we have valid list data with sufficient length
            if not isinstance(btc_close, list) or len(btc_close) < 200:
                return "INSUFFICIENT_BTC_WEEKLY_DATA"
            if not isinstance(btc_sma200, list) or len(btc_sma200) < 200:
                return "INSUFFICIENT_BTC_SMA200_DATA"
            if not isinstance(eth_close, list) or len(eth_close) < 200:
                return "INSUFFICIENT_ETH_WEEKLY_DATA"
            if not isinstance(eth_sma200, list) or len(eth_sma200) < 200:
                return "INSUFFICIENT_ETH_SMA200_DATA"
            
            # Safely convert to float and validate
            try:
                btc_current = float(btc_close[-1]) if btc_close[-1] is not None else 0
                btc_sma = float(btc_sma200[-1]) if btc_sma200[-1] is not None else 0
                eth_current = float(eth_close[-1]) if eth_close[-1] is not None else 0
                eth_sma = float(eth_sma200[-1]) if eth_sma200[-1] is not None else 0
            except (ValueError, TypeError):
                return "INVALID_PRICE_DATA_TYPE"
            
            if btc_current <= 0:
                return "INVALID_BTC_PRICE_VALUE"
            if btc_sma <= 0:
                return "INVALID_BTC_SMA200_VALUE"
            if eth_current <= 0:
                return "INVALID_ETH_PRICE_VALUE"
            if eth_sma <= 0:
                return "INVALID_ETH_SMA200_VALUE"
            
            btc_trend = "BULL" if btc_current > btc_sma else "BEAR"
            eth_trend = "BULL" if eth_current > eth_sma else "BEAR"
            
            if btc_trend == eth_trend:
                return f"ALIGNED_{btc_trend}ISH"
            else:
                return "DIVERGENT"
                
        except (IndexError, TypeError, KeyError, AttributeError) as e:
            return f"DATA_PROCESSING_ERROR: {str(e)[:50]}"

    def _find_historical_resistance_levels(self, historical):
        """Find confluence of historical resistance levels"""
        try:
            btc_daily = historical.get('BTC', {}).get('1d', {})
            if not btc_daily:
                return "MISSING_BTC_DAILY_DATA"
            if 'high' not in btc_daily or 'close' not in btc_daily:
                return "MISSING_HIGH_CLOSE_DATA"
            
            # Get data safely
            highs = btc_daily.get('high', [])
            closes = btc_daily.get('close', [])
            
            # Validate data types and length
            if not isinstance(highs, list):
                return "INVALID_HIGH_DATA_TYPE"
            if not isinstance(closes, list):
                return "INVALID_CLOSE_DATA_TYPE"
            
            if len(highs) < 50:
                return f"INSUFFICIENT_HIGH_DATA: {len(highs)} days (need 50+)"
            if len(closes) < 1:
                return "INSUFFICIENT_CLOSE_DATA"
            
            # Get recent highs (last 50 days)
            recent_highs = highs[-50:]
            
            try:
                current_price = float(closes[-1]) if closes[-1] is not None else 0
            except (ValueError, TypeError):
                return "INVALID_CURRENT_PRICE_VALUE"
            
            if current_price <= 0:
                return f"INVALID_CURRENT_PRICE: {current_price}"
            
            # Find resistance levels above current price
            resistance_levels = []
            for i in range(1, len(recent_highs)-1):
                try:
                    curr_high = float(recent_highs[i]) if recent_highs[i] is not None else 0
                    prev_high = float(recent_highs[i-1]) if recent_highs[i-1] is not None else 0
                    next_high = float(recent_highs[i+1]) if recent_highs[i+1] is not None else 0
                    
                    if curr_high > prev_high and curr_high > next_high and curr_high > current_price:
                        resistance_levels.append(curr_high)
                except (ValueError, TypeError):
                    continue
            
            if len(resistance_levels) >= 3:
                return "STRONG_CONFLUENCE"
            elif len(resistance_levels) >= 1:
                return "MODERATE_RESISTANCE"
            else:
                return "CLEAR_SKIES"
                
        except (IndexError, TypeError, KeyError, AttributeError) as e:
            return f"RESISTANCE_ANALYSIS_ERROR: {str(e)[:50]}"

    def _check_momentum_alignment(self, historical):
        """Check if momentum aligns across timeframes with percentage quantification"""
        try:
            btc_daily = historical.get('BTC', {}).get('1d', {})
            btc_weekly = historical.get('BTC', {}).get('1wk', {})
            
            if not btc_daily:
                return "MISSING_BTC_DAILY_DATA"
            if not btc_weekly:
                return "MISSING_BTC_WEEKLY_DATA"
            
            # Check MACD alignment
            daily_macd = btc_daily.get('macd_histogram', [])
            weekly_macd = btc_weekly.get('macd_histogram', [])
            
            # Validate MACD data
            if not isinstance(daily_macd, list):
                return "INVALID_DAILY_MACD_TYPE"
            if not isinstance(weekly_macd, list):
                return "INVALID_WEEKLY_MACD_TYPE"
            
            if len(daily_macd) == 0:
                return "NO_DAILY_MACD_DATA"
            if len(weekly_macd) == 0:
                return "NO_WEEKLY_MACD_DATA"
            
            try:
                # Safely get last MACD values
                daily_value = float(daily_macd[-1]) if daily_macd[-1] is not None else 0
                weekly_value = float(weekly_macd[-1]) if weekly_macd[-1] is not None else 0
            except (ValueError, TypeError):
                return "INVALID_MACD_VALUES"
            
            daily_signal = "BULL" if daily_value > 0 else "BEAR"
            weekly_signal = "BULL" if weekly_value > 0 else "BEAR"
            
            if daily_signal == weekly_signal:
                return f"ALIGNED_{daily_signal}ISH"
            else:
                # Calculate divergence percentage
                if daily_value != 0 and weekly_value != 0:
                    # Calculate relative divergence as percentage of the larger value
                    max_value = max(abs(daily_value), abs(weekly_value))
                    divergence_pct = abs(daily_value - weekly_value) / max_value * 100
                    
                    if divergence_pct < 25:
                        return f"SLIGHT_DIVERGENCE_{divergence_pct:.1f}%"
                    elif divergence_pct < 50:
                        return f"MODERATE_DIVERGENCE_{divergence_pct:.1f}%"
                    elif divergence_pct < 75:
                        return f"STRONG_DIVERGENCE_{divergence_pct:.1f}%"
                    else:
                        return f"EXTREME_DIVERGENCE_{divergence_pct:.1f}%"
                else:
                    # Handle zero values
                    if daily_value == 0 and weekly_value == 0:
                        return "BOTH_MACD_ZERO"
                    elif daily_value == 0:
                        return "DAILY_MACD_ZERO"
                    else:
                        return "WEEKLY_MACD_ZERO"
                
        except (IndexError, TypeError, KeyError, AttributeError) as e:
            return f"MOMENTUM_ANALYSIS_ERROR: {str(e)[:50]}"

    def _assess_treasury_impact(self, t10_yield):
        """Assess treasury yield impact on crypto"""
        if not t10_yield:
            return "UNKNOWN"
        
        try:
            yield_val = float(t10_yield)
            if yield_val > 5.0:
                return "VERY_BEARISH_FOR_CRYPTO"
            elif yield_val > 4.5:
                return "BEARISH_FOR_CRYPTO"
            elif yield_val < 3.0:
                return "BULLISH_FOR_CRYPTO"
            else:
                return "NEUTRAL_FOR_CRYPTO"
        except (ValueError, TypeError):
            return "UNKNOWN"

    def _assess_energy_signal(self, commodities):
        """Assess energy market signal for risk appetite"""
        if not commodities:
            return "UNKNOWN"
        
        try:
            oil = commodities.get('crude_oil')
            gas = commodities.get('natural_gas')
            
            if not oil and not gas:
                return "UNKNOWN"
            
            signals = []
            if oil:
                oil_val = float(oil)
                if oil_val > 90:
                    signals.append("OIL_BEARISH_RISK")
                elif oil_val < 60:
                    signals.append("OIL_BULLISH_RISK")
            
            if gas:
                gas_val = float(gas)
                if gas_val > 6.0:
                    signals.append("GAS_BEARISH_RISK")
                elif gas_val < 2.0:
                    signals.append("GAS_BULLISH_RISK")
            
            if not signals:
                return "ENERGY_NEUTRAL"
            elif any("BEARISH" in s for s in signals):
                return "ENERGY_BEARISH_FOR_RISK"
            else:
                return "ENERGY_BULLISH_FOR_RISK"
        except (ValueError, TypeError):
            return "UNKNOWN"



    def _analyze_volume_signal(self, coin, volumes, technical_data):
        """Analyze volume for signal confirmation"""
        if not volumes or not technical_data:
            return "NO_DATA"
        
        try:
            volume_key = f"{coin.lower()}_volume"
            current_volume = volumes.get(volume_key, 0)
            volume_trend = technical_data.get('volume_trend', 'stable')
            price_signal = technical_data.get('signal', 'NEUTRAL')
            
            if not current_volume:
                return "NO_DATA"
            
            # Volume confirmation logic
            if price_signal in ['BUY', 'STRONG BUY'] and volume_trend == 'increasing':
                return "STRONG_BULLISH_CONFIRMATION"
            elif price_signal in ['SELL', 'STRONG SELL'] and volume_trend == 'increasing':
                return "STRONG_BEARISH_CONFIRMATION"
            elif price_signal in ['BUY', 'STRONG BUY'] and volume_trend == 'decreasing':
                return "WEAK_BULLISH_SIGNAL"
            elif price_signal in ['SELL', 'STRONG SELL'] and volume_trend == 'decreasing':
                return "WEAK_BEARISH_SIGNAL"
            else:
                return "VOLUME_NEUTRAL"
        except (ValueError, TypeError, KeyError):
            return "UNKNOWN"

    def _calculate_systematic_risk_adjustment(self, market_data):
        """Calculate systematic risk adjustment multiplier"""
        try:
            risk_factors = []
        
            # Volatility regime factor (MANDATORY)
            volatility_regime = market_data.get("volatility_regime", {})
            base_multiplier = volatility_regime.get('size_multiplier', 1.0)
            risk_factors.append(("volatility", base_multiplier))
        
            # Economic calendar factor
            economic_cal = market_data.get("economic_calendar", {})
            if economic_cal and economic_cal.get('recommendation') in ['AVOID_TRADING_HIGH_VOLATILITY', 'REDUCE_POSITION_SIZE']:
                risk_factors.append(("economic", 0.5))
            elif economic_cal and economic_cal.get('high_impact', 0) > 2:
                risk_factors.append(("economic", 0.7))
            else:
                risk_factors.append(("economic", 1.0))
        
            # Treasury yield factor
            rates_data = market_data.get("interest_rates", {})
            t10_yield = rates_data.get('t10_yield')
            if t10_yield is not None and t10_yield > 5.0:
                risk_factors.append(("treasury", 0.6))
            elif t10_yield is not None and t10_yield > 4.5:
                risk_factors.append(("treasury", 0.8))
            else:
                risk_factors.append(("treasury", 1.0))
        
            # Whale movement conflict factor
            whale_data = market_data.get("whale_movements", {})
            if whale_data and whale_data.get('whale_signal') == 'WHALES_DISTRIBUTING':
                risk_factors.append(("whale_conflict", 0.7))
            else:
                risk_factors.append(("whale_conflict", 1.0))
        
            # Calculate final multiplier
            final_multiplier = 1.0
            for factor_name, multiplier in risk_factors:
                final_multiplier *= multiplier
        
            # Cap between 0.1x and 1.5x
            final_multiplier = max(0.1, min(1.5, final_multiplier))
        
            return {
                'final_multiplier': final_multiplier,
                'risk_breakdown': dict(risk_factors),
                'risk_explanation': f"Vol:{base_multiplier:.1f}x × Factors = {final_multiplier:.1f}x final"
            }
        
        except Exception as e:
            print(f"[ERROR] Risk calculation failed: {e}")
            return {
                'final_multiplier': 0.5,  # Conservative default
                'risk_breakdown': {},
                'risk_explanation': "Risk calc failed - using 0.5x conservative sizing"
            }
    def _safe_get_historical_value(self, historical, coin, timeframe, indicator):
        """Safely get historical indicator value"""
        try:
            data = historical.get(coin, {}).get(timeframe, {}).get(indicator, [])
            if isinstance(data, list) and len(data) > 0:
                value = data[-1]  # Get last value
                if value is not None:
                    return float(value)
            return 0
        except (ValueError, TypeError, IndexError):
            return 0

    def _get_sma_position(self, historical, coin):
        """Get position relative to SMA200"""
        try:
            weekly_data = historical.get(coin, {}).get('1wk', {})
            close_data = weekly_data.get('close', [])
            sma200_data = weekly_data.get('sma200', [])
            
            if (isinstance(close_data, list) and len(close_data) > 0 and
                isinstance(sma200_data, list) and len(sma200_data) > 0):
                
                current_price = float(close_data[-1]) if close_data[-1] is not None else 0
                sma200_value = float(sma200_data[-1]) if sma200_data[-1] is not None else 0
                
                if current_price > 0 and sma200_value > 0:
                    return "ABOVE" if current_price > sma200_value else "BELOW"
            
            return "N/A"
        except (ValueError, TypeError, IndexError):
            return "N/A"

    def _get_macd_signal(self, historical, coin, timeframe):
        """Get MACD signal"""
        try:
            data = historical.get(coin, {}).get(timeframe, {}).get('macd_histogram', [])
            if isinstance(data, list) and len(data) > 0:
                value = data[-1]
                if value is not None:
                    return "BULLISH" if float(value) > 0 else "BEARISH"
            return "N/A"
        except (ValueError, TypeError, IndexError):
            return "N/A"    
    
    # ============================================================================
    # END NEW HELPER FUNCTIONS
    # ============================================================================    

    def get_ai_prediction(self, market_data, reasoning_mode=False):
        """Get AI prediction using comprehensive market data"""
        try:
            print("[INFO] Generating AI prediction with comprehensive market analysis...")
            
            # Check if we have critical enhanced data for reliable predictions
            critical_sources = ['order_book_analysis', 'liquidation_heatmap', 'economic_calendar']
            missing_critical = [source for source in critical_sources if not market_data.get(source)]
            
            if missing_critical:
                warning_message = f"""🚨 CRITICAL DATA UNAVAILABLE - NO PREDICTION POSSIBLE

Missing critical market structure data:
• {', '.join(missing_critical)}

Impact: Predictions would be unreliable without this data
Action Required: Configure missing API keys or check API status

System Status: PREDICTION BLOCKED for data quality"""
                
                print(f"[WARN] {warning_message}")
                
                # Send warning to Telegram
                try:
                    from telegram_utils import send_telegram_message
                    send_telegram_message(warning_message)
                    print("[INFO] ✅ Warning sent to Telegram")
                except Exception as e:
                    print(f"[ERROR] Failed to send Telegram warning: {e}")
                
                return {
                    'prediction': None,
                    'status': 'BLOCKED',
                    'reason': f"Missing critical data: {', '.join(missing_critical)}",
                    'warning_sent': True
                }
            
            # Create comprehensive prompt
            prompt = self.create_comprehensive_prompt(market_data)
            
            # Modify system prompt for reasoning mode
            if reasoning_mode:
                system_prompt = """You are a professional cryptocurrency trader with 15+ years of experience. 

IMPORTANT: You are in REASONING MODE. DO NOT provide final trading recommendations or price targets.

Instead, show ONLY your step-by-step analysis process:

1. Market Trend Analysis: [Explain what you see in the trend data]
2. Technical Indicators Review: [Explain what the indicators tell you]  
3. Volume and Smart Money Analysis: [Explain volume patterns and smart money flow]
4. Sentiment Assessment: [Explain market sentiment and crowd behavior]
5. Risk Evaluation: [Explain what risks you identify]
6. Final Decision and Confidence: [Explain your conclusion and confidence level]

DO NOT include price targets, entry points, stop losses, or trading recommendations. Only show your analysis process."""
            else:
                system_prompt = "You are a professional cryptocurrency trader and market analyst with 15+ years of experience. Provide detailed, actionable trading analysis."
            
            # Prepare messages for API call
            messages = [
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
            
            # Try primary provider first, then fallback
            ai_prediction = None
            model_used = None
            provider_used = None
            
            print(f"[DEBUG] 🔍 AI Provider Debugging:")
            print(f"[DEBUG] Primary provider: {self.primary_provider}")
            print(f"[DEBUG] Fallback provider: {self.fallback_provider}")
            print(f"[DEBUG] xAI client available: {self.xai_client is not None}")
            print(f"[DEBUG] OpenAI client available: {self.openai_client is not None}")
            print(f"[DEBUG] xAI key configured: {'Yes' if self.xai_key and self.xai_key != 'YOUR_XAI_API_KEY' else 'No'}")
            print(f"[DEBUG] OpenAI key configured: {'Yes' if self.openai_key and self.openai_key != 'YOUR_OPENAI_API_KEY' else 'No'}")
            
            # Try primary provider
            print(f"[DEBUG] 🔍 Checking primary provider: {self.primary_provider}")
            print(f"[DEBUG] 🔍 Primary provider == 'xai': {self.primary_provider == 'xai'}")
            print(f"[DEBUG] 🔍 xAI client exists: {self.xai_client is not None}")
            print(f"[DEBUG] 🔍 Will try xAI: {self.primary_provider == 'xai' and self.xai_client is not None}")
            
            if self.primary_provider == "xai" and self.xai_client:
                try:
                    print(f"[INFO] 🚀 Using xAI Grok (primary provider)")
                    print(f"[DEBUG] xAI API Key configured: {'Yes' if self.xai_key and self.xai_key != 'YOUR_XAI_API_KEY' else 'No'}")
                    print(f"[DEBUG] xAI Client status: {self.xai_client}")
                    
                    # Direct HTTP request to xAI API
                    url = "https://api.x.ai/v1/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.xai_key}"
                    }
                    
                    payload = {
                        "model": "grok-4",
                        "messages": messages,
                        "max_tokens": 8000 if reasoning_mode else 4000,  # Increased for xAI's larger context
                        "temperature": 0.7
                    }
                    
                    print(f"[INFO] Sending request to xAI API (timeout: 120s)...")
                    print(f"[DEBUG] Request URL: {url}")
                    print(f"[DEBUG] Request headers: {dict(headers)}")
                    print(f"[DEBUG] Request payload keys: {list(payload.keys())}")
                    print(f"[DEBUG] Messages count: {len(messages)}")
                    print(f"[DEBUG] Prompt length: {len(prompt)} characters")
                    
                    response = requests.post(url, headers=headers, json=payload, timeout=120)
                    print(f"[DEBUG] Response status: {response.status_code}")
                    print(f"[DEBUG] Response headers: {dict(response.headers)}")
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    print(f"[DEBUG] Response result keys: {list(result.keys())}")
                    if 'choices' in result:
                        print(f"[DEBUG] Choices count: {len(result['choices'])}")
                        if result['choices']:
                            print(f"[DEBUG] First choice keys: {list(result['choices'][0].keys())}")
                    
                    ai_prediction = result["choices"][0]["message"]["content"]
                    finish_reason = result["choices"][0].get("finish_reason", "unknown")
                    model_used = "grok-4"
                    provider_used = "xai"
                    print(f"[INFO] ✅ xAI Grok prediction generated successfully (finish_reason: {finish_reason})")
                    
                    # Check if response was cut off
                    if finish_reason == "length":
                        print("[WARN] ⚠️ Response was cut off due to token limit")
                    elif finish_reason == "stop":
                        print("[INFO] ✅ Response completed normally")
                except Exception as e:
                    print(f"[WARN] xAI Grok failed: {e}")
                    print(f"[DEBUG] Exception type: {type(e).__name__}")
                    print(f"[DEBUG] Exception details: {str(e)}")
                    if hasattr(e, 'response'):
                        print(f"[DEBUG] Response status: {e.response.status_code if e.response else 'N/A'}")
                        print(f"[DEBUG] Response text: {e.response.text[:500] if e.response else 'N/A'}")
                    ai_prediction = None
            
            # Try OpenAI if it's the primary provider
            if self.primary_provider == "openai" and self.openai_client:
                try:
                    print(f"[INFO] 🚀 Using OpenAI (primary provider)")
                    print(f"[DEBUG] OpenAI API Key configured: {'Yes' if self.openai_key and self.openai_key != 'YOUR_OPENAI_API_KEY' else 'No'}")
                    print(f"[DEBUG] OpenAI Client initialized: {'Yes' if self.openai_client else 'No'}")
                    print(f"[DEBUG] OpenAI Client type: {type(self.openai_client)}")
                    print(f"[DEBUG] OpenAI Key length: {len(self.openai_key) if self.openai_key else 0}")
                    print(f"[DEBUG] Messages count: {len(messages)}")
                    print(f"[DEBUG] Prompt length: {len(prompt)} characters")
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4",  # Use standard GPT-4 instead of gpt-4o
                        messages=messages,
                        max_tokens=3000 if reasoning_mode else 1500,
                        temperature=0.7
                    )
                    
                    print(f"[DEBUG] OpenAI response received")
                    print(f"[DEBUG] Response choices count: {len(response.choices)}")
                    if response.choices:
                        print(f"[DEBUG] First choice message keys: {list(response.choices[0].message.__dict__.keys())}")
                    
                    ai_prediction = response.choices[0].message.content
                    model_used = "gpt-4"
                    provider_used = "openai"
                    print("[INFO] ✅ OpenAI prediction generated successfully")
                except Exception as e:
                    print(f"[WARN] OpenAI primary failed: {e}")
                    print(f"[DEBUG] Exception type: {type(e).__name__}")
                    print(f"[DEBUG] Exception details: {str(e)}")
                    ai_prediction = None
            
            # Try fallback provider if primary failed
            print(f"[DEBUG] 🔍 Checking fallback provider: {self.fallback_provider}")
            print(f"[DEBUG] 🔍 Fallback provider == 'openai': {self.fallback_provider == 'openai'}")
            print(f"[DEBUG] 🔍 OpenAI client exists: {self.openai_client is not None}")
            print(f"[DEBUG] 🔍 Will try OpenAI: {self.fallback_provider == 'openai' and self.openai_client is not None}")
            
            if ai_prediction is None and self.fallback_provider == "openai" and self.openai_client:
                try:
                    print(f"[INFO] 🔄 Using OpenAI (fallback provider)")
                    print(f"[DEBUG] OpenAI API Key configured: {'Yes' if self.openai_key and self.openai_key != 'YOUR_OPENAI_API_KEY' else 'No'}")
                    print(f"[DEBUG] OpenAI Client initialized: {'Yes' if self.openai_client else 'No'}")
                    print(f"[DEBUG] OpenAI Client type: {type(self.openai_client)}")
                    print(f"[DEBUG] OpenAI Key length: {len(self.openai_key) if self.openai_key else 0}")
                    print(f"[DEBUG] Messages count: {len(messages)}")
                    print(f"[DEBUG] Prompt length: {len(prompt)} characters")
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4",  # Use standard GPT-4 instead of gpt-4o
                        messages=messages,
                        max_tokens=3000 if reasoning_mode else 1500,
                        temperature=0.7
                    )
                    
                    print(f"[DEBUG] OpenAI response received")
                    print(f"[DEBUG] Response choices count: {len(response.choices)}")
                    if response.choices:
                        print(f"[DEBUG] First choice message keys: {list(response.choices[0].message.__dict__.keys())}")
                    
                    ai_prediction = response.choices[0].message.content
                    model_used = "gpt-4"
                    provider_used = "openai"
                    print("[INFO] ✅ OpenAI prediction generated successfully")
                except Exception as e:
                    print(f"[WARN] OpenAI fallback failed: {e}")
                    print(f"[DEBUG] OpenAI client type: {type(self.openai_client)}")
                    print(f"[DEBUG] OpenAI key length: {len(self.openai_key) if self.openai_key else 0}")
                    ai_prediction = None
            
            # Try xAI as fallback if OpenAI was primary
            if ai_prediction is None and self.fallback_provider == "xai" and self.xai_client:
                try:
                    print(f"[INFO] 🔄 Using xAI Grok (fallback provider)")
                    print(f"[DEBUG] xAI API Key configured: {'Yes' if self.xai_key and self.xai_key != 'YOUR_XAI_API_KEY' else 'No'}")
                    print(f"[DEBUG] xAI Client status: {self.xai_client}")
                    
                    # Direct HTTP request to xAI API
                    url = "https://api.x.ai/v1/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.xai_key}"
                    }
                    
                    payload = {
                        "model": "grok-4",
                        "messages": messages,
                        "max_tokens": 8000 if reasoning_mode else 4000,
                        "temperature": 0.7
                    }
                    
                    print(f"[INFO] Sending request to xAI API (timeout: 120s)...")
                    response = requests.post(url, headers=headers, json=payload, timeout=120)
                    response.raise_for_status()
                    result = response.json()
                    
                    ai_prediction = result["choices"][0]["message"]["content"]
                    model_used = "grok-4"
                    provider_used = "xai"
                    print(f"[INFO] ✅ xAI Grok prediction generated successfully")
                except Exception as e:
                    print(f"[WARN] xAI fallback failed: {e}")
                    ai_prediction = None
            
            # If both providers failed
            if ai_prediction is None:
                print(f"[DEBUG] 🚨 AI Prediction Failed Analysis:")
                print(f"[DEBUG] Primary provider: {self.primary_provider}")
                print(f"[DEBUG] Fallback provider: {self.fallback_provider}")
                print(f"[DEBUG] xAI client: {self.xai_client}")
                print(f"[DEBUG] OpenAI client: {self.openai_client}")
                print(f"[DEBUG] xAI key: {'Configured' if self.xai_key and self.xai_key != 'YOUR_XAI_API_KEY' else 'Missing/Placeholder'}")
                print(f"[DEBUG] OpenAI key: {'Configured' if self.openai_key and self.openai_key != 'YOUR_OPENAI_API_KEY' else 'Missing/Placeholder'}")
                print(f"[DEBUG] Will try xAI: {self.primary_provider == 'xai' and self.xai_client is not None}")
                print(f"[DEBUG] Will try OpenAI: {self.fallback_provider == 'openai' and self.openai_client is not None}")
                raise Exception("All AI providers failed")
            
            return {
                "prediction": ai_prediction,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": model_used,
                "provider": provider_used,
                "prompt_length": len(prompt),
                "response_length": len(ai_prediction),
                "data_points_used": self._count_available_data(market_data),
                "reasoning_mode": reasoning_mode
            }
            
        except Exception as e:
            print(f"[ERROR] AI prediction failed: {e}")
            return {
                "prediction": f"AI prediction unavailable - Error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": f"{self.primary_provider}-unknown",
                "provider": self.primary_provider,
                "error": str(e),
                "data_points_used": 0,
                "reasoning_mode": reasoning_mode
            }

    def format_ai_telegram_message(self, ai_result, market_data, test_mode=False):
        """Format AI prediction for Telegram"""
        try:
            prediction = ai_result.get("prediction", "No prediction available")
            data_points = ai_result.get("data_points_used", 0)
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            # Smart line cleaning - preserve UTC alignment but remove excess indentation
            lines = prediction.split('\n')
            cleaned_lines = []
            
            for i, line in enumerate(lines):
                # Don't strip lines that are just "UTC" - they need to stay with timestamp
                if line.strip() == "UTC":
                    # Find the previous line and combine them
                    if cleaned_lines and "Generated:" in cleaned_lines[-1]:
                        cleaned_lines[-1] = cleaned_lines[-1] + " UTC"
                        continue  # Skip adding this line separately
                
                # For other lines, remove excessive leading whitespace (more than 8 spaces)
                if line.startswith('        '):  # 8+ spaces
                    cleaned_line = line[8:].rstrip()
                else:
                    cleaned_line = line.strip()
                
                # Only add non-empty lines
                if cleaned_line:
                    cleaned_lines.append(cleaned_line)
            
            # Add empty lines between major sections for better visual separation
            formatted_lines = []
            for i, line in enumerate(cleaned_lines):
                formatted_lines.append(line)
                
                # Add empty line after section headers (bold headers with ━━━)
                if line.startswith('<b>━━━') and line.endswith('━━━</b>'):
                    formatted_lines.append('')
                
                # Add empty line before next section header (except first one)
                if i < len(cleaned_lines) - 1:
                    next_line = cleaned_lines[i+1]
                    if next_line.startswith('<b>━━━') and next_line.endswith('━━━</b>'):
                        formatted_lines.append('')

            # Join lines and remove any empty lines at the end
            cleaned_prediction = '\n'.join(formatted_lines).rstrip('\n')
            
            # Build the message with perfect footer alignment
            if test_mode:
                message = f"""{cleaned_prediction}
━━━━━━━━━━━━━━━━━━━━
📈 Data Points: {data_points}/54
⏰ {timestamp}
🤖 No unauthorized Sharing!"""
            else:
                message = f"""{cleaned_prediction}
━━━━━━━━━━━━━━━━━━━━
📈 Data Points: {data_points}/54
⏰ {timestamp}
🤖 No unauthorized Sharing!"""

            return message
            
        except Exception as e:
            print(f"[ERROR] Formatting AI Telegram message: {e}")
            return f"🤖 AI PREDICTION ERROR\n\nFailed to format prediction: {str(e)}\n\n⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

    def format_thought_process_message(self, ai_result, market_data):
        """Format AI thought process for Telegram"""
        try:
            prediction = ai_result.get("prediction", "No prediction available")
            data_points = ai_result.get("data_points_used", 0)
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            # Clean up the prediction text
            lines = prediction.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                if line:
                    cleaned_lines.append(line)
            
            thought_text = '\n'.join(cleaned_lines)
            
            # Truncate if too long (Telegram limit is ~4096 chars)
            if len(thought_text) > 3500:
                thought_text = thought_text[:3500] + "\n\n[Message truncated due to length]"
            
            message = f"""🧠 <b>AI THOUGHT PROCESS</b>

{thought_text}

━━━━━━━━━━━━━━━━━━━━
📈 Data Points: {data_points}/54
⏰ {timestamp}
🧪 REASONING MODE - TEST ENVIRONMENT"""

            return message
            
        except Exception as e:
            print(f"[ERROR] Formatting thought process message: {e}")
            return f"🧠 AI THOUGHT PROCESS ERROR\n\nFailed to format thought process: {str(e)}\n\n⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

    def send_ai_telegram(self, ai_result, market_data, test_mode=False, reasoning_mode=False):
        """Send AI prediction via Telegram"""
        try:
            # Determine which bot config to use (reasoning mode always uses test environment)
            if test_mode or reasoning_mode:
                bot_token = self.config["telegram"]["test"]["bot_token"]
                chat_id = self.config["telegram"]["test"]["chat_id"]
                print(f"[INFO] Using TEST Telegram configuration")
            else:
                bot_token = self.config["telegram"]["bot_token"] 
                chat_id = self.config["telegram"]["chat_id"]
                print(f"[INFO] Using PRODUCTION Telegram configuration")
            
            if not bot_token or not chat_id:
                mode_name = "test" if (test_mode or reasoning_mode) else "production"
                print(f"[ERROR] Telegram configuration missing for {mode_name} mode")
                print(f"[ERROR] Bot token: {'SET' if bot_token else 'NOT SET'}")
                print(f"[ERROR] Chat ID: {'SET' if chat_id else 'NOT SET'}")
                return False
            
            # Send message directly using the specific bot configuration  
            from telegram_utils import TelegramBot
            bot = TelegramBot(bot_token=bot_token, chat_id=chat_id)
            
            if reasoning_mode:
                # Send thought process message only
                thought_message = self.format_thought_process_message(ai_result, market_data)
                result = bot.send_message(thought_message)
            else:
                # Send regular message only
                message = self.format_ai_telegram_message(ai_result, market_data, test_mode)
                result = bot.send_message(message)
            
            if result:
                mode_text = "reasoning" if reasoning_mode else ("test" if test_mode else "production")
                print(f"[INFO] ✅ AI prediction sent via Telegram ({mode_text})")
                return True
            else:
                print(f"[ERROR] Failed to send AI prediction via Telegram")
                return False
                
        except Exception as e:
            print(f"[ERROR] Sending AI Telegram message: {e}")
            return False

    def save_ai_prediction(self, ai_result, market_data, test_mode=False):
        """Save AI prediction to database and files (optimized for render.com)"""
        try:
            timestamp = datetime.now(timezone.utc)
            
            # Prepare prediction data with proper database schema
            prediction_data = {
                "timestamp": timestamp.isoformat(),
                "date": timestamp.strftime('%Y-%m-%d'),  # Required by database
                "session": timestamp.strftime('%H:%M'),  # Required by database
                "type": "ai_prediction",
                "test_mode": test_mode,
                "prediction": ai_result.get("prediction", ""),
                "model": ai_result.get("model", "gpt-4o"),
                "data_points_used": ai_result.get("data_points_used", 0),
                "prompt_length": ai_result.get("prompt_length", 0),
                "response_length": ai_result.get("response_length", 0),
                # Market data for database (matching schema expectations)
                "market_data": {
                    "btc_price": market_data.get("crypto", {}).get("btc", 0),
                    "eth_price": market_data.get("crypto", {}).get("eth", 0),
                    "btc_rsi": market_data.get("technical_indicators", {}).get("BTC", {}).get("rsi14"),
                    "eth_rsi": market_data.get("technical_indicators", {}).get("ETH", {}).get("rsi14"),
                    "fear_greed": market_data.get("fear_greed", {}).get("index", 0)
                },
                # AI-specific prediction data
                "ai_prediction": ai_result.get("prediction", ""),
                "professional_analysis": None,
                "ml_predictions": None,
                "risk_analysis": None,
                # Validation defaults
                "validation_points": [],
                "final_accuracy": None,
                "ml_processed": False,
                "hourly_validated": False,
                "last_validation": None,
                "trade_metrics": None,
                "validation_status": "PENDING",
                "validation_error": ""
            }
            
            print(f"[INFO] ✅ AI prediction data prepared ({'test mode' if test_mode else 'production mode'})")
            
            # No file saving - data only prepared for potential database use
            print(f"[INFO] 📊 Data prepared (no files created)")
            
            return prediction_data
            
        except Exception as e:
            print(f"[ERROR] Saving AI prediction: {e}")
            return None

    def run_ai_prediction(self, market_data, test_mode=False, reasoning_mode=False, save_results=True, send_telegram=True):
        """Complete AI prediction workflow"""
        try:
            # Determine mode text
            if reasoning_mode:
                mode_text = "🧠 REASONING MODE"
            elif test_mode:
                mode_text = "🧪 TEST MODE"
            else:
                mode_text = "🚀 PRODUCTION MODE"
                
            print("\n" + "="*50)
            print(f"🤖 STARTING AI PREDICTION SYSTEM - {mode_text}")
            print("="*50)
            
            # Generate AI prediction with reasoning mode if enabled
            ai_result = self.get_ai_prediction(market_data, reasoning_mode)
            
            if "error" in ai_result:
                print(f"[CRITICAL] AI prediction failed: {ai_result['error']}")
                return ai_result
            
            # Final validation: Check if prediction was blocked due to data quality
            if ai_result.get('status') == 'BLOCKED':
                print(f"[WARN] AI prediction blocked: {ai_result.get('reason', 'Unknown reason')}")
                return ai_result
            
            # Prepare prediction data (no saving)
            if save_results:
                saved_data = self.save_ai_prediction(ai_result, market_data, test_mode)
                if saved_data:
                    print(f"[INFO] ✅ AI prediction data prepared")
            
            # Send Telegram message if requested
            if send_telegram and self.config["telegram"]["enabled"]:
                telegram_success = self.send_ai_telegram(ai_result, market_data, test_mode, reasoning_mode)
                if not telegram_success:
                    print("[WARN] Telegram sending failed")
            
            print("\n" + "="*50)
            print(f"🤖 AI PREDICTION SYSTEM COMPLETE - {mode_text}")
            print("="*50)
            
            return ai_result
            
        except Exception as e:
            print(f"[CRITICAL] AI prediction workflow failed: {e}")
            return {
                "prediction": None,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "FAILED"
            }
    
    def _create_data_completeness_tracker(self, market_data):
        """Create a visual tracker showing which data points are available vs missing"""
        tracker_lines = []
        
        # 1. CRYPTO PRICES (2 points)
        crypto = market_data.get("crypto", {})
        btc_available = "✅" if crypto.get("btc") else "❌"
        eth_available = "✅" if crypto.get("eth") else "❌"
        tracker_lines.append(f"💰 Crypto Prices: BTC {btc_available} | ETH {eth_available}")
        
        # 2. TECHNICAL INDICATORS (12 points - 6 per coin)
        tech = market_data.get("technical_indicators", {})
        btc_tech = tech.get("BTC", {})
        eth_tech = tech.get("ETH", {})
        
        btc_rsi = "✅" if btc_tech.get("rsi14") is not None else "❌"
        btc_signal = "✅" if btc_tech.get("signal") else "❌"
        btc_trend = "✅" if btc_tech.get("trend") else "❌"
        btc_support = "✅" if btc_tech.get("support") else "❌"
        btc_resistance = "✅" if btc_tech.get("resistance") else "❌"
        btc_volatility = "✅" if btc_tech.get("volatility") else "❌"
        
        eth_rsi = "✅" if eth_tech.get("rsi14") is not None else "❌"
        eth_signal = "✅" if eth_tech.get("signal") else "❌"
        eth_trend = "✅" if eth_tech.get("trend") else "❌"
        eth_support = "✅" if eth_tech.get("support") else "❌"
        eth_resistance = "✅" if eth_tech.get("resistance") else "❌"
        eth_volatility = "✅" if eth_tech.get("volatility") else "❌"
        
        tracker_lines.append(f"📈 Technical Indicators: BTC {btc_rsi}{btc_signal}{btc_trend}{btc_support}{btc_resistance}{btc_volatility} | ETH {eth_rsi}{eth_signal}{eth_trend}{eth_support}{eth_resistance}{eth_volatility}")
        
        # 3. FUTURES DATA (8 points - 4 per coin)
        futures = market_data.get("futures", {})
        btc_futures = futures.get("BTC", {})
        eth_futures = futures.get("ETH", {})
        
        btc_funding = "✅" if btc_futures.get("funding_rate") is not None else "❌"
        btc_long = "✅" if btc_futures.get("long_ratio") is not None else "❌"
        btc_short = "✅" if btc_futures.get("short_ratio") is not None else "❌"
        btc_oi = "✅" if btc_futures.get("open_interest") else "❌"
        
        eth_funding = "✅" if eth_futures.get("funding_rate") is not None else "❌"
        eth_long = "✅" if eth_futures.get("long_ratio") is not None else "❌"
        eth_short = "✅" if eth_futures.get("short_ratio") is not None else "❌"
        eth_oi = "✅" if eth_futures.get("open_interest") else "❌"
        
        tracker_lines.append(f"📊 Futures Data: BTC {btc_funding}{btc_long}{btc_short}{btc_oi} | ETH {eth_funding}{eth_long}{eth_short}{eth_oi}")
        
        # 4. MARKET SENTIMENT (3 points)
        fear_greed = market_data.get("fear_greed", {})
        btc_dom = market_data.get("btc_dominance")
        market_cap = market_data.get("market_cap")
        
        fg_index = "✅" if fear_greed.get("index") is not None else "❌"
        btc_dom_avail = "✅" if btc_dom is not None else "❌"
        mc_avail = "✅" if market_cap else "❌"
        
        tracker_lines.append(f"😱 Market Sentiment: F&G {fg_index} | BTC Dom {btc_dom_avail} | MC {mc_avail}")
        
        # 5. TRADING VOLUMES (2 points)
        volumes = market_data.get("volumes", {})
        btc_vol = "✅" if volumes.get("btc_volume") else "❌"
        eth_vol = "✅" if volumes.get("eth_volume") else "❌"
        
        tracker_lines.append(f"📊 Trading Volumes: BTC {btc_vol} | ETH {eth_vol}")
        
        # 6. MACROECONOMIC (4 points)
        m2_data = market_data.get("m2_supply", {})
        inflation = market_data.get("inflation", {})
        rates = market_data.get("interest_rates", {})
        
        m2_avail = "✅" if m2_data.get("m2_supply") else "❌"
        inflation_avail = "✅" if inflation.get("inflation_rate") is not None else "❌"
        fed_rate = "✅" if rates.get("fed_rate") is not None else "❌"
        t10_yield = "✅" if rates.get("t10_yield") is not None else "❌"
        
        tracker_lines.append(f"🏛️ Macroeconomic: M2 {m2_avail} | Inflation {inflation_avail} | Fed {fed_rate} | 10Y {t10_yield}")
        
        # 7. STOCK INDICES (4 points)
        stock_indices = market_data.get("stock_indices", {})
        sp500 = "✅" if stock_indices.get("sp500") is not None else "❌"
        nasdaq = "✅" if stock_indices.get("nasdaq") is not None else "❌"
        dow = "✅" if stock_indices.get("dow_jones") is not None else "❌"
        vix = "✅" if stock_indices.get("vix") is not None else "❌"
        
        tracker_lines.append(f"📈 Stock Indices: S&P500 {sp500} | NASDAQ {nasdaq} | Dow {dow} | VIX {vix}")
        
        # 8. COMMODITIES (4 points)
        commodities = market_data.get("commodities", {})
        gold = "✅" if commodities.get("gold") is not None else "❌"
        silver = "✅" if commodities.get("silver") is not None else "❌"
        oil = "✅" if commodities.get("crude_oil") is not None else "❌"
        gas = "✅" if commodities.get("natural_gas") is not None else "❌"
        
        tracker_lines.append(f"🥇 Commodities: Gold {gold} | Silver {silver} | Oil {oil} | Gas {gas}")
        
        # 9. SOCIAL METRICS (6 points)
        social = market_data.get("social_metrics", {})
        forum_posts = "✅" if social.get("forum_posts") else "❌"
        forum_topics = "✅" if social.get("forum_topics") else "❌"
        btc_github = "✅" if social.get("btc_github_stars") else "❌"
        eth_github = "✅" if social.get("eth_github_stars") else "❌"
        btc_commits = "✅" if social.get("btc_recent_commits") else "❌"
        eth_commits = "✅" if social.get("eth_recent_commits") else "❌"
        
        tracker_lines.append(f"📱 Social Metrics: Posts {forum_posts} | Topics {forum_topics} | BTC Git {btc_github} | ETH Git {eth_github} | BTC Commits {btc_commits} | ETH Commits {eth_commits}")
        
        # 10. HISTORICAL DATA (2 points)
        historical = market_data.get("historical_data", {})
        btc_hist = "✅" if historical.get("BTC") else "❌"
        eth_hist = "✅" if historical.get("ETH") else "❌"
        
        tracker_lines.append(f"📊 Historical Data: BTC {btc_hist} | ETH {eth_hist}")
        
        # 11. ENHANCED DATA SOURCES (8 points)
        order_book = market_data.get("order_book_analysis", {})
        liquidation = market_data.get("liquidation_heatmap", {})
        economic_cal = market_data.get("economic_calendar", {})
        multi_sentiment = market_data.get("multi_source_sentiment", {})
        whale_data = market_data.get("whale_movements", {})
        volatility = market_data.get("volatility_regime", {})
        
        ob_avail = "✅" if order_book else "❌"
        liq_avail = "✅" if liquidation else "❌"
        econ_avail = "✅" if economic_cal else "❌"
        multi_avail = "✅" if multi_sentiment else "❌"
        whale_avail = "✅" if whale_data else "❌"
        vol_avail = "✅" if volatility else "❌"
        
        tracker_lines.append(f"🔧 Enhanced Sources: Order Book {ob_avail} | Liquidation {liq_avail} | Economic {econ_avail} | Multi-Sentiment {multi_avail} | Whale {whale_avail} | Volatility {vol_avail}")
        
        # 12. NETWORK HEALTH (6 points)
        btc_network = market_data.get("btc_network_health", {})
        eth_network = market_data.get("eth_network_health", {})
        
        btc_hash = "✅" if btc_network.get("hash_rate") else "❌"
        btc_diff = "✅" if btc_network.get("mining_difficulty") else "❌"
        btc_mempool = "✅" if btc_network.get("mempool_congestion") is not None else "❌"
        btc_addresses = "✅" if btc_network.get("active_addresses") is not None else "❌"
        eth_gas = "✅" if eth_network.get("gas_pressure") is not None else "❌"
        eth_supply = "✅" if eth_network.get("total_supply") else "❌"
        
        tracker_lines.append(f"🌐 Network Health: BTC Hash {btc_hash} | BTC Diff {btc_diff} | BTC Mempool {btc_mempool} | BTC Addr {btc_addresses} | ETH Gas {eth_gas} | ETH Supply {eth_supply}")
        
        # 13. CORRELATIONS (8 points)
        crypto_corr = market_data.get("crypto_correlations", {})
        cross_asset = market_data.get("cross_asset_correlations", {})
        
        btc_eth_30d = "✅" if crypto_corr.get("btc_eth_correlation_30d") is not None else "❌"
        corr_strength = "✅" if crypto_corr.get("correlation_strength") else "❌"
        corr_direction = "✅" if crypto_corr.get("correlation_direction") else "❌"
        corr_trend = "✅" if crypto_corr.get("correlation_trend") else "❌"
        market_regime = "✅" if cross_asset.get("market_regime") else "❌"
        crypto_equity = "✅" if cross_asset.get("crypto_equity_regime") else "❌"
        sp500_change = "✅" if cross_asset.get("sp500_change_24h") is not None else "❌"
        equity_significance = "✅" if cross_asset.get("equity_move_significance") else "❌"
        
        tracker_lines.append(f"🔗 Correlations: BTC-ETH 30d {btc_eth_30d} | Strength {corr_strength} | Direction {corr_direction} | Trend {corr_trend} | Market Regime {market_regime} | Crypto-Equity {crypto_equity} | SP500 {sp500_change} | Equity Sig {equity_significance}")
        
        # 14. CFTC POSITIONING (8 points)
        cftc = market_data.get("cftc_positioning", {})
        
        inst_sentiment = "✅" if cftc.get("institutional_sentiment") else "❌"
        commercial_signal = "✅" if cftc.get("commercial_signal") else "❌"
        leveraged_pct = "✅" if cftc.get("leveraged_positioning_pct") is not None else "❌"
        contrarian = "✅" if cftc.get("contrarian_signal") else "❌"
        smart_money = "✅" if cftc.get("smart_money_net") is not None else "❌"
        overall_sentiment = "✅" if cftc.get("overall_cftc_sentiment") else "❌"
        positioning_extreme = "✅" if cftc.get("positioning_extreme") else "❌"
        open_interest = "✅" if cftc.get("open_interest") else "❌"
        
        tracker_lines.append(f"🏛️ CFTC Positioning: Inst Sentiment {inst_sentiment} | Commercial {commercial_signal} | Leveraged % {leveraged_pct} | Contrarian {contrarian} | Smart Money {smart_money} | Overall {overall_sentiment} | Extreme {positioning_extreme} | OI {open_interest}")
        
        return "\n".join(tracker_lines)

    async def generate_prediction(self, market_data, test_mode=False, reasoning_mode=False):
        """Generate AI prediction (async wrapper for compatibility)"""
        try:
            result = self.run_ai_prediction(market_data, test_mode, reasoning_mode, save_results=True, send_telegram=True)
            if result is None:
                return {
                    "prediction": None,
                    "error": "AI prediction failed - no result returned",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "FAILED"
                }
            return result
        except Exception as e:
            print(f"[ERROR] AI prediction generation failed: {e}")
            return {
                "prediction": None,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "FAILED"
            }


# Utility function for external use
def create_ai_predictor(config):
    """Factory function to create an AI predictor instance"""
    return AIPredictor(config)


if __name__ == "__main__":
    # Test the AI predictor
    print("Testing AI predictor...")
    
    # Mock config for testing
    test_config = {
        "api_keys": {
            "openai": "YOUR_OPENAI_API_KEY"
        },
        "telegram": {
            "enabled": True,
            "bot_token": "YOUR_BOT_TOKEN",
            "chat_id": "YOUR_CHAT_ID",
            "test": {
                "bot_token": "YOUR_TEST_BOT_TOKEN",
                "chat_id": "YOUR_TEST_CHAT_ID"
            }
        }
    }
    
    # Mock market data for testing
    mock_market_data = {
        "crypto": {"btc": 45000, "eth": 2800},
        "fear_greed": {"index": 35, "sentiment": "Fear"},
        "btc_dominance": 52.5,
        "technical_indicators": {
            "BTC": {
                "price": 45000,
                "rsi14": 45.2,
                "signal": "BUY",
                "trend": "bullish",
                "support": 44000,
                "resistance": 46000,
                "volatility": "medium"
            },
            "ETH": {
                "price": 2800,
                "rsi14": 48.1,
                "signal": "BUY", 
                "trend": "bullish",
                "support": 2750,
                "resistance": 2850,
                "volatility": "medium"
            }
        }
    }
    
    try:
        predictor = AIPredictor(test_config)
        result = predictor.get_ai_prediction(mock_market_data)
        print(f"\nAI prediction test:")
        print(f"Success: {result is not None}")
        print(f"Data points used: {result.get('data_points_used', 0)}")
    except Exception as e:
        print(f"Test failed: {e}")