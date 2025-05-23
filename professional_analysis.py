#!/usr/bin/env python3

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
from typing import Dict, List, Tuple, Optional

class ProfessionalTraderAnalysis:
    """
    Professional trading analysis framework that thinks like a seasoned trader
    Combines technical, sentiment, volume, and macro analysis for 12-hour forecasts
    """
    
    def __init__(self):
        self.timeframes = ['1h', '4h', '12h', '1d']
        self.confidence_weights = {
            'price_action': 0.25,
            'volume_flow': 0.20,
            'volatility': 0.15,
            'momentum': 0.15,
            'funding_sentiment': 0.15,
            'macro_context': 0.10
        }
    
    def analyze_market_structure(self, data: Dict) -> Dict:
        """Analyze price action and market structure like a professional trader"""
        
        # Get technical indicators from existing data
        btc_data = data.get('technical_indicators', {}).get('BTC', {})
        eth_data = data.get('technical_indicators', {}).get('ETH', {})
        
        if not btc_data:
            return {"error": "Insufficient technical data"}
        
        current_price = btc_data.get('price', 0)
        support = btc_data.get('support', 0)
        resistance = btc_data.get('resistance', 0)
        trend = btc_data.get('trend', 'neutral')
        
        # Calculate market structure
        structure_analysis = {
            'trend_strength': self._calculate_trend_strength(btc_data),
            'support_strength': self._calculate_level_strength(current_price, support, 'support'),
            'resistance_strength': self._calculate_level_strength(current_price, resistance, 'resistance'),
            'breakout_probability': self._calculate_breakout_probability(current_price, support, resistance),
            'range_position': self._calculate_range_position(current_price, support, resistance)
        }
        
        # Determine bias
        if trend.startswith('bull'):
            bias = 'bullish'
            bias_strength = 0.7 if trend == 'bullish' else 0.5
        elif trend.startswith('bear'):
            bias = 'bearish'
            bias_strength = 0.7 if trend == 'bearish' else 0.5
        else:
            bias = 'neutral'
            bias_strength = 0.3
        
        return {
            'bias': bias,
            'bias_strength': bias_strength,
            'structure': structure_analysis,
            'key_levels': {
                'support': support,
                'resistance': resistance,
                'current': current_price
            }
        }
    
    def analyze_volume_flow(self, data: Dict) -> Dict:
        """Analyze volume and order flow dynamics"""
        
        volumes = data.get('volumes', {})
        btc_volume = volumes.get('btc_volume', 0)
        
        # Get historical volume data for comparison
        try:
            btc_ticker = yf.Ticker("BTC-USD")
            hist_data = btc_ticker.history(period="7d", interval="1h")
            
            if not hist_data.empty:
                recent_volumes = hist_data['Volume'].tail(24).values
                avg_volume = np.mean(recent_volumes)
                volume_percentile = (btc_volume / avg_volume) if avg_volume > 0 else 1
                
                # Volume analysis
                volume_analysis = {
                    'current_vs_avg': volume_percentile,
                    'volume_trend': 'increasing' if volume_percentile > 1.2 else 'decreasing' if volume_percentile < 0.8 else 'stable',
                    'volume_strength': min(volume_percentile, 3.0) / 3.0  # Cap at 3x for scoring
                }
            else:
                volume_analysis = {
                    'current_vs_avg': 1.0,
                    'volume_trend': 'unknown',
                    'volume_strength': 0.5
                }
        except Exception as e:
            print(f"[WARN] Volume analysis failed: {e}")
            volume_analysis = {
                'current_vs_avg': 1.0,
                'volume_trend': 'unknown',
                'volume_strength': 0.5
            }
        
        return volume_analysis
    
    def analyze_volatility_context(self, data: Dict) -> Dict:
        """Analyze volatility metrics and expected movement range"""
        
        btc_data = data.get('technical_indicators', {}).get('BTC', {})
        current_price = btc_data.get('price', 0)
        atr = btc_data.get('atr', 0)
        volatility = btc_data.get('volatility', 'medium')
        
        if current_price == 0:
            return {"error": "No price data"}
        
        # Calculate expected 12-hour range
        atr_percentage = (atr / current_price) * 100 if current_price > 0 else 0
        
        # Volatility scoring
        if volatility == 'high':
            vol_score = 0.8
            expected_range = atr_percentage * 1.5  # High vol = wider range
        elif volatility == 'low':
            vol_score = 0.3
            expected_range = atr_percentage * 0.7  # Low vol = tighter range
        else:
            vol_score = 0.5
            expected_range = atr_percentage
        
        # Calculate 12-hour movement expectations
        range_12h = {
            'conservative': current_price * (expected_range * 0.5) / 100,
            'expected': current_price * expected_range / 100,
            'aggressive': current_price * (expected_range * 1.5) / 100
        }
        
        return {
            'atr_percentage': atr_percentage,
            'volatility_score': vol_score,
            'expected_range_12h': range_12h,
            'volatility_regime': volatility,
            'breakout_threshold': atr * 1.2  # Movement needed for confirmed breakout
        }
    
    def analyze_momentum_divergence(self, data: Dict) -> Dict:
        """Analyze RSI, momentum, and divergence signals"""
        
        btc_data = data.get('technical_indicators', {}).get('BTC', {})
        rsi = btc_data.get('rsi14', 50)
        
        # RSI analysis
        if rsi > 70:
            rsi_signal = 'overbought'
            rsi_strength = min((rsi - 70) / 20, 1.0)  # Scale 70-90 to 0-1
        elif rsi < 30:
            rsi_signal = 'oversold'
            rsi_strength = min((30 - rsi) / 20, 1.0)  # Scale 30-10 to 0-1
        else:
            rsi_signal = 'neutral'
            rsi_strength = 0.5 - abs(rsi - 50) / 40  # Closer to 50 = lower strength
        
        # Momentum scoring
        momentum_score = 0.5
        if rsi_signal == 'overbought':
            momentum_score = 0.2  # Bearish bias
        elif rsi_signal == 'oversold':
            momentum_score = 0.8  # Bullish bias
        
        return {
            'rsi_value': rsi,
            'rsi_signal': rsi_signal,
            'rsi_strength': rsi_strength,
            'momentum_score': momentum_score,
            'reversal_probability': rsi_strength if rsi_signal != 'neutral' else 0.1
        }
    
    def analyze_funding_sentiment(self, data: Dict) -> Dict:
        """Analyze funding rates and sentiment for positioning insights"""
        
        futures_data = data.get('futures', {})
        fear_greed = data.get('fear_greed', {})
        
        btc_funding = futures_data.get('BTC', {}).get('funding_rate', 0)
        fg_index = fear_greed.get('index', 50) if isinstance(fear_greed, dict) else 50
        
        # Funding rate analysis
        if btc_funding > 0.05:  # 5% = very high
            funding_signal = 'extremely_long_heavy'
            funding_strength = min(btc_funding / 0.1, 1.0)
        elif btc_funding > 0.02:  # 2% = high
            funding_signal = 'long_heavy'
            funding_strength = min(btc_funding / 0.05, 1.0)
        elif btc_funding < -0.02:  # -2% = shorts paying
            funding_signal = 'short_heavy'
            funding_strength = min(abs(btc_funding) / 0.05, 1.0)
        else:
            funding_signal = 'balanced'
            funding_strength = 0.3
        
        # Fear & Greed analysis
        if fg_index > 75:
            fg_signal = 'extreme_greed'
            fg_bias = 'bearish'  # Contrarian
        elif fg_index > 60:
            fg_signal = 'greed'
            fg_bias = 'bearish'
        elif fg_index < 25:
            fg_signal = 'extreme_fear'
            fg_bias = 'bullish'  # Contrarian
        elif fg_index < 40:
            fg_signal = 'fear'
            fg_bias = 'bullish'
        else:
            fg_signal = 'neutral'
            fg_bias = 'neutral'
        
        # Combined sentiment score
        sentiment_score = 0.5
        if funding_signal in ['extremely_long_heavy', 'long_heavy'] and fg_bias == 'bearish':
            sentiment_score = 0.2  # Very bearish
        elif funding_signal == 'short_heavy' and fg_bias == 'bullish':
            sentiment_score = 0.8  # Very bullish
        elif fg_bias == 'bullish':
            sentiment_score = 0.7
        elif fg_bias == 'bearish':
            sentiment_score = 0.3
        
        return {
            'funding_rate': btc_funding,
            'funding_signal': funding_signal,
            'funding_strength': funding_strength,
            'fear_greed_index': fg_index,
            'fear_greed_signal': fg_signal,
            'sentiment_bias': fg_bias,
            'combined_sentiment_score': sentiment_score
        }
    
    def analyze_macro_context(self, data: Dict) -> Dict:
        """Analyze macro environment and correlations"""
        
        # Get macro data
        indices = data.get('stock_indices', {})
        commodities = data.get('commodities', {})
        rates = data.get('interest_rates', {})
        
        sp500 = indices.get('sp500')
        vix = indices.get('vix')
        gold = commodities.get('gold')
        dxy_proxy = 100  # Placeholder for DXY
        
        macro_score = 0.5  # Default neutral
        
        # Risk-on/Risk-off analysis
        risk_signals = []
        
        if vix and vix < 20:
            risk_signals.append('risk_on')
        elif vix and vix > 30:
            risk_signals.append('risk_off')
        
        if sp500 and hasattr(data.get('stock_indices', {}), 'sp500_change'):
            sp500_change = indices.get('sp500_change', 0)
            if sp500_change > 1:
                risk_signals.append('risk_on')
            elif sp500_change < -1:
                risk_signals.append('risk_off')
        
        # Calculate macro bias
        risk_on_count = risk_signals.count('risk_on')
        risk_off_count = risk_signals.count('risk_off')
        
        if risk_on_count > risk_off_count:
            macro_bias = 'risk_on'
            macro_score = 0.7  # Good for BTC
        elif risk_off_count > risk_on_count:
            macro_bias = 'risk_off'
            macro_score = 0.3  # Bad for BTC
        else:
            macro_bias = 'neutral'
            macro_score = 0.5
        
        return {
            'macro_bias': macro_bias,
            'macro_score': macro_score,
            'vix_level': vix,
            'risk_signals': risk_signals,
            'environment': 'supportive' if macro_score > 0.6 else 'challenging' if macro_score < 0.4 else 'neutral'
        }
    
    def generate_probabilistic_forecast(self, data: Dict) -> Dict:
        """Generate a comprehensive probabilistic forecast like a professional trader"""
        
        print("\n[INFO] Generating professional trader analysis...")
        
        # Run all analysis components
        structure = self.analyze_market_structure(data)
        volume = self.analyze_volume_flow(data)
        volatility = self.analyze_volatility_context(data)
        momentum = self.analyze_momentum_divergence(data)
        sentiment = self.analyze_funding_sentiment(data)
        macro = self.analyze_macro_context(data)
        
        if 'error' in structure:
            return {"error": "Insufficient data for analysis"}
        
        # Calculate weighted probability scores
        scores = {
            'price_action': structure['bias_strength'] if structure['bias'] == 'bullish' else (1 - structure['bias_strength']) if structure['bias'] == 'bearish' else 0.5,
            'volume_flow': volume['volume_strength'],
            'volatility': volatility['volatility_score'],
            'momentum': momentum['momentum_score'],
            'funding_sentiment': sentiment['combined_sentiment_score'],
            'macro_context': macro['macro_score']
        }
        
        # Calculate weighted final probability
        bullish_probability = sum(
            scores[factor] * self.confidence_weights[factor] 
            for factor in scores
        )
        
        bearish_probability = 1 - bullish_probability
        
        # Determine primary scenario
        if bullish_probability > 0.65:
            primary_scenario = 'bullish'
            confidence = 'high'
        elif bullish_probability > 0.55:
            primary_scenario = 'bullish'
            confidence = 'medium'
        elif bearish_probability > 0.65:
            primary_scenario = 'bearish'
            confidence = 'high'
        elif bearish_probability > 0.55:
            primary_scenario = 'bearish'
            confidence = 'medium'
        else:
            primary_scenario = 'neutral'
            confidence = 'low'
        
        # Generate price targets
        current_price = structure['key_levels']['current']
        support = structure['key_levels']['support']
        resistance = structure['key_levels']['resistance']
        expected_move = volatility['expected_range_12h']['expected']
        
        # Calculate targets based on scenario
        if primary_scenario == 'bullish':
            target_1 = min(resistance * 0.95, current_price + expected_move * 0.7)
            target_2 = min(resistance * 1.02, current_price + expected_move * 1.2)
            stop_loss = max(support * 1.02, current_price - expected_move * 0.8)
        elif primary_scenario == 'bearish':
            target_1 = max(support * 1.05, current_price - expected_move * 0.7)
            target_2 = max(support * 0.98, current_price - expected_move * 1.2)
            stop_loss = min(resistance * 0.98, current_price + expected_move * 0.8)
        else:
            target_1 = current_price + expected_move * 0.3
            target_2 = current_price - expected_move * 0.3
            stop_loss = current_price + expected_move * 0.5
        
        return {
            'primary_scenario': primary_scenario,
            'confidence_level': confidence,
            'bullish_probability': round(bullish_probability * 100, 1),
            'bearish_probability': round(bearish_probability * 100, 1),
            'component_scores': scores,
            'price_targets': {
                'current': current_price,
                'target_1': round(target_1, 0),
                'target_2': round(target_2, 0),
                'stop_loss': round(stop_loss, 0),
                'expected_move': round(expected_move, 0)
            },
            'key_factors': {
                'strongest_signal': max(scores.items(), key=lambda x: abs(x[1] - 0.5)),
                'weakest_signal': min(scores.items(), key=lambda x: abs(x[1] - 0.5))
            },
            'risk_assessment': {
                'volatility_regime': volatility['volatility_regime'],
                'position_sizing': 'reduced' if volatility['volatility_regime'] == 'high' else 'normal',
                'time_decay': '12-hour window - reassess after'
            },
            'detailed_analysis': {
                'structure': structure,
                'volume': volume,
                'volatility': volatility,
                'momentum': momentum,
                'sentiment': sentiment,
                'macro': macro
            }
        }
    
    def _calculate_trend_strength(self, btc_data: Dict) -> float:
        """Calculate trend strength from technical data"""
        trend = btc_data.get('trend', 'neutral')
        
        if trend == 'bullish':
            return 0.8
        elif trend == 'bullish_weak':
            return 0.6
        elif trend == 'bearish':
            return 0.2
        elif trend == 'bearish_weak':
            return 0.4
        else:
            return 0.5
    
    def _calculate_level_strength(self, current: float, level: float, level_type: str) -> float:
        """Calculate strength of support/resistance level"""
        if not current or not level:
            return 0.5
        
        distance_pct = abs((current - level) / current) * 100
        
        if distance_pct < 1:  # Very close
            return 0.9
        elif distance_pct < 3:  # Close
            return 0.7
        elif distance_pct < 5:  # Moderate
            return 0.5
        else:  # Far
            return 0.3
    
    def _calculate_breakout_probability(self, current: float, support: float, resistance: float) -> float:
        """Calculate probability of breakout from current range"""
        if not all([current, support, resistance]):
            return 0.5
        
        range_size = resistance - support
        position_in_range = (current - support) / range_size
        
        # Higher probability near edges
        if position_in_range > 0.8 or position_in_range < 0.2:
            return 0.7
        else:
            return 0.3
    
    def _calculate_range_position(self, current: float, support: float, resistance: float) -> str:
        """Determine position within the range"""
        if not all([current, support, resistance]):
            return 'unknown'
        
        range_size = resistance - support
        position_in_range = (current - support) / range_size
        
        if position_in_range > 0.7:
            return 'upper_range'
        elif position_in_range < 0.3:
            return 'lower_range'
        else:
            return 'middle_range' 