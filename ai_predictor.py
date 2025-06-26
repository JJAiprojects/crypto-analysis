#!/usr/bin/env python3

import os
import json
import time
from datetime import datetime, timezone
from openai import OpenAI
from telegram_utils import send_telegram_message

class AIPredictor:
    def __init__(self, config):
        self.config = config
        self.openai_key = os.getenv("OPENAI_API_KEY") or config["api_keys"]["openai"]
        
        if not self.openai_key or self.openai_key == "YOUR_OPENAI_API_KEY":
            raise ValueError("OpenAI API key not configured")
        
        self.client = OpenAI(api_key=self.openai_key)

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
        
        prompt = f"""You are a professional crypto trader with 15+ years experience. Follow the 8-STEP ENHANCED DECISION FRAMEWORK internally to analyze the data, but provide only the final CONCISE trading outlook.

MARKET DATA HIERARCHY ({data_points_used}/54 indicators):
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
• BTC Support/Resistance: ${f"{btc_data.get('support'):,}" if btc_data.get('support') else 'N/A'} / ${f"{btc_data.get('resistance'):,}" if btc_data.get('resistance') else 'N/A'} (OVERRIDDEN by liquidation zones if present)
• ETH Support/Resistance: ${f"{eth_data.get('support'):,}" if eth_data.get('support') else 'N/A'} / ${f"{eth_data.get('resistance'):,}" if eth_data.get('resistance') else 'N/A'} (OVERRIDDEN by liquidation zones if present)

🔧 ENHANCED TECHNICAL PRECISION (Advanced Analysis):
- BTC Advanced: ATR: ${f"{btc_data.get('atr'):,.0f}" if btc_data.get('atr') else 'N/A'} ({f"{(btc_data.get('atr', 0) / (btc_data.get('price') or 1)) * 100:.1f}" if btc_data.get('atr') and btc_data.get('price') else 'N/A'}%) | SMA7/14/50: ${f"{btc_data.get('sma7'):,.0f}" if btc_data.get('sma7') else 'N/A'}/${f"{btc_data.get('sma14'):,.0f}" if btc_data.get('sma14') else 'N/A'}/${f"{btc_data.get('sma50'):,.0f}" if btc_data.get('sma50') else 'N/A'}
- BTC Dynamic Levels: Support: ${f"{self._calculate_dynamic_support(btc_data):,.0f}" if btc_data else 'N/A'} | Resistance: ${f"{self._calculate_dynamic_resistance(btc_data):,.0f}" if btc_data else 'N/A'} | Volume: {btc_data.get('volume_trend', 'N/A')}
- ETH Advanced: ATR: ${f"{eth_data.get('atr'):,.0f}" if eth_data.get('atr') else 'N/A'} ({f"{(eth_data.get('atr', 0) / (eth_data.get('price') or 1)) * 100:.1f}" if eth_data.get('atr') and eth_data.get('price') else 'N/A'}%) | SMA7/14/50: ${f"{eth_data.get('sma7'):,.0f}" if eth_data.get('sma7') else 'N/A'}/${f"{eth_data.get('sma14'):,.0f}" if eth_data.get('sma14') else 'N/A'}/${f"{eth_data.get('sma50'):,.0f}" if eth_data.get('sma50') else 'N/A'}
- ETH Dynamic Levels: Support: ${f"{self._calculate_dynamic_support(eth_data):,.0f}" if eth_data else 'N/A'} | Resistance: ${f"{self._calculate_dynamic_resistance(eth_data):,.0f}" if eth_data else 'N/A'} | Volume: {eth_data.get('volume_trend', 'N/A')}

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
- MEDIUM PRIORITY CONFLICTS: If Order Book vs Whale Movements contradict → Require 70%+ conviction on BOTH or reduce to NEUTRAL
- If Traditional TA conflicts with higher priorities → Ignore traditional signals completely
- CONFLICT RESOLUTION RULE: When in doubt, choose FLAT position over conflicted trade


STEP 1: Economic Event Override Check + Bond Market Check
- If Economic Calendar shows "AVOID_TRADING" OR high-impact event in next 24h → FORCE FLAT POSITION
- If 10Y Treasury > 4.5% → REDUCE RISK APPETITE (smaller positions, higher stop losses)
- If 10Y Treasury > 5.0% → CONSIDER FLAT POSITION (bonds competing with risk assets)
- If Volatility Regime = "EXTREME" → Reduce position size by regime multiplier regardless of setup quality

STEP 2: Liquidation Magnet Analysis (OVERRIDE TRADITIONAL S/R)
- Check if liquidation clusters exist within 5% of current price
- IF LIQUIDATION CLUSTERS FOUND: Use ONLY liquidation levels, ignore traditional S/R completely
- IF NO LIQUIDATION CLUSTERS: Use traditional S/R but flag as "WEAKER SIGNALS"
- Priority order: 1) Liquidation clusters, 2) Dynamic S/R (ATR-based), 3) Traditional S/R (last resort)
- MANDATORY: If liquidation pressure = "HIGH" → Liquidation targets become ONLY valid targets
- RULE: Never mix liquidation and traditional levels in same trade plan

STEP 3: Smart Money & Entry Timing Gate + Volume Confirmation
- Check Order Book imbalance: >70% = strong signal, 60-70% = moderate, <60% = weak
- Check Whale Movement signal: ACCUMULATING/DISTRIBUTING vs trade direction
- VOLUME GATE: Only execute if volume confirms price signal (no weak volume signals)
- EXECUTION GATE: Only execute if BOTH order book AND whale signals AND volume support trade direction
- RULE: Don't fight smart money flow OR weak volume

STEP 4: Technical Analysis WITH Historical Validation
- RSI, support/resistance (if not overridden by liquidations), trend direction
- BTC/ETH signals for directional bias
- HISTORICAL CHECK: Confirm signals align with multi-timeframe momentum
- WEEKLY/MONTHLY TREND: Only trade WITH long-term trend unless strong reversal signals
- RULE: Technical signals must pass historical momentum filter

STEP 5: Macro Trend Alignment Check
- Fear & Greed, BTC dominance, S&P 500/VIX for overall market bias
- Multi-source sentiment for crowd positioning
- RULE: Use for position sizing confidence, not trade direction

STEP 6: Sentiment Risk Assessment
- Check funding rates and long/short ratios for overcrowded trades
- High funding = crowded positioning = reversal risk
- RULE: Avoid trading in same direction as extreme crowd positioning

STEP 7: Enhanced Execution Planning
- Entry zones: Use liquidation clusters if present, else traditional S/R
- Stop loss: Place beyond next liquidation cluster or traditional S/R level
- Take profit: Target liquidation clusters as magnetic price targets
- MINIMUM 1:2 R/R, but adjust for liquidation cluster distances
- RULE: Liquidation-aware stop/target placement

STEP 8: Dynamic Risk Management & Position Sizing
- Normal market conditions = 100% position size (full intended trade)
- If Volatility Regime = "HIGH" or "EXTREME" → Reduce to 75% or 50%
- If Economic Calendar shows high risk → Reduce by 25% 
- If fighting Whale signals → Reduce by 25%
- If multiple risk factors present → Can reduce to minimum 25%
- If all signals align perfectly → Can use 100% even in elevated volatility
- POSITION SIZE REPRESENTS: Percentage of your intended trade size, NOT portfolio allocation
- OUTPUT: Present as 100%, 75%, 50%, or 25% based on risk assessment


CRITICAL DECISION TREE:
======================
1. Economic Events = FLAT? → If YES: Output "FLAT - Major events pending"
2. Extreme Volatility? → If YES: Reduce size by regime multiplier  
3. Near Liquidation Clusters? → If YES: Use clusters as primary targets, ignore traditional S/R
4. Order Book + Whales Aligned? → If NO: Lower confidence or avoid
5. Traditional signals confirm? → If YES: Execute with priority-based sizing
6. Risk management applied? → Always adjust for volatility regime and event risk

OUTPUT PRIORITY: Economic Events > Liquidation Targets > Entry Timing > Traditional TA

PRIORITY-INTEGRATED TIMEFRAME LOGIC:
- SUPER HIGH PRIORITY OVERRIDES: If Economic Events pending → Extend timeframe by 2x (wait for clarity)
- HIGH PRIORITY LIQUIDATION TARGETS: 2-6 hours (liquidations happen fast, use shorter timeframes)
- HIGH PRIORITY BOND MARKET MOVES: 12-48 hours (macro moves take time to develop)
- MEDIUM PRIORITY SMART MONEY: 4-12 hours (institutional flows develop over hours)
- LOW PRIORITY TRADITIONAL TA: 6-24 hours (standard technical patterns)
- VOLATILITY REGIME ADJUSTMENT: If "EXTREME" → Cut all timeframes by 50% (faster moves)
- CONFLICT RESOLUTION: If multiple timeframes suggested → Use the SHORTEST from highest priority signal
FINAL RULE: Priority level determines base timeframe, volatility regime adjusts duration

REQUIRED OUTPUT FORMAT (CONCISE ONLY):
=====================================

<b>━━━ 📊 EXECUTIVE SUMMARY ━━━</b>
- Fear & Greed: [value] ([sentiment])
- Position Size: [X]% (of intended trade size - 100% = full position, 50% = half position, etc.)
- Market Bias: [BULLISH/BEARISH/NEUTRAL]
- Primary Driver: [key factor driving direction]
- Risk Level: [High/Medium/Low] 
- Position Crowding: [BTC/ETH crowding assessment]

<b>━━━ 🎯 BTC EXECUTION PLAN - [BIAS] ━━━</b>
💰 Current: $[price]
⏱️ Timeframe: [X-Yh] ([breakout/swing/trend/reversal] setup)
📍 <b>Entry: $[low]-$[high]</b>
🛑 <b>SL: $[price] ([X]%)</b>
🎯 <b>TP 1: $[price] ([X]%)</b> 
🎯 <b>TP 2: $[price] ([X]%)</b>
⚖️ Risk/Reward: [X:X]
📊 Confidence: [XX]% ([key reasoning])

<b>━━━ 🎯 ETH EXECUTION PLAN - [BIAS] ━━━</b>
💰 Current: $[price]
⏱️ Timeframe: [X-Yh] ([breakout/swing/trend/reversal] setup)
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

POSITION SIZE INSTRUCTION:
Position Size represents the recommended position size for this trade setup (not portfolio allocation).
- Standard position: 100% (full position)
- Reduced risk: 75% (moderate position) 
- High risk conditions: 50% (conservative position)
- Extreme risk: 25% (minimal position)
Present in Executive Summary as percentage of intended position size.

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
                return "INSUFFICIENT_DATA"
            
            # Safely extract weekly data
            btc_close = btc_weekly.get('close', [])
            btc_sma200 = btc_weekly.get('sma200', [])
            eth_close = eth_weekly.get('close', [])
            eth_sma200 = eth_weekly.get('sma200', [])
            
            # Check if we have valid list data
            if not all([
                isinstance(btc_close, list) and len(btc_close) > 0,
                isinstance(btc_sma200, list) and len(btc_sma200) > 0,
                isinstance(eth_close, list) and len(eth_close) > 0,
                isinstance(eth_sma200, list) and len(eth_sma200) > 0
            ]):
                return "INSUFFICIENT_DATA"
            
            # Safely convert to float
            try:
                btc_current = float(btc_close[-1]) if btc_close[-1] is not None else 0
                btc_sma = float(btc_sma200[-1]) if btc_sma200[-1] is not None else 0
                eth_current = float(eth_close[-1]) if eth_close[-1] is not None else 0
                eth_sma = float(eth_sma200[-1]) if eth_sma200[-1] is not None else 0
            except (ValueError, TypeError):
                return "INVALID_PRICE_DATA"
            
            if btc_sma == 0 or eth_sma == 0:
                return "INVALID_SMA_DATA"
            
            btc_trend = "BULL" if btc_current > btc_sma else "BEAR"
            eth_trend = "BULL" if eth_current > eth_sma else "BEAR"
            
            if btc_trend == eth_trend:
                return f"ALIGNED_{btc_trend}ISH"
            else:
                return "DIVERGENT"
                
        except (IndexError, TypeError, KeyError, AttributeError):
            return "UNKNOWN"

    def _find_historical_resistance_levels(self, historical):
        """Find confluence of historical resistance levels"""
        try:
            btc_daily = historical.get('BTC', {}).get('1d', {})
            if not btc_daily or 'high' not in btc_daily or 'close' not in btc_daily:
                return "NO_DATA"
            
            # Get data safely
            highs = btc_daily.get('high', [])
            closes = btc_daily.get('close', [])
            
            # Validate data
            if not isinstance(highs, list) or not isinstance(closes, list):
                return "INVALID_DATA_TYPE"
            
            if len(highs) < 50 or len(closes) < 1:
                return "INSUFFICIENT_DATA"
            
            # Get recent highs (last 50 days)
            recent_highs = highs[-50:]
            
            try:
                current_price = float(closes[-1]) if closes[-1] is not None else 0
            except (ValueError, TypeError):
                return "INVALID_PRICE"
            
            if current_price <= 0:
                return "INVALID_PRICE"
            
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
                
        except (IndexError, TypeError, KeyError, AttributeError):
            return "UNKNOWN"

    def _check_momentum_alignment(self, historical):
        """Check if momentum aligns across timeframes"""
        try:
            btc_daily = historical.get('BTC', {}).get('1d', {})
            btc_weekly = historical.get('BTC', {}).get('1wk', {})
            
            if not btc_daily or not btc_weekly:
                return "INSUFFICIENT_DATA"
            
            # Check MACD alignment
            daily_macd = btc_daily.get('macd_histogram', [])
            weekly_macd = btc_weekly.get('macd_histogram', [])
            
            # Validate MACD data
            if not isinstance(daily_macd, list) or not isinstance(weekly_macd, list):
                return "INVALID_MACD_TYPE"
            
            if len(daily_macd) == 0 or len(weekly_macd) == 0:
                return "NO_MACD_DATA"
            
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
                return "DIVERGENT_MOMENTUM"
                
        except (IndexError, TypeError, KeyError, AttributeError):
            return "UNKNOWN"

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

    def _calculate_dynamic_support(self, coin_data):
        """Calculate dynamic support using ATR and moving averages"""
        if not coin_data:
            return 0
        
        try:
            price = float(coin_data.get('price', 0))
            atr = float(coin_data.get('atr', 0))
            sma14 = float(coin_data.get('sma14', price))
            static_support = float(coin_data.get('support', price * 0.95))
            
            if price == 0:
                return 0
            
            # Combine static support with dynamic ATR-based support
            atr_support = price - (1.5 * atr) if atr > 0 else price * 0.98
            sma_support = sma14 * 0.98
            
            return max(static_support, atr_support, sma_support)
        except (ValueError, TypeError):
            return 0

    def _calculate_dynamic_resistance(self, coin_data):
        """Calculate dynamic resistance using ATR and moving averages"""
        if not coin_data:
            return 0
        
        try:
            price = float(coin_data.get('price', 0))
            atr = float(coin_data.get('atr', 0))
            sma14 = float(coin_data.get('sma14', price))
            static_resistance = float(coin_data.get('resistance', price * 1.05))
            
            if price == 0:
                return 0
            
            # Combine static resistance with dynamic ATR-based resistance
            atr_resistance = price + (1.5 * atr) if atr > 0 else price * 1.02
            sma_resistance = sma14 * 1.02
            
            return min(static_resistance, atr_resistance, sma_resistance)
        except (ValueError, TypeError):
            return 0

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

    def get_ai_prediction(self, market_data):
        """Get AI prediction using comprehensive market data"""
        try:
            print("[INFO] Generating AI prediction with comprehensive market analysis...")
            
            # Create comprehensive prompt
            prompt = self.create_comprehensive_prompt(market_data)
            
            # Make OpenAI API call
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a professional cryptocurrency trader and market analyst with 15+ years of experience. Provide detailed, actionable trading analysis."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=1500,
                temperature=0.7
            )
            
            ai_prediction = response.choices[0].message.content
            
            print("[INFO] ✅ AI prediction generated successfully")
            
            return {
                "prediction": ai_prediction,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "gpt-4",
                "prompt_length": len(prompt),
                "response_length": len(ai_prediction),
                "data_points_used": self._count_available_data(market_data)
            }
            
        except Exception as e:
            print(f"[ERROR] AI prediction failed: {e}")
            return {
                "prediction": f"AI prediction unavailable - Error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "gpt-4",
                "error": str(e),
                "data_points_used": 0
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

    def send_ai_telegram(self, ai_result, market_data, test_mode=False):
        """Send AI prediction via Telegram"""
        try:
            message = self.format_ai_telegram_message(ai_result, market_data, test_mode)
            
            # Determine which bot config to use (ONLY difference in test mode)
            if test_mode:
                bot_token = self.config["telegram"]["test"]["bot_token"]
                chat_id = self.config["telegram"]["test"]["chat_id"]
                print(f"[INFO] Using TEST Telegram configuration")
            else:
                bot_token = self.config["telegram"]["bot_token"] 
                chat_id = self.config["telegram"]["chat_id"]
                print(f"[INFO] Using PRODUCTION Telegram configuration")
            
            if not bot_token or not chat_id:
                mode_name = "test" if test_mode else "production"
                print(f"[ERROR] Telegram configuration missing for {mode_name} mode")
                print(f"[ERROR] Bot token: {'SET' if bot_token else 'NOT SET'}")
                print(f"[ERROR] Chat ID: {'SET' if chat_id else 'NOT SET'}")
                return False
            
            # Send message directly using the specific bot configuration  
            from telegram_utils import TelegramBot
            bot = TelegramBot(bot_token=bot_token, chat_id=chat_id)
            # Don't add prefix here since it's already handled in format_ai_telegram_message
            result = bot.send_message(message)
            
            if result:
                print(f"[INFO] ✅ AI prediction sent via Telegram ({'test' if test_mode else 'production'})")
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
                "model": ai_result.get("model", "gpt-4"),
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
            
            # Simple file backup for non-test mode
            if not test_mode:
                filename = f"ai_prediction_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(prediction_data, f, indent=2, default=str)
                print(f"[INFO] ✅ AI prediction saved to {filename}")
            else:
                print(f"[INFO] 🧪 Test mode - no file created")
            
            return prediction_data
            
        except Exception as e:
            print(f"[ERROR] Saving AI prediction: {e}")
            return None

    def run_ai_prediction(self, market_data, test_mode=False, save_results=True, send_telegram=True):
        """Complete AI prediction workflow"""
        try:
            mode_text = "🧪 TEST MODE" if test_mode else "🚀 PRODUCTION MODE"
            print("\n" + "="*50)
            print(f"🤖 STARTING AI PREDICTION SYSTEM - {mode_text}")
            print("="*50)
            
            # Generate AI prediction
            ai_result = self.get_ai_prediction(market_data)
            
            if "error" in ai_result:
                print(f"[CRITICAL] AI prediction failed: {ai_result['error']}")
                return None
            
            # Save prediction if requested
            if save_results:
                saved_data = self.save_ai_prediction(ai_result, market_data, test_mode)
                if saved_data:
                    mode_text = "test file" if test_mode else "database and file"
                    print(f"[INFO] ✅ AI prediction saved to {mode_text}")
            
            # Send Telegram message if requested
            if send_telegram and self.config["telegram"]["enabled"]:
                telegram_success = self.send_ai_telegram(ai_result, market_data, test_mode)
                if not telegram_success:
                    print("[WARN] Telegram sending failed")
            
            print("\n" + "="*50)
            print(f"🤖 AI PREDICTION SYSTEM COMPLETE - {mode_text}")
            print("="*50)
            
            return ai_result
            
        except Exception as e:
            print(f"[CRITICAL] AI prediction workflow failed: {e}")
            return None

    async def generate_prediction(self, market_data, test_mode=False):
        """Generate AI prediction (async wrapper for compatibility)"""
        try:
            return self.run_ai_prediction(market_data, test_mode, save_results=True, send_telegram=True)
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