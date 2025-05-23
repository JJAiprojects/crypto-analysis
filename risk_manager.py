import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import os

class RiskManager:
    def __init__(self):
        self.risk_metrics = {}
        self.position_sizes = {}
        self.stop_loss_levels = {}
        self.take_profit_levels = {}
        self.volatility_history = {}
        
    def calculate_volatility(self, price_history, window=14):
        """Calculate price volatility using standard deviation"""
        returns = np.log(price_history / price_history.shift(1))
        volatility = returns.rolling(window=window).std() * np.sqrt(252)  # Annualized
        return volatility
    
    def calculate_atr(self, high, low, close, period=14):
        """Calculate Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def update_risk_metrics(self, current_data, prediction_confidence):
        """Update risk metrics based on current market conditions and prediction confidence"""
        # Calculate volatility if we have enough price history
        if 'price_history' in current_data:
            price_history = pd.Series(current_data['price_history'])
            volatility = self.calculate_volatility(price_history)
            self.risk_metrics['volatility'] = float(volatility.iloc[-1])
        
        # Calculate ATR if we have OHLC data
        if all(key in current_data for key in ['high', 'low', 'close']):
            atr = self.calculate_atr(
                current_data['high'],
                current_data['low'],
                current_data['close']
            )
            self.risk_metrics['atr'] = float(atr.iloc[-1])
        
        # Update prediction confidence
        self.risk_metrics['prediction_confidence'] = prediction_confidence
        
        # Calculate risk score (0-100)
        risk_score = 50  # Base risk score
        
        # Adjust based on volatility
        if 'volatility' in self.risk_metrics:
            vol = self.risk_metrics['volatility']
            if vol > 0.8:  # High volatility
                risk_score += 20
            elif vol < 0.2:  # Low volatility
                risk_score -= 20
        
        # Adjust based on prediction confidence
        if prediction_confidence > 0.8:
            risk_score -= 15
        elif prediction_confidence < 0.5:
            risk_score += 15
        
        self.risk_metrics['risk_score'] = min(max(risk_score, 0), 100)
    
    def calculate_position_size(self, account_size, risk_per_trade=0.02):
        """Calculate position size based on risk metrics"""
        if 'risk_score' not in self.risk_metrics:
            return account_size * risk_per_trade
        
        # Adjust risk per trade based on risk score
        adjusted_risk = risk_per_trade * (1 - (self.risk_metrics['risk_score'] / 200))
        
        # Calculate position size
        position_size = account_size * adjusted_risk
        
        self.position_sizes = {
            'base_size': float(position_size),
            'adjusted_risk': float(adjusted_risk),
            'account_size': float(account_size)
        }
        
        return position_size
    
    def calculate_stop_loss(self, entry_price, direction):
        """Calculate stop loss levels based on ATR and volatility"""
        if 'atr' not in self.risk_metrics:
            return None
        
        atr = self.risk_metrics['atr']
        volatility = self.risk_metrics.get('volatility', 0.5)
        
        # Calculate stop loss distance based on ATR and volatility
        sl_distance = atr * (1 + volatility)
        
        if direction == 'long':
            stop_loss = entry_price - sl_distance
        else:
            stop_loss = entry_price + sl_distance
        
        self.stop_loss_levels = {
            'price': float(stop_loss),
            'distance': float(sl_distance),
            'atr_multiple': float(1 + volatility)
        }
        
        return stop_loss
    
    def calculate_take_profit(self, entry_price, direction, risk_reward_ratio=2):
        """Calculate take profit levels based on stop loss distance"""
        if not self.stop_loss_levels:
            return None
        
        sl_distance = self.stop_loss_levels['distance']
        tp_distance = sl_distance * risk_reward_ratio
        
        if direction == 'long':
            take_profit = entry_price + tp_distance
        else:
            take_profit = entry_price - tp_distance
        
        self.take_profit_levels = {
            'price': float(take_profit),
            'distance': float(tp_distance),
            'risk_reward_ratio': float(risk_reward_ratio)
        }
        
        return take_profit
    
    def get_risk_summary(self):
        """Get a summary of current risk metrics and levels"""
        return {
            'risk_metrics': self.risk_metrics,
            'position_sizes': self.position_sizes,
            'stop_loss_levels': self.stop_loss_levels,
            'take_profit_levels': self.take_profit_levels
        }
    
    def save_risk_data(self, directory='risk_data'):
        """Save risk metrics and levels to file"""
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{directory}/risk_data_{timestamp}.json"
        
        data = {
            'timestamp': timestamp,
            'risk_metrics': self.risk_metrics,
            'position_sizes': self.position_sizes,
            'stop_loss_levels': self.stop_loss_levels,
            'take_profit_levels': self.take_profit_levels
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
    
    def load_risk_data(self, filename):
        """Load risk data from file"""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Risk data file {filename} not found")
        
        with open(filename, 'r') as f:
            data = json.load(f)
        
        self.risk_metrics = data['risk_metrics']
        self.position_sizes = data['position_sizes']
        self.stop_loss_levels = data['stop_loss_levels']
        self.take_profit_levels = data['take_profit_levels'] 