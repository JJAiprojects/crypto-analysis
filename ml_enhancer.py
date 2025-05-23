#!/usr/bin/env python3

import json
import os
from datetime import datetime, timedelta
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error
import joblib

class PredictionEnhancer:
    """Machine Learning enhancer for crypto predictions"""
    
    def __init__(self):
        self.direction_model = None
        self.price_model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.confidence_adjustment_factor = 1.0
        self.risk_adjustment_factor = 1.0
        
    def predict(self, market_data):
        """Generate ML-enhanced predictions"""
        try:
            if not self.is_trained:
                return {"error": "Models not trained yet"}
                
            # Extract features from market data
            features = self._extract_features(market_data)
            if features is None:
                return {"error": "Could not extract features"}
                
            # Scale features
            features_scaled = self.scaler.transform([features])
            
            # Get predictions
            direction_prob = self.direction_model.predict_proba(features_scaled)[0]
            price_pred = self.price_model.predict(features_scaled)[0]
            
            # Determine direction
            if direction_prob[1] > 0.6:  # Bullish
                direction = "rally"
                confidence = direction_prob[1]
            elif direction_prob[0] > 0.6:  # Bearish
                direction = "decline"
                confidence = direction_prob[0]
            else:
                direction = "sideways"
                confidence = max(direction_prob)
            
            return {
                "direction": {
                    "prediction": direction,
                    "confidence": confidence * self.confidence_adjustment_factor
                },
                "price": {
                    "predicted_change": price_pred,
                    "confidence": confidence
                },
                "risk_factors": {
                    "volatility_risk": self._calculate_volatility_risk(market_data),
                    "sentiment_risk": self._calculate_sentiment_risk(market_data)
                }
            }
            
        except Exception as e:
            return {"error": f"Prediction failed: {str(e)}"}
    
    def train_models(self, historical_data, prediction_history):
        """Train ML models on historical data"""
        try:
            if len(prediction_history) < 10:
                print("[WARN] Not enough prediction history for training")
                return
                
            # Prepare training data
            X, y_direction, y_price = self._prepare_training_data(prediction_history)
            if len(X) < 5:
                print("[WARN] Not enough valid training samples")
                return
                
            # Split data
            X_train, X_test, y_dir_train, y_dir_test, y_price_train, y_price_test = train_test_split(
                X, y_direction, y_price, test_size=0.2, random_state=42
            )
            
            # Train scaler
            self.scaler.fit(X_train)
            X_train_scaled = self.scaler.transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train direction model
            self.direction_model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.direction_model.fit(X_train_scaled, y_dir_train)
            
            # Train price model
            self.price_model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.price_model.fit(X_train_scaled, y_price_train)
            
            # Evaluate models
            dir_accuracy = accuracy_score(y_dir_test, self.direction_model.predict(X_test_scaled))
            price_mse = mean_squared_error(y_price_test, self.price_model.predict(X_test_scaled))
            
            print(f"[INFO] Direction model accuracy: {dir_accuracy:.2f}")
            print(f"[INFO] Price model MSE: {price_mse:.4f}")
            
            self.is_trained = True
            
        except Exception as e:
            print(f"[ERROR] Model training failed: {e}")
    
    def incremental_learning(self, new_data):
        """Perform incremental learning with new data"""
        try:
            if not new_data:
                return
                
            print(f"[INFO] Processing {len(new_data)} new data points for incremental learning")
            
            # For now, just log the learning - full implementation would retrain models
            for data_point in new_data:
                validation_points = data_point.get("validation_points", [])
                if validation_points:
                    outcomes = [vp["type"] for vp in validation_points]
                    print(f"[INFO] Learning from outcomes: {outcomes}")
                    
        except Exception as e:
            print(f"[ERROR] Incremental learning failed: {e}")
    
    def learn_from_insights(self, insights):
        """Learn from deep analysis insights to adjust model parameters"""
        try:
            if "core_performance" not in insights:
                return
                
            core = insights["core_performance"]
            
            # Adjust confidence based on performance
            win_rate = core.get("win_rate", 0.5)
            r_expectancy = core.get("r_expectancy", 0)
            
            # Update adjustment factors
            self._adjust_model_parameters(win_rate, r_expectancy)
            
            # Update feature weights based on successful patterns
            if "setup_analysis" in insights:
                self._update_feature_weights(insights["setup_analysis"])
                
            print(f"[INFO] Model parameters adjusted based on insights")
            print(f"[INFO] Confidence adjustment: {self.confidence_adjustment_factor:.2f}")
            print(f"[INFO] Risk adjustment: {self.risk_adjustment_factor:.2f}")
            
        except Exception as e:
            print(f"[ERROR] Learning from insights failed: {e}")
    
    def save_models(self, model_dir):
        """Save trained models"""
        try:
            if not os.path.exists(model_dir):
                os.makedirs(model_dir)
                
            if self.direction_model:
                joblib.dump(self.direction_model, f"{model_dir}/direction_model.joblib")
            if self.price_model:
                joblib.dump(self.price_model, f"{model_dir}/price_model.joblib")
            if self.scaler:
                joblib.dump(self.scaler, f"{model_dir}/scaler.joblib")
                
            # Save adjustment factors
            with open(f"{model_dir}/adjustments.json", "w") as f:
                json.dump({
                    "confidence_adjustment_factor": self.confidence_adjustment_factor,
                    "risk_adjustment_factor": self.risk_adjustment_factor
                }, f)
                
            print(f"[INFO] Models saved to {model_dir}")
            
        except Exception as e:
            print(f"[ERROR] Failed to save models: {e}")
    
    def load_models(self, model_dir):
        """Load trained models"""
        try:
            direction_path = f"{model_dir}/direction_model.joblib"
            price_path = f"{model_dir}/price_model.joblib"
            scaler_path = f"{model_dir}/scaler.joblib"
            adjustments_path = f"{model_dir}/adjustments.json"
            
            if all(os.path.exists(p) for p in [direction_path, price_path, scaler_path]):
                self.direction_model = joblib.load(direction_path)
                self.price_model = joblib.load(price_path)
                self.scaler = joblib.load(scaler_path)
                self.is_trained = True
                
                # Load adjustment factors if available
                if os.path.exists(adjustments_path):
                    with open(adjustments_path, "r") as f:
                        adjustments = json.load(f)
                        self.confidence_adjustment_factor = adjustments.get("confidence_adjustment_factor", 1.0)
                        self.risk_adjustment_factor = adjustments.get("risk_adjustment_factor", 1.0)
                
                print(f"[INFO] Models loaded from {model_dir}")
                return True
            else:
                print(f"[WARN] Some model files missing in {model_dir}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to load models: {e}")
            return False
    
    def _extract_features(self, market_data):
        """Extract numerical features from market data"""
        try:
            features = []
            
            # Price features
            btc_price = market_data.get("btc_price", 0)
            eth_price = market_data.get("eth_price", 0)
            features.extend([btc_price, eth_price])
            
            # Technical indicators
            btc_rsi = market_data.get("btc_rsi", 50)
            eth_rsi = market_data.get("eth_rsi", 50)
            features.extend([btc_rsi, eth_rsi])
            
            # Fear & Greed
            fear_greed = market_data.get("fear_greed", 50)
            if isinstance(fear_greed, dict):
                fear_greed = fear_greed.get("index", 50)
            features.append(fear_greed)
            
            # Market cap and dominance
            market_cap = market_data.get("market_cap", 0) or 0
            btc_dominance = market_data.get("btc_dominance", 50) or 50
            features.extend([market_cap / 1e12, btc_dominance])  # Normalize market cap
            
            return features if len(features) == 7 else None
            
        except Exception as e:
            print(f"[ERROR] Feature extraction failed: {e}")
            return None
    
    def _prepare_training_data(self, prediction_history):
        """Prepare training data from prediction history"""
        X, y_direction, y_price = [], [], []
        
        for pred in prediction_history:
            # Extract features
            market_data = pred.get("market_data", {})
            features = self._extract_features(market_data)
            if features is None:
                continue
                
            # Extract target variables from validation points
            validation_points = pred.get("validation_points", [])
            if not validation_points:
                continue
                
            # Determine actual outcome
            outcome = self._determine_outcome(validation_points)
            if outcome is None:
                continue
                
            X.append(features)
            y_direction.append(outcome["direction"])
            y_price.append(outcome["price_change"])
        
        return np.array(X), np.array(y_direction), np.array(y_price)
    
    def _determine_outcome(self, validation_points):
        """Determine actual outcome from validation points"""
        # Simplified outcome determination
        for vp in validation_points:
            if vp["type"] in ["PROFESSIONAL_TARGET_1", "PROFESSIONAL_TARGET_2"]:
                predicted = vp.get("predicted_level", 0)
                actual = vp.get("actual_price", 0)
                if predicted and actual:
                    direction = 1 if actual > predicted else 0  # 1 = bullish, 0 = bearish
                    price_change = (actual - predicted) / predicted
                    return {"direction": direction, "price_change": price_change}
        return None
    
    def _calculate_volatility_risk(self, market_data):
        """Calculate volatility risk score"""
        # Simplified volatility risk calculation
        btc_rsi = market_data.get("btc_rsi", 50)
        fear_greed = market_data.get("fear_greed", 50)
        if isinstance(fear_greed, dict):
            fear_greed = fear_greed.get("index", 50)
        
        # Higher risk when RSI extreme or fear/greed extreme
        rsi_risk = max(0, abs(btc_rsi - 50) - 20) / 30
        sentiment_risk = max(0, abs(fear_greed - 50) - 25) / 25
        
        return min(1.0, (rsi_risk + sentiment_risk) / 2)
    
    def _calculate_sentiment_risk(self, market_data):
        """Calculate sentiment risk score"""
        fear_greed = market_data.get("fear_greed", 50)
        if isinstance(fear_greed, dict):
            fear_greed = fear_greed.get("index", 50)
        
        # Higher risk at extremes
        return abs(fear_greed - 50) / 50
    
    def _adjust_model_parameters(self, win_rate, r_expectancy):
        """Adjust model parameters based on performance"""
        # Adjust confidence based on win rate
        if win_rate > 0.7:
            self.confidence_adjustment_factor = min(1.2, self.confidence_adjustment_factor + 0.05)
        elif win_rate < 0.4:
            self.confidence_adjustment_factor = max(0.8, self.confidence_adjustment_factor - 0.05)
        
        # Adjust risk based on R-expectancy
        if r_expectancy > 0.3:
            self.risk_adjustment_factor = min(1.2, self.risk_adjustment_factor + 0.05)
        elif r_expectancy < 0:
            self.risk_adjustment_factor = max(0.7, self.risk_adjustment_factor - 0.1)
    
    def _update_feature_weights(self, setup_analysis):
        """Update feature importance based on successful setups"""
        # Simplified feature weight updating
        # In a full implementation, this would adjust model parameters
        best_setups = sorted(setup_analysis.items(), 
                           key=lambda x: x[1].get("expectancy_score", 0), reverse=True)
        
        if best_setups:
            print(f"[INFO] Best performing setup: {best_setups[0][0]}")

if __name__ == "__main__":
    # Test the enhancer
    enhancer = PredictionEnhancer()
    test_data = {
        "btc_price": 45000,
        "eth_price": 3000,
        "btc_rsi": 65,
        "eth_rsi": 58,
        "fear_greed": 45,
        "market_cap": 1.5e12,
        "btc_dominance": 52
    }
    
    result = enhancer.predict(test_data)
    print(f"[TEST] Prediction result: {result}") 