#!/usr/bin/env python3

import json
import os
from datetime import datetime, timedelta

class RiskManager:
    """Risk management system for crypto trading"""
    
    def __init__(self):
        self.max_risk_per_trade = 0.02  # 2% max risk per trade
        self.risk_reward_ratio = 2.0    # Minimum 2:1 RR ratio
        self.max_portfolio_risk = 0.10  # 10% max portfolio risk
        self.max_daily_loss = 0.05      # 5% max daily loss
        
        # Risk metrics
        self.current_portfolio_risk = 0.0
        self.daily_pnl = 0.0
        self.open_positions = []
        self.risk_metrics = {
            "win_rate": 0.5,
            "avg_win": 1.0,
            "avg_loss": 1.0,
            "volatility": 0.02,
            "max_drawdown": 0.0
        }
    
    def calculate_position_size(self, account_balance, risk_percentage=None):
        """Calculate position size based on risk parameters"""
        if risk_percentage is None:
            risk_percentage = self.max_risk_per_trade
            
        # Ensure we don't exceed portfolio risk limits
        available_risk = min(
            risk_percentage,
            self.max_portfolio_risk - self.current_portfolio_risk,
            self.max_daily_loss - abs(self.daily_pnl)
        )
        
        if available_risk <= 0:
            return 0
        
        # Calculate position size
        risk_amount = account_balance * available_risk
        position_size = risk_amount
        
        return max(0, position_size)
    
    def calculate_stop_loss(self, entry_price, direction, atr=None):
        """Calculate stop loss level"""
        if direction.lower() in ['long', 'buy']:
            if atr:
                stop_loss = entry_price - (1.5 * atr)
            else:
                stop_loss = entry_price * 0.98  # 2% stop loss
        else:  # short/sell
            if atr:
                stop_loss = entry_price + (1.5 * atr)
            else:
                stop_loss = entry_price * 1.02  # 2% stop loss
        
        return stop_loss
    
    def calculate_take_profit(self, entry_price, direction, risk_reward_ratio=None):
        """Calculate take profit level based on risk-reward ratio"""
        if risk_reward_ratio is None:
            risk_reward_ratio = self.risk_reward_ratio
            
        # First, calculate the stop loss to determine risk
        stop_loss = self.calculate_stop_loss(entry_price, direction)
        risk = abs(entry_price - stop_loss)
        
        if direction.lower() in ['long', 'buy']:
            take_profit = entry_price + (risk * risk_reward_ratio)
        else:  # short/sell
            take_profit = entry_price - (risk * risk_reward_ratio)
        
        return take_profit
    
    def validate_trade(self, entry_price, stop_loss, take_profit, direction):
        """Validate if a trade meets risk management criteria"""
        try:
            # Calculate risk and reward
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            
            if risk == 0:
                return False, "Invalid stop loss - no risk defined"
            
            # Calculate risk-reward ratio
            rr_ratio = reward / risk
            
            # Check minimum RR ratio
            if rr_ratio < self.risk_reward_ratio:
                return False, f"RR ratio {rr_ratio:.2f} below minimum {self.risk_reward_ratio}"
            
            # Check direction consistency
            if direction.lower() in ['long', 'buy']:
                if take_profit <= entry_price or stop_loss >= entry_price:
                    return False, "Invalid levels for long position"
            else:  # short/sell
                if take_profit >= entry_price or stop_loss <= entry_price:
                    return False, "Invalid levels for short position"
            
            return True, f"Trade validated - RR: {rr_ratio:.2f}"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def update_risk_metrics(self, market_data, prediction_confidence):
        """Update risk metrics based on market conditions"""
        try:
            # Extract market volatility indicators
            btc_rsi = market_data.get("btc_rsi", 50)
            fear_greed = market_data.get("fear_greed", 50)
            if isinstance(fear_greed, dict):
                fear_greed = fear_greed.get("index", 50)
            
            # Calculate volatility score
            rsi_volatility = abs(btc_rsi - 50) / 50  # 0-1 scale
            sentiment_volatility = abs(fear_greed - 50) / 50  # 0-1 scale
            
            # Update volatility metric
            self.risk_metrics["volatility"] = (rsi_volatility + sentiment_volatility) / 2
            
            # Adjust risk based on confidence and volatility
            confidence_factor = min(1.0, prediction_confidence)
            volatility_factor = 1.0 - self.risk_metrics["volatility"]
            
            # Lower risk in high volatility, low confidence scenarios
            adjusted_risk = self.max_risk_per_trade * confidence_factor * volatility_factor
            self.max_risk_per_trade = max(0.005, adjusted_risk)  # Minimum 0.5% risk
            
        except Exception as e:
            print(f"[ERROR] Risk metrics update failed: {e}")
    
    def get_risk_summary(self):
        """Get current risk management summary"""
        return {
            "max_risk_per_trade": self.max_risk_per_trade,
            "risk_reward_ratio": self.risk_reward_ratio,
            "current_portfolio_risk": self.current_portfolio_risk,
            "daily_pnl": self.daily_pnl,
            "risk_metrics": self.risk_metrics,
            "open_positions": len(self.open_positions),
            "risk_capacity": self.max_portfolio_risk - self.current_portfolio_risk
        }
    
    def add_position(self, position_data):
        """Add a new position to risk tracking"""
        position = {
            "id": len(self.open_positions) + 1,
            "entry_price": position_data.get("entry_price"),
            "stop_loss": position_data.get("stop_loss"),
            "take_profit": position_data.get("take_profit"),
            "direction": position_data.get("direction"),
            "position_size": position_data.get("position_size"),
            "risk_amount": position_data.get("risk_amount"),
            "timestamp": datetime.now().isoformat()
        }
        
        self.open_positions.append(position)
        
        # Update portfolio risk
        risk_percentage = position_data.get("risk_amount", 0) / 100  # Assuming percentage
        self.current_portfolio_risk += risk_percentage
        
        return position["id"]
    
    def close_position(self, position_id, exit_price):
        """Close a position and update metrics"""
        for i, position in enumerate(self.open_positions):
            if position["id"] == position_id:
                # Calculate PnL
                entry = position["entry_price"]
                direction = position["direction"]
                
                if direction.lower() in ['long', 'buy']:
                    pnl_percentage = (exit_price - entry) / entry
                else:
                    pnl_percentage = (entry - exit_price) / entry
                
                # Update daily PnL
                self.daily_pnl += pnl_percentage
                
                # Remove from open positions
                self.open_positions.pop(i)
                
                # Update portfolio risk
                risk_amount = position.get("risk_amount", 0) / 100
                self.current_portfolio_risk -= risk_amount
                self.current_portfolio_risk = max(0, self.current_portfolio_risk)
                
                return pnl_percentage
        
        return None
    
    def check_daily_limits(self):
        """Check if daily risk limits are reached"""
        limits_status = {
            "daily_loss_limit": abs(self.daily_pnl) >= self.max_daily_loss,
            "portfolio_risk_limit": self.current_portfolio_risk >= self.max_portfolio_risk,
            "can_trade": True
        }
        
        limits_status["can_trade"] = not (
            limits_status["daily_loss_limit"] or 
            limits_status["portfolio_risk_limit"]
        )
        
        return limits_status
    
    def reset_daily_metrics(self):
        """Reset daily metrics (call at start of new trading day)"""
        self.daily_pnl = 0.0
        
        # Optional: Clear positions that should reset daily
        # This depends on your trading strategy
    
    def save_risk_state(self, filename="risk_state.json"):
        """Save current risk state to file"""
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "current_portfolio_risk": self.current_portfolio_risk,
                "daily_pnl": self.daily_pnl,
                "open_positions": self.open_positions,
                "risk_metrics": self.risk_metrics,
                "settings": {
                    "max_risk_per_trade": self.max_risk_per_trade,
                    "risk_reward_ratio": self.risk_reward_ratio,
                    "max_portfolio_risk": self.max_portfolio_risk,
                    "max_daily_loss": self.max_daily_loss
                }
            }
            
            with open(filename, "w") as f:
                json.dump(state, f, indent=4)
                
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to save risk state: {e}")
            return False
    
    def load_risk_state(self, filename="risk_state.json"):
        """Load risk state from file"""
        try:
            if not os.path.exists(filename):
                return False
                
            with open(filename, "r") as f:
                state = json.load(f)
            
            # Load state
            self.current_portfolio_risk = state.get("current_portfolio_risk", 0.0)
            self.daily_pnl = state.get("daily_pnl", 0.0)
            self.open_positions = state.get("open_positions", [])
            self.risk_metrics = state.get("risk_metrics", self.risk_metrics)
            
            # Load settings if available
            settings = state.get("settings", {})
            if settings:
                self.max_risk_per_trade = settings.get("max_risk_per_trade", self.max_risk_per_trade)
                self.risk_reward_ratio = settings.get("risk_reward_ratio", self.risk_reward_ratio)
                self.max_portfolio_risk = settings.get("max_portfolio_risk", self.max_portfolio_risk)
                self.max_daily_loss = settings.get("max_daily_loss", self.max_daily_loss)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to load risk state: {e}")
            return False

if __name__ == "__main__":
    # Test the risk manager
    rm = RiskManager()
    
    # Test position size calculation
    account_balance = 10000
    position_size = rm.calculate_position_size(account_balance)
    print(f"[TEST] Position size for $10k account: ${position_size:.2f}")
    
    # Test stop loss and take profit calculation
    entry_price = 45000
    stop_loss = rm.calculate_stop_loss(entry_price, "long")
    take_profit = rm.calculate_take_profit(entry_price, "long")
    
    print(f"[TEST] Entry: ${entry_price}, SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}")
    
    # Test trade validation
    valid, message = rm.validate_trade(entry_price, stop_loss, take_profit, "long")
    print(f"[TEST] Trade validation: {valid} - {message}")
    
    # Test risk summary
    summary = rm.get_risk_summary()
    print(f"[TEST] Risk summary: {summary}") 