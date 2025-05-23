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
        self.confidence_adjustment_factor = 1.0
        self.risk_adjustment_factor = 1.0
        
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
        """Save trained models to directory"""
        try:
            os.makedirs(directory, exist_ok=True)
            
            if self.is_trained:
                joblib.dump(self.direction_model, f"{directory}/direction_model.joblib")
                joblib.dump(self.price_model, f"{directory}/price_model.joblib")
                joblib.dump(self.scaler, f"{directory}/scaler.joblib")
                print(f"[INFO] Models saved to {directory}")
            else:
                print("[WARN] Models not trained - cannot save")
                
        except Exception as e:
            print(f"[ERROR] Failed to save models: {e}")
    
    def incremental_learning(self, new_training_data):
        """Incrementally train models with new validation data"""
        try:
            if not new_training_data:
                print("[INFO] No new training data provided")
                return
            
            print(f"[INFO] Processing {len(new_training_data)} new training samples")
            
            # Extract features and targets from validation data
            X_new = []
            y_direction_new = []
            y_price_new = []
            
            for training_point in new_training_data:
                pred_data = training_point.get("prediction_data", {})
                validation_points = training_point.get("validation_points", [])
                actual_btc_price = training_point.get("actual_btc_price")
                
                # Extract market data for features
                market_data = pred_data.get("market_data", {})
                if not market_data:
                    continue
                
                features, _ = self.prepare_features(market_data)
                if features is None:
                    continue
                
                X_new.append(features[0])
                
                # Determine actual direction based on validation points
                targets_hit = [vp for vp in validation_points if vp["type"].startswith("PROFESSIONAL_TARGET")]
                stops_hit = [vp for vp in validation_points if vp["type"] == "PROFESSIONAL_STOP_LOSS"]
                
                if targets_hit and not stops_hit:
                    actual_direction = "bullish"
                elif stops_hit and not targets_hit:
                    actual_direction = "bearish"
                else:
                    actual_direction = "neutral"
                
                y_direction_new.append(actual_direction)
                
                # Use actual price for price prediction target
                if actual_btc_price:
                    y_price_new.append(float(actual_btc_price))
                else:
                    y_price_new.append(float(market_data.get("btc_price", 0)))
            
            if not X_new:
                print("[WARN] No valid training samples extracted")
                return
            
            # Convert to numpy arrays
            X_new = np.array(X_new)
            y_direction_new = np.array(y_direction_new)
            y_price_new = np.array(y_price_new)
            
            # If models are already trained, use them as base
            if self.is_trained:
                # Load existing models to continue training
                try:
                    # Scale new features
                    X_new_scaled = self.scaler.transform(X_new)
                    
                    # For incremental learning, we can retrain with partial_fit
                    # But RandomForest and GradientBoosting don't support partial_fit
                    # So we'll collect this data and retrain periodically
                    
                    # Save incremental data for future retraining
                    incremental_file = "models/incremental_data.json"
                    incremental_data = []
                    
                    if os.path.exists(incremental_file):
                        try:
                            with open(incremental_file, "r") as f:
                                incremental_data = json.load(f)
                        except:
                            incremental_data = []
                    
                    # Add new data
                    for i in range(len(X_new)):
                        incremental_data.append({
                            "features": X_new[i].tolist(),
                            "direction": y_direction_new[i],
                            "price": float(y_price_new[i]),
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Keep only last 100 incremental samples
                    incremental_data = incremental_data[-100:]
                    
                    # Save incremental data
                    with open(incremental_file, "w") as f:
                        json.dump(incremental_data, f, indent=4)
                    
                    print(f"[INFO] Saved {len(X_new)} incremental learning samples")
                    
                    # If we have enough incremental data, retrain models
                    if len(incremental_data) >= 20:
                        print("[INFO] Retraining models with incremental data")
                        self._retrain_with_incremental_data(incremental_data)
                    
                except Exception as e:
                    print(f"[ERROR] Incremental learning failed: {e}")
            else:
                print("[INFO] Models not yet trained, storing data for future training")
                
        except Exception as e:
            print(f"[ERROR] Incremental learning failed: {e}")
    
    def _retrain_with_incremental_data(self, incremental_data):
        """Retrain models with accumulated incremental data"""
        try:
            if len(incremental_data) < 10:
                print("[WARN] Insufficient incremental data for retraining")
                return
            
            # Extract features and targets
            X = []
            y_direction = []
            y_price = []
            
            for sample in incremental_data:
                X.append(sample["features"])
                y_direction.append(sample["direction"])
                y_price.append(sample["price"])
            
            X = np.array(X)
            y_direction = np.array(y_direction)
            y_price = np.array(y_price)
            
            # Scale features
            X_scaled = self.scaler.transform(X)
            
            # Retrain models with new data
            self.direction_model.fit(X_scaled, y_direction)
            self.price_model.fit(X_scaled, y_price)
            
            # Update metrics
            metrics = {
                'last_incremental_training': datetime.now().isoformat(),
                'incremental_samples': len(X),
                'model_updated': True
            }
            
            # Save updated models
            self.save_models("models")
            
            print(f"[INFO] Models retrained with {len(X)} incremental samples")
            
        except Exception as e:
            print(f"[ERROR] Incremental retraining failed: {e}")

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

    def learn_from_insights(self, insights):
        """Learn from deep analysis insights to improve future predictions"""
        try:
            print("[INFO] Processing deep learning insights for model improvement...")
            
            # Extract key patterns for model adjustment
            improvement_data = {
                "timestamp": datetime.now().isoformat(),
                "performance_metrics": insights.get("core_performance", {}),
                "best_setups": insights.get("setup_analysis", {}),
                "optimal_timing": insights.get("timing_analysis", {}),
                "market_conditions": insights.get("market_condition_analysis", {}),
                "psychological_patterns": insights.get("psychological_patterns", {}),
                "recommendations": insights.get("improvement_recommendations", [])
            }
            
            # Adjust model parameters based on insights
            self._adjust_model_parameters(improvement_data)
            
            # Update feature importance weights
            self._update_feature_weights(improvement_data)
            
            # Save insights for future reference
            insights_file = "models/learning_insights.json"
            os.makedirs("models", exist_ok=True)
            
            all_insights = []
            if os.path.exists(insights_file):
                try:
                    with open(insights_file, "r") as f:
                        all_insights = json.load(f)
                except Exception:
                    all_insights = []
            
            all_insights.append(improvement_data)
            
            # Keep only last 6 months of insights
            cutoff = datetime.now() - timedelta(days=180)
            all_insights = [insight for insight in all_insights 
                           if datetime.fromisoformat(insight["timestamp"]) > cutoff]
            
            with open(insights_file, "w") as f:
                json.dump(all_insights, f, indent=4)
            
            print(f"[INFO] ML models updated with insights - {len(all_insights)} historical insights stored")
            
        except Exception as e:
            print(f"[ERROR] Failed to learn from insights: {e}")
            import traceback
            traceback.print_exc()
    
    def _adjust_model_parameters(self, improvement_data):
        """Adjust model parameters based on performance insights"""
        performance = improvement_data.get("performance_metrics", {})
        
        # Adjust confidence thresholds based on calibration
        psychological = improvement_data.get("psychological_patterns", {})
        if psychological.get("overconfidence_bias", 0) > 0.3:
            # Reduce confidence scaling if overconfident
            self.confidence_adjustment_factor = max(0.8, self.confidence_adjustment_factor - 0.05)
            print(f"[INFO] Reduced confidence scaling to {self.confidence_adjustment_factor} due to overconfidence")
        elif psychological.get("confidence_calibration", 0) > 0.15:
            # Increase confidence scaling if well-calibrated
            self.confidence_adjustment_factor = min(1.2, self.confidence_adjustment_factor + 0.02)
            print(f"[INFO] Increased confidence scaling to {self.confidence_adjustment_factor} - good calibration")
        
        # Adjust risk parameters based on R-expectancy
        r_expectancy = performance.get("r_expectancy", 0)
        if r_expectancy < 0:
            self.risk_adjustment_factor = max(0.5, self.risk_adjustment_factor - 0.1)
            print(f"[INFO] Reduced risk factor to {self.risk_adjustment_factor} due to negative expectancy")
        elif r_expectancy > 0.3:
            self.risk_adjustment_factor = min(1.5, self.risk_adjustment_factor + 0.05)
            print(f"[INFO] Increased risk factor to {self.risk_adjustment_factor} - strong expectancy")
    
    def _update_feature_weights(self, improvement_data):
        """Update feature importance weights based on what's working"""
        best_setups = improvement_data.get("best_setups", {})
        market_conditions = improvement_data.get("market_conditions", {})
        
        # Analyze which signals are performing best
        if best_setups:
            # Extract signal types from best performing setups
            for setup_name, stats in best_setups.items():
                if stats.get("expectancy_score", 0) > 0.3:
                    # This setup is performing well, boost related features
                    if "volume" in setup_name.lower():
                        self._boost_feature_weight("volume_signals", 0.05)
                    if "momentum" in setup_name.lower():
                        self._boost_feature_weight("momentum_signals", 0.05)
                    if "sentiment" in setup_name.lower():
                        self._boost_feature_weight("sentiment_signals", 0.05)
                    if "confluence" in setup_name.lower():
                        self._boost_feature_weight("confluence_signals", 0.1)
        
        # Adjust based on market condition performance
        volatility_perf = market_conditions.get("volatility", {})
        if volatility_perf:
            best_vol = max(volatility_perf.items(), key=lambda x: x[1].get("win_rate", 0))
            if best_vol[1].get("win_rate", 0) > 0.6:
                vol_level = best_vol[0]
                if vol_level == "high":
                    self._boost_feature_weight("volatility_signals", 0.03)
                elif vol_level == "low":
                    self._boost_feature_weight("stability_signals", 0.03)
    
    def _boost_feature_weight(self, feature_category, boost_amount):
        """Boost the weight of a feature category"""
        if not hasattr(self, "feature_weights"):
            self.feature_weights = {}
        
        current_weight = self.feature_weights.get(feature_category, 1.0)
        new_weight = min(1.5, current_weight + boost_amount)  # Cap at 1.5x
        self.feature_weights[feature_category] = new_weight
        print(f"[INFO] Boosted {feature_category} weight to {new_weight:.3f}")
    
    def get_feature_weights(self):
        """Get current feature weights for model training"""
        return getattr(self, "feature_weights", {}) 