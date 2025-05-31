#!/usr/bin/env python3

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PredictionExtractor:
    """Extract essential trading signals from AI and calculation predictions"""
    
    def __init__(self):
        self.ai_patterns = self._setup_ai_patterns()
    
    def _setup_ai_patterns(self):
        """Setup regex patterns to extract trading signals from AI text"""
        return {
            'entry': [
                r'entry.*?(?:level|price|at|around).*?(\$?\d+[,.]?\d*)',
                r'(?:buy|long|enter).*?(?:at|around|near).*?(\$?\d+[,.]?\d*)',
                r'target entry.*?(\$?\d+[,.]?\d*)',
                r'enter.*?(\$?\d+[,.]?\d*)'
            ],
            'stop_loss': [
                r'stop.?loss.*?(\$?\d+[,.]?\d*)',
                r'sl.*?(\$?\d+[,.]?\d*)',
                r'stop.*?(\$?\d+[,.]?\d*)',
                r'cut losses.*?(\$?\d+[,.]?\d*)'
            ],
            'take_profit': [
                r'take.?profit.*?(\$?\d+[,.]?\d*)',
                r'tp.*?(\$?\d+[,.]?\d*)',
                r'target.*?(\$?\d+[,.]?\d*)',
                r'profit.*?(?:at|around).*?(\$?\d+[,.]?\d*)'
            ],
            'confidence': [
                r'confidence.*?(\d+)%',
                r'(\d+)%.*?confidence',
                r'certainty.*?(\d+)%',
                r'conviction.*?(\d+)%'
            ]
        }
    
    def extract_from_ai_prediction(self, ai_text: str, current_btc_price: float) -> Dict:
        """Extract trading signals from AI prediction text"""
        try:
            # Clean the text
            text = ai_text.lower().replace(',', '').replace('$', '')
            
            # Extract values
            entry = self._extract_price(text, self.ai_patterns['entry'], current_btc_price)
            stop_loss = self._extract_price(text, self.ai_patterns['stop_loss'], current_btc_price, entry)
            take_profit = self._extract_price(text, self.ai_patterns['take_profit'], current_btc_price, entry)
            confidence = self._extract_confidence(text)
            
            # Validate and adjust if needed
            validated_signals = self._validate_signals(entry, stop_loss, take_profit, confidence, current_btc_price)
            
            return {
                'method': 'ai',
                'entry_level': validated_signals['entry'],
                'stop_loss': validated_signals['stop_loss'],
                'take_profit': validated_signals['take_profit'],
                'confidence': validated_signals['confidence'],
                'raw_text': ai_text[:500],  # Store snippet for reference
                'extraction_success': validated_signals['valid']
            }
            
        except Exception as e:
            logger.error(f"Error extracting from AI prediction: {e}")
            return self._create_fallback_ai_prediction(current_btc_price)
    
    def extract_from_calculation_prediction(self, calc_result: Dict, current_btc_price: float) -> Dict:
        """Extract trading signals from calculation prediction result"""
        try:
            # Handle both direct market_analysis and full prediction result
            if 'market_analysis' in calc_result:
                # Full prediction result with trading_plans
                market_analysis = calc_result.get('market_analysis', {})
                trading_plans = calc_result.get('trading_plans', {})
                btc_plan = trading_plans.get('BTC', {})
            else:
                # Direct market_analysis result
                market_analysis = calc_result
                btc_plan = {}
            
            market_bias = market_analysis.get('market_bias', 'NEUTRAL')
            confidence = market_analysis.get('confidence', 50)
            sentiment_score = market_analysis.get('sentiment_score', 0)
            
            # If we have trading plans, use them preferentially
            if btc_plan and btc_plan.get('current_price', 0) > 0:
                entry_low = btc_plan.get('entry_low', current_btc_price * 0.999)
                entry_high = btc_plan.get('entry_high', current_btc_price * 1.001)
                entry = (entry_low + entry_high) / 2
                take_profit = btc_plan.get('target1', current_btc_price * 1.02)
                stop_loss = btc_plan.get('stop_loss', current_btc_price * 0.98)
                position_confidence = btc_plan.get('position_confidence', confidence)
                
                print(f"[INFO] Using trading plan values: Entry=${entry:.2f}, TP=${take_profit:.2f}, SL=${stop_loss:.2f}")
            else:
                # Generate trading signals based on market analysis only
                print(f"[INFO] No trading plan found, generating signals from market analysis")
                if market_bias == 'BULLISH':
                    # Conservative long position
                    entry = current_btc_price * 0.998  # Enter slightly below current price
                    take_profit = current_btc_price * (1.03 if confidence > 70 else 1.02)  # 2-3% profit target
                    stop_loss = current_btc_price * 0.97  # 3% stop loss
                elif market_bias == 'BEARISH':
                    # Conservative short position
                    entry = current_btc_price * 1.002  # Enter slightly above current price
                    take_profit = current_btc_price * (0.97 if confidence > 70 else 0.98)  # 2-3% profit target
                    stop_loss = current_btc_price * 1.03  # 3% stop loss
                else:
                    # Neutral - small long bias (crypto default)
                    entry = current_btc_price * 0.999
                    take_profit = current_btc_price * 1.015  # 1.5% profit target
                    stop_loss = current_btc_price * 0.985   # 1.5% stop loss
                    confidence = min(confidence, 60)  # Cap confidence for neutral
                
                position_confidence = confidence
            
            return {
                'method': 'calculation',
                'entry_level': round(entry, 2),
                'stop_loss': round(stop_loss, 2),
                'take_profit': round(take_profit, 2),
                'confidence': round(position_confidence, 1),
                'market_bias': market_bias,
                'sentiment_score': round(sentiment_score, 3),
                'extraction_success': True
            }
            
        except Exception as e:
            logger.error(f"Error extracting from calculation prediction: {e}")
            return self._create_fallback_calculation_prediction(current_btc_price)
    
    def _extract_price(self, text: str, patterns: List[str], current_price: float, reference_price: Optional[float] = None) -> Optional[float]:
        """Extract price value from text using patterns"""
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Clean and convert to float
                    price_str = str(match).replace(',', '').replace('$', '').strip()
                    price = float(price_str)
                    
                    # Validate price is reasonable (within 20% of current price)
                    if current_price * 0.8 <= price <= current_price * 1.2:
                        return round(price, 2)
                        
                except (ValueError, TypeError):
                    continue
        return None
    
    def _extract_confidence(self, text: str) -> float:
        """Extract confidence percentage from text"""
        for pattern in self.ai_patterns['confidence']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    confidence = float(match)
                    if 0 <= confidence <= 100:
                        return confidence
                except (ValueError, TypeError):
                    continue
        return 65.0  # Default moderate confidence
    
    def _validate_signals(self, entry: Optional[float], stop_loss: Optional[float], 
                         take_profit: Optional[float], confidence: float, current_price: float) -> Dict:
        """Validate and adjust trading signals"""
        
        # Use current price as fallback for entry
        if not entry:
            entry = current_price * 0.999  # Slightly below current
        
        # Determine if it's likely a long or short position
        is_long = entry <= current_price * 1.001
        
        if is_long:
            # Long position validation
            if not stop_loss or stop_loss >= entry:
                stop_loss = entry * 0.97  # 3% stop loss
            if not take_profit or take_profit <= entry:
                take_profit = entry * 1.03  # 3% take profit
        else:
            # Short position validation  
            if not stop_loss or stop_loss <= entry:
                stop_loss = entry * 1.03  # 3% stop loss
            if not take_profit or take_profit >= entry:
                take_profit = entry * 0.97  # 3% take profit
        
        # Validate confidence
        if not confidence or confidence < 10 or confidence > 95:
            confidence = 65.0
        
        return {
            'entry': round(entry, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'confidence': round(confidence, 1),
            'valid': True
        }
    
    def _create_fallback_ai_prediction(self, current_price: float) -> Dict:
        """Create fallback AI prediction when extraction fails"""
        return {
            'method': 'ai',
            'entry_level': round(current_price * 0.999, 2),
            'stop_loss': round(current_price * 0.97, 2),
            'take_profit': round(current_price * 1.03, 2),
            'confidence': 50.0,
            'raw_text': 'Extraction failed - using fallback values',
            'extraction_success': False
        }
    
    def _create_fallback_calculation_prediction(self, current_price: float) -> Dict:
        """Create fallback calculation prediction when extraction fails"""
        return {
            'method': 'calculation',
            'entry_level': round(current_price * 0.999, 2),
            'stop_loss': round(current_price * 0.97, 2),
            'take_profit': round(current_price * 1.03, 2),
            'confidence': 50.0,
            'market_bias': 'NEUTRAL',
            'sentiment_score': 0.0,
            'extraction_success': False
        }
    
    def save_extracted_predictions(self, ai_signals: Dict, calc_signals: Dict, 
                                 market_data: Dict, test_mode: bool = False) -> bool:
        """Save both extracted predictions to database"""
        try:
            from database_manager import db_manager
            timestamp = datetime.now(timezone.utc)
            date_str = timestamp.strftime('%Y-%m-%d')
            time_str = timestamp.strftime('%H:%M')
            
            # Get current BTC price for notes
            btc_price = market_data.get("crypto", {}).get("btc", 0)
            
            # Save AI prediction
            ai_notes = f"BTC: ${btc_price:,.0f} | Extraction: {'Success' if ai_signals.get('extraction_success') else 'Fallback'}"
            if test_mode:
                ai_notes = f"[TEST] {ai_notes}"
                
            ai_saved = db_manager.save_simple_prediction(
                date=date_str,
                time=time_str,
                method='ai',
                entry_level=ai_signals['entry_level'],
                stop_loss=ai_signals['stop_loss'],
                take_profit=ai_signals['take_profit'],
                confidence=ai_signals['confidence'],
                coin='BTC',
                notes=ai_notes
            )
            
            # Save calculation prediction
            calc_notes = f"BTC: ${btc_price:,.0f} | Bias: {calc_signals.get('market_bias', 'NEUTRAL')} | Score: {calc_signals.get('sentiment_score', 0):.3f}"
            if test_mode:
                calc_notes = f"[TEST] {calc_notes}"
                
            calc_saved = db_manager.save_simple_prediction(
                date=date_str,
                time=time_str,
                method='calculation',
                entry_level=calc_signals['entry_level'],
                stop_loss=calc_signals['stop_loss'],
                take_profit=calc_signals['take_profit'],
                confidence=calc_signals['confidence'],
                coin='BTC',
                notes=calc_notes
            )
            
            if ai_saved and calc_saved:
                logger.info("✅ Both predictions saved to database successfully")
                return True
            else:
                logger.warning(f"⚠️ Partial save: AI={ai_saved}, Calc={calc_saved}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving extracted predictions: {e}")
            return False

# Global extractor instance
extractor = PredictionExtractor() 