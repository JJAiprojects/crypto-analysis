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
        
        # BTC and ETH specific data
        btc_data = technicals.get("BTC", {})
        eth_data = technicals.get("ETH", {})
        btc_futures = futures.get("BTC", {})
        eth_futures = futures.get("ETH", {})
        
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
        
        data_quality_header = ""
        if data_quality_warnings:
            data_quality_header = f"""

🚨 DATA QUALITY WARNINGS:
{chr(10).join(data_quality_warnings)}

⚠️ CRITICAL: You are working with incomplete market structure data. 
   - Order book analysis unavailable: Cannot assess smart money flow
   - Liquidation heatmap unavailable: Cannot identify price targets
   - Economic calendar unavailable: Cannot assess market timing risks
   - Correlation data unavailable: Cannot assess BTC-ETH relationship

⚠️ RECOMMENDATION: If these warnings appear, DO NOT make trading predictions.
   Instead, explain why predictions would be unreliable and what data is needed.
"""
        
        prompt = f"""You are a professional crypto trader with 15+ years experience.{data_quality_header}

⚠️ CRITICAL INSTRUCTION: You MUST follow the 8-STEP ENHANCED DECISION FRAMEWORK internally to analyze the data. This framework is MANDATORY and cannot be ignored. Only provide the final CONCISE trading outlook based on this framework.

MARKET DATA HIERARCHY ({data_points_used}/57 indicators):
=========================================================

🔥 SUPER HIGH PRIORITY (Absolute Override - Can Force Flat Position):
• Economic Calendar: {economic_cal.get('recommendation', 'N/A') if economic_cal else 'API_KEY_MISSING'} | High Impact Events: {economic_cal.get('high_impact', 0) if economic_cal else 0} | Next: {economic_cal.get('next_high_impact', {}).get('title', 'None')[:30] if economic_cal and economic_cal.get('next_high_impact') else 'None'}
• Volatility Regime: {volatility_regime.get('current_regime', 'N/A')} | Position Size Multiplier: {volatility_regime.get('size_multiplier', 1.0):.1f}x | Risk State: {volatility_regime.get('risk_state', 'N/A')}

🚨 HIGH PRIORITY (Override Traditional S/R & Price Targets):
• Liquidation BTC: {liquidation_map.get('BTC', {}).get('liquidation_pressure', 'N/A') if liquidation_map else 'API_KEY_MISSING'} | Funding: {f"{liquidation_map.get('BTC', {}).get('funding_rate', 0):.3f}" if liquidation_map and liquidation_map.get('BTC') and liquidation_map.get('BTC', {}).get('funding_rate') is not None else 'N/A'}% | Long/Short zones: {len(liquidation_map.get('BTC', {}).get('nearby_long_liquidations', []))} / {len(liquidation_map.get('BTC', {}).get('nearby_short_liquidations', []))}
• Liquidation ETH: {liquidation_map.get('ETH', {}).get('liquidation_pressure', 'N/A') if liquidation_map else 'API_KEY_MISSING'} | Funding: {f"{liquidation_map.get('ETH', {}).get('funding_rate', 0):.3f}" if liquidation_map and liquidation_map.get('ETH') and liquidation_map.get('ETH', {}).get('funding_rate') is not None else 'N/A'}% | Long/Short zones: {len(liquidation_map.get('ETH', {}).get('nearby_long_liquidations', []))} / {len(liquidation_map.get('ETH', {}).get('nearby_short_liquidations', []))}
• Bond Market Signal: 10Y Treasury: {f"{rates_data.get('t10_yield'):.2f}" if rates_data.get('t10_yield') is not None else 'N/A'}% | Risk-Off Threshold: {'BREACHED' if rates_data.get('t10_yield', 0) > 4.5 else 'NORMAL'} | Crypto Impact: {self._assess_treasury_impact(rates_data.get('t10_yield'))}

⚠️ MEDIUM PRIORITY (Entry Timing & Smart Money Flow):
• Order Book BTC: {order_book.get('BTC', {}).get('book_signal', 'N/A') if order_book else 'API_KEY_MISSING'} | Imbalance: {f"{order_book.get('BTC', {}).get('imbalance_ratio', 0)*100:.1f}" if order_book and order_book.get('BTC') and order_book.get('BTC', {}).get('imbalance_ratio') is not None else 'N/A'}% | MM: {f"{order_book.get('BTC', {}).get('mm_dominance', 0)*100:.1f}" if order_book and order_book.get('BTC') and order_book.get('BTC', {}).get('mm_dominance') is not None else 'N/A'}%
• Order Book ETH: {order_book.get('ETH', {}).get('book_signal', 'N/A') if order_book else 'API_KEY_MISSING'} | Imbalance: {f"{order_book.get('ETH', {}).get('imbalance_ratio', 0)*100:.1f}" if order_book and order_book.get('ETH') and order_book.get('ETH', {}).get('imbalance_ratio') is not None else 'N/A'}% | MM: {f"{order_book.get('ETH', {}).get('mm_dominance', 0)*100:.1f}" if order_book and order_book.get('ETH') and order_book.get('ETH', {}).get('mm_dominance') is not None else 'N/A'}%
• Volume Intelligence BTC: 24h: ${f"{volumes.get('btc_volume', 0)/1e9:.1f}" if volumes.get('btc_volume') else 'N/A'}B | Trend: {btc_data.get('volume_trend', 'N/A')} | Volume Signal: {self._analyze_volume_signal('BTC', volumes, btc_data)}
• Volume Intelligence ETH: 24h: ${f"{volumes.get('eth_volume', 0)/1e9:.1f}" if volumes.get('eth_volume') else 'N/A'}B | Trend: {eth_data.get('volume_trend', 'N/A')} | Volume Signal: {self._analyze_volume_signal('ETH', volumes, eth_data)}
• Whale Movements: {whale_data.get('whale_signal', 'N/A') if whale_data else 'API_KEY_MISSING'} | Sentiment: {f"{whale_data.get('whale_sentiment', 0):.2f}" if whale_data and whale_data.get('whale_sentiment') is not None else 'N/A'} | Active Signals: {whale_data.get('signals_detected', 0) if whale_data else 0}
• Smart Money Flow: {whale_data.get('breakdown', {}).get('large_trades', {}).get('activity', 'N/A') if whale_data and whale_data.get('breakdown') and whale_data.get('breakdown', {}).get('large_trades') else 'N/A'} | Exchange Flows: {whale_data.get('breakdown', {}).get('exchange_flows', {}).get('activity', 'N/A') if whale_data and whale_data.get('breakdown') and whale_data.get('breakdown', {}).get('exchange_flows') else 'N/A'}

🟢 LOW PRIORITY (Traditional Analysis - Confirmation Only):
• Fear & Greed: {fear_greed.get('index', 'N/A')} ({fear_greed.get('sentiment', 'N/A')})
• Multi-Source Sentiment: {multi_sentiment.get('sentiment_signal', 'N/A') if multi_sentiment else 'LIMITED_DATA'} | Sources: {multi_sentiment.get('sources_analyzed', 0) if multi_sentiment else 0} | Score: {f"{multi_sentiment.get('average_sentiment'):.2f}" if multi_sentiment and multi_sentiment.get('average_sentiment') is not None else 'N/A'}
• BTC Trend: {btc_data.get('trend', 'N/A')} | Price: ${f"{btc_data.get('price'):,}" if btc_data.get('price') else 'N/A'} | RSI: {f"{btc_data.get('rsi14'):.1f}" if btc_data.get('rsi14') is not None else 'N/A'} | Signal: {btc_data.get('signal', 'N/A')}
• ETH Trend: {eth_data.get('trend', 'N/A')} | Price: ${f"{eth_data.get('price'):,}" if eth_data.get('price') else 'N/A'} | RSI: {f"{eth_data.get('rsi14'):.1f}" if eth_data.get('rsi14') is not None else 'N/A'} | Signal: {eth_data.get('signal', 'N/A')}
• S&P 500: {f"{stock_indices.get('sp500'):,.0f}" if stock_indices.get('sp500') is not None else 'N/A'} | VIX: {f"{stock_indices.get('vix'):.1f}" if stock_indices.get('vix') is not None else 'N/A'}
• Global Market Cap: ${market_cap_data[0] if market_cap_data[0] else 0:,.0f} USD ({market_cap_data[1] if market_cap_data[1] else 0:+.1f}% 24h)
• BTC Support/Resistance (PRIMARY): ${f"{btc_data.get('support'):,}" if btc_data.get('support') else 'N/A'} / ${f"{btc_data.get('resistance'):,}" if btc_data.get('resistance') else 'N/A'} (Pivot method - USE THESE)
• ETH Support/Resistance (PRIMARY): ${f"{eth_data.get('support'):,}" if eth_data.get('support') else 'N/A'} / ${f"{eth_data.get('resistance'):,}" if eth_data.get('resistance') else 'N/A'} (Pivot method - USE THESE)

⚠️ SUPPORT/RESISTANCE USAGE RULES:
- PRIMARY: Always use pivot point levels (support/resistance) for entries and targets
- REFERENCE: ATR levels (atr_support/atr_resistance) for volatility context only
- REFERENCE: SMA levels (sma_support/sma_resistance) for trend context only
- RISK MANAGEMENT: Use ATR for stop loss calculations
- NEVER: Override pivot levels with ATR/SMA levels unless liquidation clusters present

🔧 ENHANCED TECHNICAL PRECISION (Advanced Analysis):
- BTC Advanced: ATR: ${f"{btc_data.get('atr'):,.0f}" if btc_data.get('atr') else 'N/A'} ({f"{(btc_data.get('atr', 0) / (btc_data.get('price') or 1)) * 100:.1f}" if btc_data.get('atr') and btc_data.get('price') else 'N/A'}%) | SMA7/14/50: ${f"{btc_data.get('sma7'):,.0f}" if btc_data.get('sma7') else 'N/A'}/${f"{btc_data.get('sma14'):,.0f}" if btc_data.get('sma14') else 'N/A'}/${f"{btc_data.get('sma50'):,.0f}" if btc_data.get('sma50') else 'N/A'}
- BTC Reference Levels: ATR Support: ${f"{btc_data.get('atr_support'):,.0f}" if btc_data.get('atr_support') else 'N/A'} | ATR Resistance: ${f"{btc_data.get('atr_resistance'):,.0f}" if btc_data.get('atr_resistance') else 'N/A'} | SMA Support: ${f"{btc_data.get('sma_support'):,.0f}" if btc_data.get('sma_support') else 'N/A'} | SMA Resistance: ${f"{btc_data.get('sma_resistance'):,.0f}" if btc_data.get('sma_resistance') else 'N/A'} | Volume: {btc_data.get('volume_trend', 'N/A')}
- ETH Advanced: ATR: ${f"{eth_data.get('atr'):,.0f}" if eth_data.get('atr') else 'N/A'} ({f"{(eth_data.get('atr', 0) / (eth_data.get('price') or 1)) * 100:.1f}" if eth_data.get('atr') and eth_data.get('price') else 'N/A'}%) | SMA7/14/50: ${f"{eth_data.get('sma7'):,.0f}" if eth_data.get('sma7') else 'N/A'}/${f"{eth_data.get('sma14'):,.0f}" if eth_data.get('sma14') else 'N/A'}/${f"{eth_data.get('sma50'):,.0f}" if eth_data.get('sma50') else 'N/A'}
- ETH Reference Levels: ATR Support: ${f"{eth_data.get('atr_support'):,.0f}" if eth_data.get('atr_support') else 'N/A'} | ATR Resistance: ${f"{eth_data.get('atr_resistance'):,.0f}" if eth_data.get('atr_resistance') else 'N/A'} | SMA Support: ${f"{eth_data.get('sma_support'):,.0f}" if eth_data.get('sma_support') else 'N/A'} | SMA Resistance: ${f"{eth_data.get('sma_resistance'):,.0f}" if eth_data.get('sma_resistance') else 'N/A'} | Volume: {eth_data.get('volume_trend', 'N/A')}

🔴 ADDITIONAL CONTEXT:
• BTC Funding: {f"{btc_futures.get('funding_rate'):.3f}" if btc_futures.get('funding_rate') is not None else 'N/A'}% | ETH Funding: {f"{eth_futures.get('funding_rate'):.3f}" if eth_futures.get('funding_rate') is not None else 'N/A'}%
• BTC Long/Short: {f"{btc_futures.get('long_ratio'):.0f}" if btc_futures.get('long_ratio') is not None else 'N/A'}/{f"{btc_futures.get('short_ratio'):.0f}" if btc_futures.get('short_ratio') is not None else 'N/A'} | ETH Long/Short: {f"{eth_futures.get('long_ratio'):.0f}" if eth_futures.get('long_ratio') is not None else 'N/A'}/{f"{eth_futures.get('short_ratio'):.0f}" if eth_futures.get('short_ratio') is not None else 'N/A'}
• BTC Volume: ${f"{volumes.get('btc_volume', 0)/1e9:.1f}" if volumes.get('btc_volume') else 'N/A'}B | ETH Volume: ${f"{volumes.get('eth_volume', 0)/1e9:.1f}" if volumes.get('eth_volume') else 'N/A'}B
• BTC Dominance: {btc_dominance:.1f}% | Inflation: {f"{inflation_data.get('inflation_rate'):.1f}" if inflation_data.get('inflation_rate') is not None else 'N/A'}% | Fed Rate: {f"{rates_data.get('fed_rate'):.2f}" if rates_data.get('fed_rate') is not None else 'N/A'}%

🔵 MACROECONOMIC & MARKET CONTEXT:
• M2 Money Supply: ${f"{m2_data.get('m2_supply', 0)/1e12:.1f}" if m2_data.get('m2_supply') else 'N/A'}T | Date: {m2_data.get('m2_date', 'N/A')}
• NASDAQ: {f"{stock_indices.get('nasdaq'):,.0f}" if stock_indices.get('nasdaq') is not None else 'N/A'} | Dow Jones: {f"{stock_indices.get('dow_jones'):,.0f}" if stock_indices.get('dow_jones') is not None else 'N/A'}
• Precious Metals: Gold ${f"{commodities.get('gold'):,.0f}" if commodities.get('gold') is not None else 'N/A'}/oz | Silver ${f"{commodities.get('silver'):,.2f}" if commodities.get('silver') is not None else 'N/A'}/oz
• Energy Complex: Crude Oil ${f"{commodities.get('crude_oil'):,.1f}" if commodities.get('crude_oil') is not None else 'N/A'}/bbl | Natural Gas ${f"{commodities.get('natural_gas'):,.2f}" if commodities.get('natural_gas') is not None else 'N/A'}/MMBtu | Energy Signal: {self._assess_energy_signal(commodities)}
• Social Activity: Forum Posts: {f"{social_metrics.get('forum_posts', 0):,}" if social_metrics.get('forum_posts') else 'N/A'} | BTC GitHub: {f"{social_metrics.get('btc_github_stars', 0):,}" if social_metrics.get('btc_github_stars') else 'N/A'} stars | ETH GitHub: {f"{social_metrics.get('eth_github_stars', 0):,}" if social_metrics.get('eth_github_stars') else 'N/A'} stars

🕐 HISTORICAL CONTEXT & TREND VALIDATION:
==============================================

🔵 BTC Multi-Timeframe Analysis:
- Daily Trend: SMA20: ${self._safe_get_historical_value(historical, 'BTC', '1d', 'sma20'):,.0f} | SMA50: ${self._safe_get_historical_value(historical, 'BTC', '1d', 'sma50'):,.0f} | SMA200: ${self._safe_get_historical_value(historical, 'BTC', '1d', 'sma200'):,.0f}
- Weekly Position: Price vs SMA200: {self._get_sma_position(historical, 'BTC')}
- MACD Signal: {self._get_macd_signal(historical, 'BTC', '1d')}
- Momentum State: {self._analyze_momentum_state(historical.get('BTC', {}))}

📊 ETH Multi-Timeframe Analysis:  
- Daily Trend: SMA20: ${self._safe_get_historical_value(historical, 'ETH', '1d', 'sma20'):,.0f} | SMA50: ${self._safe_get_historical_value(historical, 'ETH', '1d', 'sma50'):,.0f} | SMA200: ${self._safe_get_historical_value(historical, 'ETH', '1d', 'sma200'):,.0f}
- Weekly Position: Price vs SMA200: {self._get_sma_position(historical, 'ETH')}
- MACD Signal: {self._get_macd_signal(historical, 'ETH', '1d')}
- Momentum State: {self._analyze_momentum_state(historical.get('ETH', {}))}

⚡ CRITICAL HISTORICAL OVERRIDES:
- Long-term Trend Direction: {self._determine_longterm_trend(historical)}
- Historical Resistance Confluence: {self._find_historical_resistance_levels(historical)}
- Multi-timeframe Momentum Alignment: {self._check_momentum_alignment(historical)}

⚠️ FORMATTING REQUIREMENTS:
- All prices must be whole numbers (no decimals): $106,384 not $106,384.79
- Use comma separators for thousands: $106,384, $2,454
- Percentages can have 1 decimal: 0.8%, 1.2%
- Confidence levels are whole numbers: 70%, 75%

📊 DATA INCOMPLETENESS HANDLING:
- "N/A" or "nan" values: Ignore completely, do not fabricate data
- Missing data sources: Reduce confidence by 10-15% per missing source
- Limited data: Flag as "LIMITED_ANALYSIS" and reduce position size
- API failures: Use available data only, never assume missing values

🔗 CORRELATION ANALYSIS INTEGRATION:
- BTC-ETH Correlation: Use correlation data for joint positioning decisions
- High correlation (>0.7): Similar position sizing and timing
- Low correlation (<0.3): Independent positioning allowed
- Negative correlation: Consider inverse positioning for diversification
- Cross-asset correlation: Use market regime data for risk adjustment

🎯 PROBABILISTIC FORECASTING:
- Confidence levels represent win probability estimates
- High confidence (75-85%): Strong signal alignment, higher win rate expected
- Medium confidence (60-74%): Mixed signals, moderate win rate expected  
- Low confidence (45-59%): Weak signals, lower win rate expected
- Very low confidence (<45%): Avoid trading, wait for better setup

ENHANCED 8-STEP INTERNAL ANALYSIS FRAMEWORK (Do NOT output these steps):
========================================================================

PRIORITY-BASED OVERRIDE LOGIC:
• 🔥 SUPER HIGH: Economic Events + Volatility Regimes = Can FORCE FLAT POSITION regardless of all other signals
• 🚨 HIGH: Liquidation Clusters = REPLACE traditional support/resistance as primary price targets
• ⚠️ MEDIUM: Order Book + Whales = GATE execution (only trade if these align with direction)
• 🟢 LOW: Traditional TA + Sentiment = Confirmation only, NEVER override higher priority signals

STEP 0: CONFLICT RESOLUTION HIERARCHY (Handle Contradictions):
- SUPER HIGH vs HIGH: Economic Events and Volatility override everything → FORCE FLAT if conflict
- HIGH PRIORITY CONFLICTS: If Liquidation signals contradict Bond Market signals → Use MOST RECENT liquidation data, discount bond impact by 50%  
- MEDIUM PRIORITY CONFLICTS: If Order Book vs Whale Movements contradict → Require 70%+ conviction on BOTH or reduce to SIDEWAYS
- If Traditional TA conflicts with higher priorities → Ignore traditional signals completely
- CONFLICT RESOLUTION RULE: When in doubt, choose FLAT position over conflicted trade

STEP 0.5: SIDEWAYS MARKET DETECTION & TREND VALIDATION + NOISE FILTERING
- Check if market is in sideways consolidation: Price range <1% and RSI 40-60 over last 3h
- Check for mixed signals: If high-priority signals conflict by >50%, flag as potential sideways
- BREAKOUT POTENTIAL CHECK: If sideways, check volume >1.5x 3-hour average and price within 0.5% of support/resistance
- IF BREAKOUT POTENTIAL: Flag for conditional breakout setup in Step 7
- IF SIDEWAYS DETECTED: Set bias to "SIDEWAYS" and proceed to Step 7
- IF TRENDING: Continue with normal analysis flow
- TREND VALIDATION: Check last 2-3 candles for momentum changes with noise filtering:
  * Minimum threshold: >0.5% move required to trigger validation
  * Confirmation requirement: 2 consecutive 1-hour candles in same direction (green/bullish, red/bearish) with volume >10% above 3-hour average
  * Apply individually to BTC and ETH
  * If threshold met but no confirmation → Flag as potential noise, continue monitoring
- REVERSAL ALERT: If >2 consecutive opposite candles with confirmation → Flag for bias adjustment
- RULE: SIDEWAYS covers both consolidation patterns and mixed/uncertain signals, noise filtering prevents false signals

📊 TERMINOLOGY DEFINITIONS:
- Volatility Ratio: Current ATR / Average ATR (last 24h) - measures relative volatility
- Mixed Signals >50%: When more than half of high-priority signals conflict
- Adaptive Thresholds: Signal strength requirements that adjust to market volatility
- Noise Filtering: Ignoring small price movements that don't confirm larger trends

STEP 1: Economic Event Override Check + Bond Market Check
- If Economic Calendar shows "AVOID_TRADING" OR high-impact event in next 24h → FORCE FLAT POSITION
- If 10Y Treasury > 4.5% → REDUCE RISK APPETITE (smaller positions, higher stop losses)
- If 10Y Treasury > 5.0% → CONSIDER FLAT POSITION (bonds competing with risk assets)
- If Volatility Regime = "EXTREME" → Reduce position size by regime multiplier regardless of setup quality

STEP 2: Liquidation Magnet Analysis (OVERRIDE TRADITIONAL S/R)
- Check if liquidation clusters exist within 5% of current price
- IF LIQUIDATION CLUSTERS FOUND: Use ONLY liquidation levels, ignore traditional S/R completely
- IF NO LIQUIDATION CLUSTERS: Use traditional S/R but flag as "WEAKER SIGNALS"
- Priority order: 1) Liquidation clusters, 2) Pivot point S/R (script-calculated), 3) ATR/SMA reference levels
- MANDATORY: If liquidation pressure = "HIGH" → Liquidation targets become ONLY valid targets
- RULE: Never mix liquidation and traditional levels in same trade plan

STEP 3: Smart Money & Entry Timing Gate + Volume Confirmation + Adaptive Thresholds
- Check Order Book imbalance with adaptive thresholds:
  * Low Volatility: >60% = strong signal, 50-60% = moderate, <50% = weak
  * Medium Volatility: >75% = strong signal, 65-75% = moderate, <65% = weak
  * High/Extreme Volatility: >85% = strong signal, 75-85% = moderate, <75% = weak
- Check Whale Movement signal with same adaptive thresholds:
  * Low Volatility: >60% alignment required
  * Medium Volatility: >75% alignment required
  * High/Extreme Volatility: >85% alignment required
- VOLUME GATE: Only execute if volume confirms price signal (no weak volume signals)
- EXECUTION GATE: Only execute if BOTH order book AND whale signals AND volume support trade direction
- RULE: Don't fight smart money flow OR weak volume, adapt thresholds to market conditions

STEP 4: Technical Analysis WITH Historical Validation + Multi-timeframe Filter
- RSI, pivot point support/resistance (if not overridden by liquidations), trend direction
- BTC/ETH signals for directional bias
- HISTORICAL CHECK: Confirm signals align with multi-timeframe momentum
- WEEKLY/MONTHLY TREND: Only trade WITH long-term trend unless strong reversal signals
- OPTIONAL 4H FILTER: Check 4-hour SMA20 direction vs 1-hour trend for both BTC and ETH
  * If aligned: +5% confidence (capped at 85%) for respective coin
  * If misaligned: -5% confidence and flag "Trend Divergence Warning" for respective coin
- RULE: Technical signals must pass historical momentum filter, 4h filter is advisory only

STEP 5: Macro Trend Alignment Check
- Fear & Greed, BTC dominance, S&P 500/VIX for overall market bias
- Multi-source sentiment for crowd positioning
- Social metrics analysis: Forum activity, GitHub stars, developer sentiment
- RULE: Use for position sizing confidence, not trade direction

STEP 5.5: SOCIAL METRICS & DEVELOPER ACTIVITY ANALYSIS
- Forum activity spikes: >20% increase in posts = potential sentiment shift
- GitHub activity: BTC/ETH star changes indicate developer interest
- Developer sentiment: High activity = positive long-term outlook
- Social momentum: Trending topics and community engagement
- RULE: Social metrics are confirmation signals, not primary drivers

STEP 6: Sentiment Risk Assessment
- Check funding rates and long/short ratios for overcrowded trades
- High funding = crowded positioning = reversal risk
- Social sentiment extremes = potential reversal signals
- RULE: Avoid trading in same direction as extreme crowd positioning

STEP 7: Enhanced Execution Planning + Conditional Breakout Setup
- Entry zones: Use liquidation clusters if present, else pivot point S/R
- Stop loss: Place beyond next liquidation cluster or pivot point S/R level
- Take profit: Target liquidation clusters as magnetic price targets
- MINIMUM 1:2 R/R, but adjust for liquidation cluster distances
- CONDITIONAL BREAKOUT: If breakout potential flagged in Step 0.5, create additional breakout plan:
  * Entry: On breakout confirmation (candle close > resistance or < support by 1% with volume spike)
  * SL: Beyond the opposite level (1% below support for long, 1% above resistance for short)
  * TP: Next liquidation cluster or 2% move
  * Confidence: Reduce by 10% due to uncertainty
- RULE: Liquidation-aware stop/target placement

STEP 8: Dynamic Risk Management & Position Sizing + Confidence Calculation + Reversal Detection + ATR Trigger
- Normal market conditions = 100% position size (full intended trade)
- If Volatility Regime = "HIGH" or "EXTREME" → Reduce to 75% or 50%
- If Economic Calendar shows high risk → Reduce by 25% 
- If fighting Whale signals → Reduce by 25%
- REVERSAL DETECTION: Check latest 3 candles for both BTC and ETH individually
  * If BTC shows >1% opposite movement → Reduce BTC position to 50%
  * If ETH shows >1% opposite movement → Reduce ETH position to 50%
- ATR VOLATILITY TRIGGER: Check 1-hour ATR for both BTC and ETH individually
  * If BTC 1h ATR increases >2% from prior hour → Reduce BTC position by 25%
  * If ETH 1h ATR increases >2% from prior hour → Reduce ETH position by 25%
  * If BOTH ATRs spike >2% → Reduce both positions by 25% (correlation risk)
- If multiple risk factors present → Can reduce to minimum 25%
- If all signals align perfectly → Can use 100% even in elevated volatility
- CONFIDENCE CALCULATION: Base confidence = average of signal strengths (order book, volume, RSI, liquidation, whale movements)
- CONFIDENCE ADJUSTMENT: +5% if all high-priority signals align, -5% if misaligned by >50%
- CONFIDENCE CAP: Maximum 85% to account for market uncertainty
- POSITION SIZE REPRESENTS: Percentage of your intended trade size, NOT portfolio allocation
- OUTPUT: Present individual position sizes in each execution plan (100%, 75%, 50%, or 25%)

⚠️ REMINDER: You MUST follow the above 8-STEP FRAMEWORK (Steps 0-8) to analyze the data. Do not skip any steps.

POSITION SIZE INSTRUCTION:
Position Size represents the recommended position size for each coin individually (not portfolio allocation).
- Standard position: 100% (full position)
- Reduced risk: 75% (moderate position) 
- High risk conditions: 50% (conservative position)
- Extreme risk: 25% (minimal position)
- Reversal detection: 50% if >1% opposite movement in last 3 candles
Present in each execution plan as percentage of intended position size for that specific coin.

CRITICAL DECISION TREE:
======================
1. Sideways Market Detected? → If YES: Output "SIDEWAYS - No Entry, Monitor for breakout"
2. Economic Events = FLAT? → If YES: Output "FLAT - Major events pending"
3. Extreme Volatility? → If YES: Reduce size by regime multiplier  
4. Near Liquidation Clusters? → If YES: Use clusters as primary targets, ignore pivot point S/R
5. Order Book + Whales Aligned? → If NO: Lower confidence or avoid
6. Pivot point signals confirm? → If YES: Execute with priority-based sizing
7. Risk management applied? → Always adjust for volatility regime and event risk

OUTPUT PRIORITY: Economic Events > Liquidation Targets > Entry Timing > Pivot Point TA

PRIORITY-INTEGRATED TIMEFRAME LOGIC + VOLATILITY-BASED ACTIVATION:
- SUPER HIGH PRIORITY OVERRIDES: If Economic Events pending → Extend timeframe by 2x (wait for clarity)
- HIGH PRIORITY LIQUIDATION TARGETS: 2-6 hours (liquidations happen fast, use shorter timeframes)
  * VOLATILITY ACTIVATION: If Volatility Ratio >0.6 → Use 2-4h, if >0.9 with volume >2x average → Use 1-2h
- HIGH PRIORITY BOND MARKET MOVES: 12-48 hours (macro moves take time to develop)
- MEDIUM PRIORITY SMART MONEY: 4-12 hours (institutional flows develop over hours)
  * VOLATILITY ACTIVATION: If Volatility Ratio >0.6 → Use 2-4h, if >0.9 with volume >2x average → Use 1-2h
- LOW PRIORITY PIVOT POINT TA: 6-24 hours (standard technical patterns)
- VOLATILITY REGIME ADJUSTMENT: If "EXTREME" → Cut all timeframes by 50% (faster moves)
- CONFLICT RESOLUTION: If multiple timeframes suggested → Use the SHORTEST from highest priority signal
FINAL RULE: Priority level determines base timeframe, volatility regime adjusts duration and activation

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
- Volatility Regime: [regime] detected - position sizing adjusted accordingly
- Macro Risk: [traditional market alignment]
- Data Quality: [Limited analysis warnings if applicable]
- Social Sentiment: [Forum/GitHub activity insights]
- Win Probability: [Confidence-based win rate estimate]

[IF SIDEWAYS DETECTED, REPLACE EXECUTION PLANS WITH:]
<b>━━━ ⏸️ MARKET STATUS: SIDEWAYS ━━━</b>
- No Entry - Monitor for breakout (consolidation) or signal alignment (mixed signals)
- Key Levels: Support $[X], Resistance $[Y]
- Breakout Watch: Volume >1.5x average near levels
- Confidence: [XX]% (sideways uncertainty)
- Correlation Status: [BTC-ETH correlation during sideways]

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
Focus on the most critical information: Executive Summary, Execution Plans, and Risk Notes.

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
        
        return count

    # ============================================================================
    # NEW HELPER FUNCTIONS - ADD HERE
    # ============================================================================
    
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
            t10_yield = rates_data.get('t10_yield', 0)
            if t10_yield > 5.0:
                risk_factors.append(("treasury", 0.6))
            elif t10_yield > 4.5:
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
                return None
            
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
            return None

    async def generate_prediction(self, market_data, test_mode=False, reasoning_mode=False):
        """Generate AI prediction (async wrapper for compatibility)"""
        try:
            return self.run_ai_prediction(market_data, test_mode, reasoning_mode, save_results=True, send_telegram=True)
        except Exception as e:
            print(f"[ERROR] AI prediction generation failed: {e}")
            return None


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