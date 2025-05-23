import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, accuracy_score
import joblib
import json
from datetime import datetime, timedelta
import os

class PredictionEnhancer:
    def __init__(self):
        self.direction_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.price_model = GradientBoostingRegressor(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_importance = {}
        self.model_metrics = {}
        
    def prepare_features(self, market_data):
        """Extract and prepare features from market data"""
        try:
            features = {}
            
            # Price metrics
            btc_price = market_data.get('btc_price', 0)
            eth_price = market_data.get('eth_price', 0)
            features['btc_price'] = float(btc_price[0] if isinstance(btc_price, tuple) else btc_price)
            features['eth_price'] = float(eth_price[0] if isinstance(eth_price, tuple) else eth_price)
            
            # Technical indicators
            btc_rsi = market_data.get('btc_rsi', 50)
            eth_rsi = market_data.get('eth_rsi', 50)
            features['btc_rsi'] = float(btc_rsi[0] if isinstance(btc_rsi, tuple) else btc_rsi)
            features['eth_rsi'] = float(eth_rsi[0] if isinstance(eth_rsi, tuple) else eth_rsi)
            
            # Market sentiment
            fear_greed = market_data.get('fear_greed', {})
            if isinstance(fear_greed, dict):
                features['fear_greed'] = float(fear_greed.get('index', 50))
            else:
                fear_greed = fear_greed[0] if isinstance(fear_greed, tuple) else fear_greed
                features['fear_greed'] = float(fear_greed if fear_greed is not None else 50)
            
            # Market metrics
            market_cap = market_data.get('market_cap', 0)
            btc_dominance = market_data.get('btc_dominance', 50)
            features['market_cap'] = float(market_cap[0] if isinstance(market_cap, tuple) else market_cap)
            features['btc_dominance'] = float(btc_dominance[0] if isinstance(btc_dominance, tuple) else btc_dominance)
            
            # Convert to numpy array
            feature_names = sorted(features.keys())
            feature_values = np.array([features[name] for name in feature_names])
            
            return feature_values.reshape(1, -1), feature_names
            
        except Exception as e:
            print(f"[ERROR] Feature preparation failed: {e}")
            return None, None
    
    def prepare_targets(self, prediction_data):
        """Extract target variables from prediction data"""
        targets = {}
        
        # Direction prediction (up/down/stagnant)
        direction_map = {
            'rally': 1,
            'dip': -1,
            'stagnation': 0
        }
        
        prediction_text = prediction_data['prediction'].lower()
        direction = 0
        for key, value in direction_map.items():
            if key in prediction_text:
                direction = value
                break
        
        targets['direction'] = direction
        
        # Price prediction (if available)
        if 'price_targets' in prediction_data:
            targets['price'] = prediction_data['price_targets'].get('target', 0)
        
        return targets
    
    def train_models(self, historical_data, prediction_history):
        """Train models on historical data"""
        try:
            # Prepare training data
            X = []
            y_direction = []
            y_price = []
            feature_names = None
            
            for pred in prediction_history:
                if 'market_data' not in pred or 'predictions' not in pred:
                    continue
                    
                market_data = pred['market_data']
                features, names = self.prepare_features(market_data)
                
                if features is not None:
                    X.append(features[0])
                    if feature_names is None:
                        feature_names = names
                    
                    # Get direction target
                    ai_pred = pred['predictions'].get('ai_prediction', '')
                    if 'bullish' in ai_pred.lower():
                        y_direction.append('bullish')
                    elif 'bearish' in ai_pred.lower():
                        y_direction.append('bearish')
                    else:
                        y_direction.append('neutral')
                    
                    # Get price target
                    if 'btc_price' in market_data:
                        y_price.append(float(market_data['btc_price']))
            
            if not X or not y_direction or not y_price:
                print("[WARN] Insufficient training data")
                return
            
            X = np.array(X)
            y_direction = np.array(y_direction)
            y_price = np.array(y_price)
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train models
            self.direction_model.fit(X_scaled, y_direction)
            self.price_model.fit(X_scaled, y_price)
            
            self.is_trained = True
            
            # Save model metrics
            metrics = {
                'last_training': datetime.now().isoformat(),
                'n_samples': len(X),
                'feature_names': feature_names,
                'feature_importance': dict(zip(feature_names, 
                                            self.direction_model.feature_importances_))
            }
            
            # Save metrics
            os.makedirs('models', exist_ok=True)
            with open('models/model_metrics.json', 'w') as f:
                json.dump(metrics, f, indent=4)
            
            return metrics
            
        except Exception as e:
            print(f"[ERROR] Model training failed: {e}")
            return None
    
    def predict(self, market_data):
        """Make predictions using trained models"""
        if not self.is_trained:
            print("[WARN] Models not trained yet. Returning default predictions.")
            return {
                'direction': {
                    'prediction': 'neutral',
                    'confidence': 0.5
                },
                'price': {
                    'prediction': market_data.get('btc_price', 0),
                    'confidence': 0.5
                }
            }
        
        try:
            # Prepare features
            features, feature_names = self.prepare_features(market_data)
            if features is None:
                raise ValueError("Failed to prepare features")
            
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Make predictions
            direction_pred = self.direction_model.predict(features_scaled)[0]
            direction_proba = self.direction_model.predict_proba(features_scaled)[0]
            price_pred = self.price_model.predict(features_scaled)[0]
            
            # Get confidence scores
            direction_confidence = float(max(direction_proba))
            
            return {
                'direction': {
                    'prediction': direction_pred,
                    'confidence': direction_confidence
                },
                'price': {
                    'prediction': float(price_pred),
                    'confidence': 0.7  # Placeholder confidence for price prediction
                }
            }
            
        except Exception as e:
            print(f"[ERROR] Prediction failed: {e}")
            return {
                'direction': {
                    'prediction': 'neutral',
                    'confidence': 0.5
                },
                'price': {
                    'prediction': market_data.get('btc_price', 0),
                    'confidence': 0.5
                }
            }
    
    def save_models(self, directory):
        """Save trained models and scaler"""
        if not self.is_trained:
            print("[WARN] No trained models to save")
            return
        
        try:
            os.makedirs(directory, exist_ok=True)
            
            joblib.dump(self.direction_model, f"{directory}/direction_model.joblib")
            joblib.dump(self.price_model, f"{directory}/price_model.joblib")
            joblib.dump(self.scaler, f"{directory}/scaler.joblib")
            
            print(f"[INFO] Models saved to {directory}")
            
        except Exception as e:
            print(f"[ERROR] Failed to save models: {e}")
    
    def load_models(self, directory):
        """Load trained models and scaler"""
        try:
            self.direction_model = joblib.load(f"{directory}/direction_model.joblib")
            self.price_model = joblib.load(f"{directory}/price_model.joblib")
            self.scaler = joblib.load(f"{directory}/scaler.joblib")
            
            self.is_trained = True
            print(f"[INFO] Models loaded from {directory}")
            
        except Exception as e:
            print(f"[ERROR] Failed to load models: {e}")
            self.is_trained = False 