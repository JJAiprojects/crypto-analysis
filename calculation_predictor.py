#!/usr/bin/env python3

import os
import json
import math
from datetime import datetime, timezone
from telegram_utils import send_telegram_message

class CalculationPredictor:
    def __init__(self, config):
        self.config = config

    def analyze_market_conditions(self, market_data):
        """
        Comprehensive calculation-based market analysis using the same data points as AI
        
        This function uses weighted scoring of technical indicators, macroeconomic data,
        and market sentiment to generate trading signals with confidence levels.
        """
        try:
            print("[INFO] Starting calculation-based market analysis...")
            
            # Extract market data safely
            crypto = market_data.get("crypto", {})
            technicals = market_data.get("technical_indicators", {})
            futures = market_data.get("futures", {})
            fear_greed = market_data.get("fear_greed", {})
            
            # Macroeconomic data
            m2_data = market_data.get("m2_supply", {})
            inflation_data = market_data.get("inflation", {})
            rates_data = market_data.get("interest_rates", {})
            stock_indices = market_data.get("stock_indices", {})
            commodities = market_data.get("commodities", {})
            social_metrics = market_data.get("social_metrics", {})
            
            # Market structure
            btc_dominance = market_data.get("btc_dominance", 50)
            market_cap_data = market_data.get("market_cap", (0, 0))
            volumes = market_data.get("volumes", {})
            
            # BTC and ETH data
            btc_data = technicals.get("BTC", {})
            eth_data = technicals.get("ETH", {})
            btc_futures = futures.get("BTC", {})
            eth_futures = futures.get("ETH", {})
            
            # Initialize sentiment scoring
            sentiment_score = 0
            sentiment_factors = []
            confidence_multiplier = 1.0
            
            # 1. FEAR & GREED INDEX (20% weight)
            fg_index = fear_greed.get("index", 50)
            if fg_index:
                fg_score = (fg_index - 50) / 50  # Normalize to -1 to 1
                sentiment_score += fg_score * 0.20
                sentiment_factors.append(f"Fear&Greed: {fg_index} ({fg_score:+.2f})")
                confidence_multiplier *= 1.1 if abs(fg_score) > 0.3 else 0.9
            
            # 2. BTC DOMINANCE (15% weight)
            if btc_dominance:
                # BTC dominance above 50% = alt season ending, below 45% = alt season
                dom_score = (btc_dominance - 47.5) / 10  # Normalize around 47.5%
                dom_weight = max(-0.15, min(0.15, dom_score * 0.15))
                sentiment_score += dom_weight
                sentiment_factors.append(f"BTC Dom: {btc_dominance:.1f}% ({dom_weight:+.3f})")
            
            # 3. STOCK MARKET CORRELATION (15% weight)
            stock_sentiment = 0
            sp500_change = stock_indices.get("sp500_change", 0)
            nasdaq_change = stock_indices.get("nasdaq_change", 0) 
            vix = stock_indices.get("vix", 20)
            
            if sp500_change:
                stock_sentiment += sp500_change / 5  # 5% move = 1.0 score
            if nasdaq_change:
                stock_sentiment += nasdaq_change / 5
            if vix:
                # VIX below 20 = bullish, above 30 = bearish
                vix_score = -(vix - 25) / 15  # Normalize around 25
                stock_sentiment += vix_score
                
            stock_weight = max(-0.15, min(0.15, stock_sentiment * 0.05))
            sentiment_score += stock_weight
            sentiment_factors.append(f"Stocks: S&P{sp500_change:+.1f}% NASDAQ{nasdaq_change:+.1f}% VIX{vix:.1f} ({stock_weight:+.3f})")
            
            # 4. FUNDING RATES (10% weight)
            btc_funding = btc_futures.get("funding_rate", 0)
            eth_funding = eth_futures.get("funding_rate", 0)
            if btc_funding and eth_funding:
                avg_funding = (btc_funding + eth_funding) / 2
                # Negative funding = bullish (shorts pay longs)
                funding_score = -avg_funding * 20  # 0.05% funding = 1.0 score
                funding_weight = max(-0.10, min(0.10, funding_score * 0.10))
                sentiment_score += funding_weight
                sentiment_factors.append(f"Funding: {avg_funding:.3f}% ({funding_weight:+.3f})")
            
            # 5. LONG/SHORT RATIOS (5% weight)
            btc_ls_ratio = btc_futures.get("long_ratio", 0.5) / (btc_futures.get("short_ratio", 0.5) + 1e-6)
            eth_ls_ratio = eth_futures.get("long_ratio", 0.5) / (eth_futures.get("short_ratio", 0.5) + 1e-6)
            if btc_ls_ratio and eth_ls_ratio:
                avg_ls_ratio = (btc_ls_ratio + eth_ls_ratio) / 2
                # Ratio > 1.2 = too bullish (contrarian bearish), < 0.8 = too bearish (contrarian bullish)
                ratio_score = 0
                if avg_ls_ratio > 1.2:
                    ratio_score = -(avg_ls_ratio - 1.2) * 2  # Contrarian
                elif avg_ls_ratio < 0.8:
                    ratio_score = (0.8 - avg_ls_ratio) * 2  # Contrarian
                    
                ratio_weight = max(-0.05, min(0.05, ratio_score * 0.05))
                sentiment_score += ratio_weight
                sentiment_factors.append(f"L/S Ratio: {avg_ls_ratio:.2f} ({ratio_weight:+.3f})")
            
            # 6. TECHNICAL TREND ALIGNMENT (25% weight)
            btc_trend = btc_data.get("trend", "neutral")
            eth_trend = eth_data.get("trend", "neutral")
            btc_rsi = btc_data.get("rsi14", 50)
            eth_rsi = eth_data.get("rsi14", 50)
            
            trend_score = 0
            
            # BTC trend analysis
            if btc_trend == "bullish":
                trend_score += 0.15
                if btc_rsi > 70:
                    trend_score -= 0.05  # Overbought penalty
                elif btc_rsi < 30:
                    trend_score += 0.05  # Oversold bonus
            elif btc_trend == "bullish_weak":
                trend_score += 0.08
            elif btc_trend == "bearish":
                trend_score -= 0.15
                if btc_rsi < 30:
                    trend_score += 0.05  # Oversold contrarian
                elif btc_rsi > 70:
                    trend_score -= 0.05  # Still overbought
            elif btc_trend == "bearish_weak":
                trend_score -= 0.08
            
            # ETH trend analysis
            if eth_trend == "bullish":
                trend_score += 0.10
                if eth_rsi > 70:
                    trend_score -= 0.03
                elif eth_rsi < 30:
                    trend_score += 0.03
            elif eth_trend == "bullish_weak":
                trend_score += 0.05
            elif eth_trend == "bearish":
                trend_score -= 0.10
                if eth_rsi < 30:
                    trend_score += 0.03
                elif eth_rsi > 70:
                    trend_score -= 0.03
            elif eth_trend == "bearish_weak":
                trend_score -= 0.05
            
            sentiment_score += trend_score
            sentiment_factors.append(f"Trends: BTC({btc_trend}) ETH({eth_trend}) ({trend_score:+.3f})")
            
            # 7. MACROECONOMIC FACTORS (10% weight)
            macro_score = 0
            
            # Interest rates impact
            fed_rate = rates_data.get("fed_rate", 5.0)
            if fed_rate:
                # Higher rates = bearish for risk assets
                rate_score = -(fed_rate - 4.0) / 5.0  # Normalize around 4%
                macro_score += rate_score * 0.03
                
            # Inflation impact
            inflation_rate = inflation_data.get("inflation_rate", 3.0)
            if inflation_rate:
                # Moderate inflation (2-4%) = neutral, high inflation = bearish, deflation = bearish
                if 2.0 <= inflation_rate <= 4.0:
                    inflation_score = 0.02
                elif inflation_rate > 6.0:
                    inflation_score = -0.04
                elif inflation_rate < 1.0:
                    inflation_score = -0.03
                else:
                    inflation_score = 0
                macro_score += inflation_score
            
            # Commodities (Gold/Oil correlation)
            gold_price = commodities.get("gold", 2000)
            oil_price = commodities.get("crude_oil", 80)
            if gold_price and oil_price:
                # Rising gold = risk-off, rising oil = inflation concerns
                if gold_price > 2100:  # High gold
                    macro_score -= 0.02
                elif gold_price < 1900:  # Low gold
                    macro_score += 0.02
                    
                if oil_price > 90:  # High oil
                    macro_score -= 0.01
                elif oil_price < 70:  # Low oil
                    macro_score += 0.01
            
            macro_weight = max(-0.10, min(0.10, macro_score))
            sentiment_score += macro_weight
            sentiment_factors.append(f"Macro: Fed{fed_rate:.1f}% Inf{inflation_rate:.1f}% ({macro_weight:+.3f})")
            
            # 8. VOLUME AND MOMENTUM (10% weight)
            volume_score = 0
            btc_volume_trend = btc_data.get("volume_trend", "stable")
            eth_volume_trend = eth_data.get("volume_trend", "stable")
            
            if btc_volume_trend == "increasing":
                volume_score += 0.05
            elif btc_volume_trend == "decreasing":
                volume_score -= 0.03
                
            if eth_volume_trend == "increasing":
                volume_score += 0.03
            elif eth_volume_trend == "decreasing":
                volume_score -= 0.02
                
            # Market cap change
            market_cap_change = market_cap_data[1] if len(market_cap_data) > 1 and market_cap_data[1] else 0
            if market_cap_change:
                cap_score = market_cap_change / 10  # 10% change = 1.0 score
                volume_score += cap_score * 0.02
            
            volume_weight = max(-0.10, min(0.10, volume_score))
            sentiment_score += volume_weight
            sentiment_factors.append(f"Volume: BTC({btc_volume_trend}) ETH({eth_volume_trend}) MCap{market_cap_change:+.1f}% ({volume_weight:+.3f})")
            
            # 9. SOCIAL SENTIMENT & DEVELOPMENT ACTIVITY (5% weight)
            social_score = 0
            social_data = market_data.get("social_metrics", {})
            
            # GitHub activity indicates development health
            btc_commits = social_data.get("btc_recent_commits", 0)
            eth_commits = social_data.get("eth_recent_commits", 0)
            btc_stars = social_data.get("btc_github_stars", 0)
            eth_stars = social_data.get("eth_github_stars", 0)
            
            if btc_commits and eth_commits:
                # High development activity = bullish long-term
                commit_activity = (btc_commits + eth_commits) / 60  # Normalize around 30 commits each
                social_score += min(0.02, commit_activity * 0.02)
            
            if btc_stars and eth_stars:
                # GitHub stars growth indicates community interest
                total_stars = btc_stars + eth_stars
                if total_stars > 130000:  # High community interest
                    social_score += 0.01
                elif total_stars < 100000:  # Declining interest
                    social_score -= 0.005
            
            # Forum activity (if available)
            forum_posts = social_data.get("forum_posts", 0)
            forum_topics = social_data.get("forum_topics", 0)
            if forum_posts and forum_topics:
                # High forum activity can indicate retail FOMO (contrarian indicator)
                forum_activity = (forum_posts + forum_topics) / 1000
                if forum_activity > 2.0:  # Very high activity = retail FOMO
                    social_score -= 0.015  # Contrarian bearish
                elif forum_activity > 1.0:  # Moderate activity = healthy interest
                    social_score += 0.01
            
            social_weight = max(-0.05, min(0.05, social_score))
            sentiment_score += social_score
            # Safe string formatting for social metrics
            try:
                total_commits = btc_commits + eth_commits
                total_stars_k = max(0, (btc_stars + eth_stars) // 1000)  # Ensure non-negative
                sentiment_factors.append(f"Social: Dev{total_commits} Stars{total_stars_k}k ({social_weight:+.3f})")
            except Exception as social_error:
                print(f"[WARN] Social metrics formatting error: {social_error}")
                sentiment_factors.append(f"Social: DevN/A StarsN/A ({social_weight:+.3f})")
            
            # 10. ENHANCED COMMODITIES ANALYSIS (5% weight)
            enhanced_macro_score = 0
            
            # Silver analysis (risk-on/risk-off)
            silver_price = commodities.get("silver", 30)
            if silver_price:
                # Silver above $35 = risk-on, below $25 = risk-off
                if silver_price > 35:
                    enhanced_macro_score += 0.015  # Risk-on bullish for crypto
                elif silver_price < 25:
                    enhanced_macro_score -= 0.015  # Risk-off bearish
            
            # Natural gas (inflation/energy cost indicator)
            nat_gas_price = commodities.get("natural_gas", 3.5)
            if nat_gas_price:
                # High energy costs = bearish for risk assets
                if nat_gas_price > 5.0:
                    enhanced_macro_score -= 0.01
                elif nat_gas_price < 3.0:
                    enhanced_macro_score += 0.005
            
            # M2 Money Supply (liquidity indicator) - SAFE CALCULATION
            m2_data = market_data.get("m2_supply", {})
            m2_supply = m2_data.get("m2_supply", 0)
            if m2_supply and m2_supply > 0:
                # Rising M2 = more liquidity = bullish for risk assets
                # M2 above $22T = high liquidity environment
                if m2_supply > 22000:  # $22T+
                    enhanced_macro_score += 0.02
                elif m2_supply < 20000:  # Below $20T
                    enhanced_macro_score -= 0.01
            
            enhanced_macro_weight = max(-0.05, min(0.05, enhanced_macro_score))
            sentiment_score += enhanced_macro_weight
            
            # Safe M2 formatting
            try:
                if m2_supply and m2_supply > 0:
                    m2_display = f"M2${(m2_supply/1000):.0f}T"
                else:
                    m2_display = "M2:N/A"
                sentiment_factors.append(f"Enhanced Macro: Silver${silver_price:.0f} NatGas${nat_gas_price:.1f} {m2_display} ({enhanced_macro_weight:+.3f})")
            except Exception as m2_error:
                print(f"[WARN] M2 formatting error: {m2_error}")
                sentiment_factors.append(f"Enhanced Macro: Silver${silver_price:.0f} NatGas${nat_gas_price:.1f} M2:ERR ({enhanced_macro_weight:+.3f})")
            
            # 11. HISTORICAL PATTERN ANALYSIS (5% weight)
            historical_score = 0
            historical_data = market_data.get("historical_data", {})
            
            btc_historical = historical_data.get("BTC", {})
            eth_historical = historical_data.get("ETH", {})
            
            if btc_historical and eth_historical:
                # Analyze multiple timeframes for pattern confirmation
                pattern_strength = 0
                
                # Check for trend consistency across timeframes
                for timeframe in ['1h', '4h', '1d', '1wk']:
                    btc_tf_data = btc_historical.get(timeframe, [])
                    eth_tf_data = eth_historical.get(timeframe, [])
                    
                    # Handle both dict and list formats
                    if isinstance(btc_tf_data, dict):
                        # Extract close prices from historical data structure
                        btc_tf_data = btc_tf_data.get('close', []) if btc_tf_data else []
                    if isinstance(eth_tf_data, dict):
                        # Extract close prices from historical data structure
                        eth_tf_data = eth_tf_data.get('close', []) if eth_tf_data else []
                    
                    # Flatten nested lists (each price is wrapped in a single-item list)
                    if btc_tf_data and isinstance(btc_tf_data[0], list):
                        btc_tf_data = [item[0] if isinstance(item, list) and len(item) > 0 else item for item in btc_tf_data]
                    
                    if eth_tf_data and isinstance(eth_tf_data[0], list):
                        eth_tf_data = [item[0] if isinstance(item, list) and len(item) > 0 else item for item in eth_tf_data]
                    
                    # Ensure we have numeric list data
                    if isinstance(btc_tf_data, list) and isinstance(eth_tf_data, list):
                        # Filter out non-numeric values with improved logic
                        try:
                            # More robust numeric filtering
                            btc_filtered = []
                            for x in btc_tf_data:
                                try:
                                    val = float(x)
                                    if not (math.isnan(val) or math.isinf(val)):
                                        btc_filtered.append(val)
                                except (ValueError, TypeError):
                                    continue
                            btc_tf_data = btc_filtered
                            
                            eth_filtered = []
                            for x in eth_tf_data:
                                try:
                                    val = float(x)
                                    if not (math.isnan(val) or math.isinf(val)):
                                        eth_filtered.append(val)
                                except (ValueError, TypeError):
                                    continue
                            eth_tf_data = eth_filtered
                            
                        except (ValueError, TypeError) as filter_error:
                            print(f"[WARN] Filtering error for {timeframe}: {filter_error}")
                            btc_tf_data = []
                            eth_tf_data = []
                        
                        if len(btc_tf_data) > 10 and len(eth_tf_data) > 10:
                            # Simple momentum check: current vs 10 periods ago
                            try:
                                btc_current = btc_tf_data[-1] if btc_tf_data else 0
                                btc_past = btc_tf_data[-10] if len(btc_tf_data) >= 10 else btc_current
                                eth_current = eth_tf_data[-1] if eth_tf_data else 0
                                eth_past = eth_tf_data[-10] if len(eth_tf_data) >= 10 else eth_current
                                
                                if btc_past > 0 and eth_past > 0:
                                    btc_momentum = (btc_current - btc_past) / btc_past
                                    eth_momentum = (eth_current - eth_past) / eth_past
                                    
                                    # Weight shorter timeframes less
                                    weight_multiplier = {'1h': 0.1, '4h': 0.3, '1d': 0.8, '1wk': 1.0}.get(timeframe, 0.5)
                                    
                                    if btc_momentum > 0 and eth_momentum > 0:  # Both positive
                                        pattern_strength += 0.01 * weight_multiplier
                                    elif btc_momentum < 0 and eth_momentum < 0:  # Both negative
                                        pattern_strength -= 0.01 * weight_multiplier
                            except (ZeroDivisionError, TypeError, IndexError) as hist_error:
                                print(f"[WARN] Historical analysis error for {timeframe}: {hist_error}")
                                continue
                        else:
                            print(f"[WARN] Insufficient historical data for {timeframe}: BTC={len(btc_tf_data)}, ETH={len(eth_tf_data)}")
                    else:
                        print(f"[WARN] Historical data for {timeframe} is not in expected format after conversion")
                
                historical_score = pattern_strength
            
            historical_weight = max(-0.05, min(0.05, historical_score))
            sentiment_score += historical_score
            sentiment_factors.append(f"Historical: Pattern{len(btc_historical)} TF convergence ({historical_weight:+.3f})")
            
            # 12. ADDITIONAL STOCK INDICES (Enhanced from 3 to 4 indices)
            # Already covered: S&P 500, NASDAQ, VIX
            # Add Dow Jones analysis
            dow_change = stock_indices.get("dow_jones_change", 0)
            if dow_change:
                dow_score = dow_change / 8  # 8% move = 1.0 score (less volatile than NASDAQ)
                dow_weight = max(-0.03, min(0.03, dow_score * 0.03))
                sentiment_score += dow_weight
                # Update existing stock factors message
                for i, factor in enumerate(sentiment_factors):
                    if factor.startswith("Stocks:"):
                        sentiment_factors[i] = f"Stocks: S&P{sp500_change:+.1f}% NASDAQ{nasdaq_change:+.1f}% DOW{dow_change:+.1f}% VIX{vix:.1f} ({stock_weight+dow_weight:+.3f})"
                        break
            
            # Calculate final confidence
            base_confidence = abs(sentiment_score) * 100 * confidence_multiplier
            confidence = min(95, max(15, base_confidence))
            
            # Determine market bias
            if sentiment_score > 0.25:
                market_bias = "BULLISH"
                scenario_confidence = "high"
            elif sentiment_score > 0.10:
                market_bias = "BULLISH"
                scenario_confidence = "medium"
            elif sentiment_score < -0.25:
                market_bias = "BEARISH"
                scenario_confidence = "high"
            elif sentiment_score < -0.10:
                market_bias = "BEARISH"
                scenario_confidence = "medium"
            else:
                market_bias = "NEUTRAL"
                scenario_confidence = "low"
            
            # Calculate bullish/bearish percentages
            normalized_score = max(-1, min(1, sentiment_score * 2))  # Amplify for clearer percentages
            bullish_pct = ((normalized_score + 1) / 2) * 100
            bearish_pct = 100 - bullish_pct
            
            # Determine strongest signal
            factor_weights = {
                "Technical Trends": 0.25,
                "Fear & Greed": 0.20,
                "Stock Correlation": 0.15,
                "BTC Dominance": 0.15,
                "Futures Sentiment": 0.15,
                "Macro Environment": 0.10
            }
            strongest_signal = max(factor_weights.keys(), key=lambda k: factor_weights[k])
            
            # Volatility assessment
            btc_volatility = btc_data.get("volatility", "medium")
            eth_volatility = eth_data.get("volatility", "medium")
            vix_level = stock_indices.get("vix", 20)
            
            if btc_volatility == "high" or eth_volatility == "high" or vix_level > 25:
                volatility = "High"
            elif btc_volatility == "low" and eth_volatility == "low" and vix_level < 15:
                volatility = "Low"
            else:
                volatility = "Medium"
            
            print(f"[INFO] ✅ Calculation analysis complete - {market_bias} ({confidence:.0f}%)")
            
            return {
                'market_bias': market_bias,
                'scenario_confidence': scenario_confidence,
                'confidence': confidence,
                'sentiment_score': sentiment_score,
                'bullish_percentage': bullish_pct,
                'bearish_percentage': bearish_pct,
                'sentiment_factors': sentiment_factors,
                'strongest_signal': strongest_signal,
                'volatility': volatility,
                'data_points_used': self._count_data_points_used(market_data)
            }
            
        except Exception as e:
            print(f"[ERROR] Market conditions analysis failed: {e}")
            print(f"[DEBUG] Error type: {type(e).__name__}")
            import traceback
            print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
            return {
                'market_bias': 'NEUTRAL',
                'scenario_confidence': 'low',
                'confidence': 50,
                'sentiment_score': 0,
                'bullish_percentage': 50,
                'bearish_percentage': 50,
                'sentiment_factors': [f'Error in calculation: {str(e)}'],
                'strongest_signal': 'Unknown',
                'volatility': 'Medium',
                'data_points_used': self._count_data_points_used(market_data)
            }

    def calculate_trading_levels(self, market_data, market_analysis):
        """Calculate specific trading levels for BTC and ETH"""
        try:
            technicals = market_data.get("technical_indicators", {})
            btc_data = technicals.get("BTC", {})
            eth_data = technicals.get("ETH", {})
            
            trading_plans = {}
            
            # BTC Trading Plan - Ensure we have BTC price
            btc_price = btc_data.get("price", 0)
            if btc_price == 0:
                # Fallback to crypto data
                btc_price = market_data.get("crypto", {}).get("btc", 0)
                
            if btc_price == 0:
                print("[ERROR] BTC price not available - cannot calculate trading levels")
                return {"BTC": {}, "ETH": {}}
            
            btc_support = btc_data.get("support", btc_price * 0.95)
            btc_resistance = btc_data.get("resistance", btc_price * 1.05)
            btc_atr = btc_data.get("atr", btc_price * 0.02)
            btc_signal = btc_data.get("signal", "NEUTRAL")
            btc_rsi = btc_data.get("rsi14", 50)
            
            # Determine entry strategy based on market bias and technical signals
            market_bias = market_analysis.get("market_bias", "NEUTRAL")
            confidence = market_analysis.get("confidence", 50)
            
            # Risk management parameters
            leverage = 13.5  # Standard futures leverage
            risk_per_trade = 0.03  # 3% account risk
            
            if market_bias == "BULLISH" and btc_signal in ["BUY", "STRONG BUY"]:
                # Bullish scenario
                entry_low = max(btc_support, btc_price * 0.995)  # Tight entry near current price
                entry_high = btc_price * 1.002
                
                # Stop loss below support with ATR buffer
                stop_loss = min(btc_support * 0.998, btc_price - 1.5 * btc_atr)
                
                # Target levels based on resistance and confidence
                risk = abs(btc_price - stop_loss)
                if confidence > 70:
                    rrr = 3.0  # High confidence = higher targets
                elif confidence > 50:
                    rrr = 2.0
                else:
                    rrr = 1.5
                
                target1 = min(btc_resistance * 0.999, btc_price + rrr * risk)
                target2 = min(btc_resistance * 1.005, btc_price + (rrr + 1) * risk)
                
                plan_bias = "BULLISH"
                
            elif market_bias == "BEARISH" and btc_signal in ["SELL", "STRONG SELL"]:
                # Bearish scenario
                entry_high = min(btc_resistance, btc_price * 1.005)
                entry_low = btc_price * 0.998
                
                # Stop loss above resistance with ATR buffer
                stop_loss = max(btc_resistance * 1.002, btc_price + 1.5 * btc_atr)
                
                # Target levels
                risk = abs(stop_loss - btc_price)
                if confidence > 70:
                    rrr = 3.0
                elif confidence > 50:
                    rrr = 2.0
                else:
                    rrr = 1.5
                
                target1 = max(btc_support * 1.001, btc_price - rrr * risk)
                target2 = max(btc_support * 0.995, btc_price - (rrr + 1) * risk)
                
                plan_bias = "BEARISH"
                
            else:
                # Neutral/Range-bound scenario
                entry_low = btc_price * 0.99
                entry_high = btc_price * 1.01
                stop_loss = btc_price * (0.98 if market_bias != "BEARISH" else 1.02)
                target1 = btc_price * (1.02 if market_bias != "BEARISH" else 0.98)
                target2 = btc_price * (1.04 if market_bias != "BEARISH" else 0.96)
                plan_bias = "NEUTRAL"
            
            # Calculate percentages and ratios
            entry_price = (entry_low + entry_high) / 2
            tp1_pct = ((target1 - entry_price) / entry_price) * 100
            tp2_pct = ((target2 - entry_price) / entry_price) * 100
            sl_pct = ((stop_loss - entry_price) / entry_price) * 100
            
            if abs(stop_loss - entry_price) > 0:
                rrr1 = abs(target1 - entry_price) / abs(stop_loss - entry_price)
                rrr2 = abs(target2 - entry_price) / abs(stop_loss - entry_price)
            else:
                rrr1 = rrr2 = 1.0
            
            # Position confidence based on multiple factors
            position_confidence = min(85, max(25, 
                confidence * 0.6 +  # Market confidence
                (30 if btc_rsi < 70 and btc_rsi > 30 else 10) +  # RSI not extreme
                (20 if abs(tp1_pct) > 1.0 else 10)  # Reasonable target
            ))
            
            confidence_level = "HIGH" if position_confidence > 65 else "MEDIUM" if position_confidence > 45 else "LOW"
            
            # Strategy recommendation
            if confidence > 70 and abs(tp1_pct) > 2.0:
                strategy = "Strong position with scaled entries"
            elif confidence > 50:
                strategy = "Standard position with risk management"
            else:
                strategy = "Skip or scalp with tight stops"
            
            trading_plans["BTC"] = {
                "plan_bias": plan_bias,
                "current_price": btc_price,
                "entry_low": entry_low,
                "entry_high": entry_high,
                "target1": target1,
                "target2": target2,
                "stop_loss": stop_loss,
                "tp1_pct": tp1_pct,
                "tp2_pct": tp2_pct,
                "sl_pct": sl_pct,
                "rrr1": rrr1,
                "rrr2": rrr2,
                "position_confidence": position_confidence,
                "confidence_level": confidence_level,
                "strategy": strategy,
                "support": btc_support,
                "resistance": btc_resistance,
                "rsi": btc_rsi,
                "signal": btc_signal,
                "trend": btc_data.get("trend", "neutral")
            }
            
            # ETH Trading Plan (similar logic)
            eth_price = eth_data.get("price", 0)
            if eth_price == 0:
                # Fallback to crypto data
                eth_price = market_data.get("crypto", {}).get("eth", 0)
            
            if eth_price > 0:
                eth_support = eth_data.get("support", eth_price * 0.95)
                eth_resistance = eth_data.get("resistance", eth_price * 1.05)
                eth_atr = eth_data.get("atr", eth_price * 0.02)
                eth_signal = eth_data.get("signal", "NEUTRAL")
                eth_rsi = eth_data.get("rsi14", 50)
                
                # Determine entry strategy based on market bias and technical signals
                market_bias = market_analysis.get("market_bias", "NEUTRAL")
                confidence = market_analysis.get("confidence", 50)
                
                # Risk management parameters
                leverage = 13.5  # Standard futures leverage
                risk_per_trade = 0.03  # 3% account risk
                
                if market_bias == "BULLISH" and eth_signal in ["BUY", "STRONG BUY"]:
                    # Bullish scenario
                    entry_low = max(eth_support, eth_price * 0.995)  # Tight entry near current price
                    entry_high = eth_price * 1.002
                    
                    # Stop loss below support with ATR buffer
                    stop_loss = min(eth_support * 0.998, eth_price - 1.5 * eth_atr)
                    
                    # Target levels based on resistance and confidence
                    risk = abs(eth_price - stop_loss)
                    if confidence > 70:
                        rrr = 3.0  # High confidence = higher targets
                    elif confidence > 50:
                        rrr = 2.0
                    else:
                        rrr = 1.5
                    
                    target1 = min(eth_resistance * 0.999, eth_price + rrr * risk)
                    target2 = min(eth_resistance * 1.005, eth_price + (rrr + 1) * risk)
                    
                    plan_bias = "BULLISH"
                    
                elif market_bias == "BEARISH" and eth_signal in ["SELL", "STRONG SELL"]:
                    # Bearish scenario
                    entry_high = min(eth_resistance, eth_price * 1.005)
                    entry_low = eth_price * 0.998
                    
                    # Stop loss above resistance with ATR buffer
                    stop_loss = max(eth_resistance * 1.002, eth_price + 1.5 * eth_atr)
                    
                    # Target levels
                    risk = abs(stop_loss - eth_price)
                    if confidence > 70:
                        rrr = 3.0
                    elif confidence > 50:
                        rrr = 2.0
                    else:
                        rrr = 1.5
                    
                    target1 = max(eth_support * 1.001, eth_price - rrr * risk)
                    target2 = max(eth_support * 0.995, eth_price - (rrr + 1) * risk)
                    
                    plan_bias = "BEARISH"
                    
                else:
                    # Neutral/Range-bound scenario
                    entry_low = eth_price * 0.99
                    entry_high = eth_price * 1.01
                    stop_loss = eth_price * (0.98 if market_bias != "BEARISH" else 1.02)
                    target1 = eth_price * (1.02 if market_bias != "BEARISH" else 0.98)
                    target2 = eth_price * (1.04 if market_bias != "BEARISH" else 0.96)
                    plan_bias = "NEUTRAL"
                
                # Calculate percentages and ratios
                entry_price = (entry_low + entry_high) / 2
                tp1_pct = ((target1 - entry_price) / entry_price) * 100
                tp2_pct = ((target2 - entry_price) / entry_price) * 100
                sl_pct = ((stop_loss - entry_price) / entry_price) * 100
                
                if abs(stop_loss - entry_price) > 0:
                    rrr1 = abs(target1 - entry_price) / abs(stop_loss - entry_price)
                    rrr2 = abs(target2 - entry_price) / abs(stop_loss - entry_price)
                else:
                    rrr1 = rrr2 = 1.0
                
                # Position confidence based on multiple factors
                position_confidence = min(85, max(25, 
                    confidence * 0.6 +  # Market confidence
                    (30 if eth_rsi < 70 and eth_rsi > 30 else 10) +  # RSI not extreme
                    (20 if abs(tp1_pct) > 1.0 else 10)  # Reasonable target
                ))
                
                confidence_level = "HIGH" if position_confidence > 65 else "MEDIUM" if position_confidence > 45 else "LOW"
                
                # Strategy recommendation
                if confidence > 70 and abs(tp1_pct) > 2.0:
                    strategy = "Strong position with scaled entries"
                elif confidence > 50:
                    strategy = "Standard position with risk management"
                else:
                    strategy = "Skip or scalp with tight stops"
                
                trading_plans["ETH"] = {
                    "plan_bias": plan_bias,
                    "current_price": eth_price,
                    "entry_low": entry_low,
                    "entry_high": entry_high,
                    "target1": target1,
                    "target2": target2,
                    "stop_loss": stop_loss,
                    "tp1_pct": tp1_pct,
                    "tp2_pct": tp2_pct,
                    "sl_pct": sl_pct,
                    "rrr1": rrr1,
                    "rrr2": rrr2,
                    "position_confidence": position_confidence,
                    "confidence_level": confidence_level,
                    "strategy": strategy,
                    "support": eth_support,
                    "resistance": eth_resistance,
                    "rsi": eth_rsi,
                    "signal": eth_signal,
                    "trend": eth_data.get("trend", "neutral")
                }
            
            return trading_plans
            
        except Exception as e:
            print(f"[ERROR] Trading levels calculation failed: {e}")
            return {"BTC": {}, "ETH": {}}

    def _count_data_points_used(self, market_data):
        """Count data points used in calculation analysis - ENHANCED to match AI (47 points)"""
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
        
        return count

    def format_calculation_telegram_message(self, market_analysis, trading_plans, market_data):
        """Format calculation prediction for Telegram in the same style as AI"""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            # Market overview
            market_bias = market_analysis.get("market_bias", "NEUTRAL")
            confidence = market_analysis.get("confidence", 50)
            scenario_confidence = market_analysis.get("scenario_confidence", "medium")
            bullish_pct = market_analysis.get("bullish_percentage", 50)
            bearish_pct = market_analysis.get("bearish_percentage", 50)
            strongest_signal = market_analysis.get("strongest_signal", "Unknown")
            volatility = market_analysis.get("volatility", "Medium")
            data_points = market_analysis.get("data_points_used", 0)
            
            # Fear & Greed data (same as AI format)
            fear_greed = market_data.get("fear_greed", {})
            fg_index = fear_greed.get("index", 50)
            fg_sentiment = fear_greed.get("sentiment", "Neutral")
            
            # BTC data
            btc_plan = trading_plans.get("BTC", {})
            btc_price = btc_plan.get("current_price", 0)
            btc_support = btc_plan.get("support", 0)
            btc_resistance = btc_plan.get("resistance", 0)
            btc_rsi = btc_plan.get("rsi", 50)
            btc_signal = btc_plan.get("signal", "NEUTRAL")
            btc_trend = btc_plan.get("trend", "neutral")
            
            # ETH data  
            eth_plan = trading_plans.get("ETH", {})
            eth_price = eth_plan.get("current_price", 0)
            eth_support = eth_plan.get("support", 0)
            eth_resistance = eth_plan.get("resistance", 0)
            eth_rsi = eth_plan.get("rsi", 50)
            eth_signal = eth_plan.get("signal", "NEUTRAL")
            eth_trend = eth_plan.get("trend", "neutral")
            
            message = f"""📊 **CALCULATION PREDICTION** 📊
━━━━━━━━━━━━━━━━━━━━

📊 EXECUTIVE SUMMARY
• Fear & Greed: {fg_index} ({fg_sentiment})
• Scenario: {market_bias} ({scenario_confidence} confidence)
• Timeframe: overnight and early morning
• Bullish: {bullish_pct:.1f}% | Bearish: {bearish_pct:.1f}%
• Strongest Signal: {strongest_signal}
• Volatility: {volatility}

BTC ANALYSIS
💰 Current: ${btc_price:,.0f}
📈 Resistance: ${btc_resistance:,.0f}
📉 Support: ${btc_support:,.0f}
📊 RSI: {btc_rsi:.1f}
📊 Signal: {btc_signal}
📈 Trend: {btc_trend.title()}

🎯 BTC PLAN - {btc_plan.get('plan_bias', 'NEUTRAL')}
• Entry: ${btc_plan.get('entry_low', 0):,.0f} - ${btc_plan.get('entry_high', 0):,.0f}
• Target: ${btc_plan.get('target1', 0):,.0f} ({btc_plan.get('tp1_pct', 0):+.1f}%)
• Stop: ${btc_plan.get('stop_loss', 0):,.0f} ({btc_plan.get('sl_pct', 0):+.1f}%)
• R/R: {btc_plan.get('rrr1', 0):.1f}:1
• Confidence: {btc_plan.get('position_confidence', 50):.0f}% ({btc_plan.get('confidence_level', 'MEDIUM')})

ETH ANALYSIS
💰 Current: ${eth_price:,.0f}
📈 Resistance: ${eth_resistance:,.0f}
📉 Support: ${eth_support:,.0f}
📊 RSI: {eth_rsi:.1f}
📊 Signal: {eth_signal}
📈 Trend: {eth_trend.title()}

🎯 ETH PLAN - {eth_plan.get('plan_bias', 'NEUTRAL')}
• Entry: ${eth_plan.get('entry_low', 0):,.0f} - ${eth_plan.get('entry_high', 0):,.0f}
• Target: ${eth_plan.get('target1', 0):,.0f} ({eth_plan.get('tp1_pct', 0):+.1f}%)
• Stop: ${eth_plan.get('stop_loss', 0):,.0f} ({eth_plan.get('sl_pct', 0):+.1f}%)
• R/R: {eth_plan.get('rrr1', 0):.1f}:1
• Confidence: {eth_plan.get('position_confidence', 50):.0f}% ({eth_plan.get('confidence_level', 'MEDIUM')})

━━━━━━━━━━━━━━━━━━━━
📈 Data Points: {data_points}/47
⏰ Generated: {timestamp}
🔢 Calculation-Based Analysis"""

            return message
            
        except Exception as e:
            print(f"[ERROR] Formatting calculation Telegram message: {e}")
            return f"📊 CALCULATION PREDICTION ERROR\n\nFailed to format prediction: {str(e)}\n\n⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

    def send_calculation_telegram(self, market_analysis, trading_plans, market_data, test_mode=False):
        """Send calculation prediction via Telegram"""
        try:
            message = self.format_calculation_telegram_message(market_analysis, trading_plans, market_data)
            
            # Determine which bot config to use (ONLY difference in test mode)
            if test_mode:
                bot_token = self.config["telegram"]["test"]["bot_token"]
                chat_id = self.config["telegram"]["test"]["chat_id"]
                prefix = "🧪 [TEST] "
                print(f"[INFO] Using TEST Telegram configuration")
            else:
                bot_token = self.config["telegram"]["bot_token"]
                chat_id = self.config["telegram"]["chat_id"]
                prefix = ""
                print(f"[INFO] Using PRODUCTION Telegram configuration")
            
            if not bot_token or not chat_id:
                mode_name = "test" if test_mode else "production"
                print(f"[ERROR] Telegram configuration missing for {mode_name} mode")
                print(f"[ERROR] Bot token: {'SET' if bot_token else 'NOT SET'}")
                print(f"[ERROR] Chat ID: {'SET' if chat_id else 'NOT SET'}")
                return False
            
            # Send message directly using the specific bot configuration (like AI predictor)
            from telegram_utils import TelegramBot
            bot = TelegramBot(bot_token=bot_token, chat_id=chat_id)
            result = bot.send_message(f"{prefix}{message}")
            
            if result:
                print(f"[INFO] ✅ Calculation prediction sent via Telegram ({'test' if test_mode else 'production'})")
                return True
            else:
                print(f"[ERROR] Failed to send calculation prediction via Telegram")
                return False
                
        except Exception as e:
            print(f"[ERROR] Sending calculation Telegram message: {e}")
            return False

    def save_calculation_prediction(self, market_analysis, trading_plans, market_data, test_mode=False):
        """Save calculation prediction to database and files (test mode has same functionality)"""
        try:
            timestamp = datetime.now(timezone.utc)
            
            # Prepare prediction data
            prediction_data = {
                "timestamp": timestamp.isoformat(),
                "type": "calculation_prediction",
                "test_mode": test_mode,
                "market_analysis": market_analysis,
                "trading_plans": trading_plans,
                "data_points_used": market_analysis.get("data_points_used", 0),
                "market_context": {
                    "btc_price": market_data.get("crypto", {}).get("btc", 0),
                    "eth_price": market_data.get("crypto", {}).get("eth", 0),
                    "fear_greed": market_data.get("fear_greed", {}).get("index", 0),
                    "btc_dominance": market_data.get("btc_dominance", 0)
                }
            }
            
            # Save to database (same for both test and production)
            try:
                from database_manager import db_manager
                # DISABLED: This conflicts with the main script's extraction-based saves
                # db_manager.save_prediction(prediction_data)
                print(f"[INFO] ✅ Calculation prediction data prepared ({'test mode' if test_mode else 'production mode'})")
                print(f"[INFO] Database save handled by main script through extraction")
            except ImportError:
                print("[WARN] Database not available - saving to file only")
            except Exception as e:
                print(f"[ERROR] Database preparation failed: {e}")
            
            # Save to JSON file as backup (same filename format for both modes)
            filename = f"calculation_prediction_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(filename, 'w') as f:
                    json.dump(prediction_data, f, indent=2, default=str)
                print(f"[INFO] ✅ Calculation prediction saved to {filename}")
            except Exception as e:
                print(f"[ERROR] File save failed: {e}")
            
            return prediction_data
            
        except Exception as e:
            print(f"[ERROR] Saving calculation prediction: {e}")
            return None

    def run_calculation_prediction(self, market_data, test_mode=False, save_results=True, send_telegram=True):
        """Complete calculation prediction workflow"""
        try:
            mode_text = "🧪 TEST MODE" if test_mode else "🚀 PRODUCTION MODE"
            print("\n" + "="*50)
            print(f"📊 STARTING CALCULATION PREDICTION SYSTEM - {mode_text}")
            print("="*50)
            
            # Analyze market conditions
            market_analysis = self.analyze_market_conditions(market_data)
            
            # Calculate trading levels
            trading_plans = self.calculate_trading_levels(market_data, market_analysis)
            
            # Save prediction if requested
            if save_results:
                saved_data = self.save_calculation_prediction(market_analysis, trading_plans, market_data, test_mode)
                if saved_data:
                    mode_text = "test file" if test_mode else "database and file"
                    print(f"[INFO] ✅ Calculation prediction saved to {mode_text}")
            
            # Send Telegram message if requested
            if send_telegram and self.config["telegram"]["enabled"]:
                telegram_success = self.send_calculation_telegram(market_analysis, trading_plans, market_data, test_mode)
                if not telegram_success:
                    print("[WARN] Telegram sending failed")
            
            print("\n" + "="*50)
            print(f"📊 CALCULATION PREDICTION SYSTEM COMPLETE - {mode_text}")
            print("="*50)
            
            result = {
                "market_analysis": market_analysis,
                "trading_plans": trading_plans,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "test_mode": test_mode
            }
            
            return result
            
        except Exception as e:
            print(f"[CRITICAL] Calculation prediction workflow failed: {e}")
            return None

    async def generate_prediction(self, market_data, test_mode=False):
        """Generate calculation prediction (async wrapper for compatibility)"""
        try:
            return self.run_calculation_prediction(market_data, test_mode, save_results=True, send_telegram=True)
        except Exception as e:
            print(f"[ERROR] Calculation prediction generation failed: {e}")
            return None


# Utility function for external use
def create_calculation_predictor(config):
    """Factory function to create a calculation predictor instance"""
    return CalculationPredictor(config)


if __name__ == "__main__":
    # Test the calculation predictor
    print("Testing calculation predictor...")
    
    # Mock config for testing
    test_config = {
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
                "volatility": "medium",
                "volume_trend": "increasing",
                "atr": 900
            },
            "ETH": {
                "price": 2800,
                "rsi14": 48.1,
                "signal": "BUY",
                "trend": "bullish",
                "support": 2750,
                "resistance": 2850,
                "volatility": "medium",
                "volume_trend": "stable",
                "atr": 56
            }
        },
        "futures": {
            "BTC": {"funding_rate": 0.01, "long_ratio": 0.6, "short_ratio": 0.4},
            "ETH": {"funding_rate": 0.015, "long_ratio": 0.55, "short_ratio": 0.45}
        },
        "stock_indices": {"sp500_change": 1.2, "nasdaq_change": 1.5, "vix": 18.5},
        "interest_rates": {"fed_rate": 5.25},
        "inflation": {"inflation_rate": 3.2},
        "commodities": {"gold": 2050, "crude_oil": 85}
    }
    
    try:
        predictor = CalculationPredictor(test_config)
        result = predictor.run_calculation_prediction(mock_market_data, test_mode=True, send_telegram=False)
        print(f"\nCalculation prediction test:")
        print(f"Success: {result is not None}")
        print(f"Market bias: {result['market_analysis']['market_bias'] if result else 'N/A'}")
        print(f"Data points used: {result['market_analysis']['data_points_used'] if result else 0}")
    except Exception as e:
        print(f"Test failed: {e}") 