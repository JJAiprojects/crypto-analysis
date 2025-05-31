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
        """Create comprehensive AI prompt using all 50+ data points"""
        
        # Extract all data safely
        crypto = market_data.get("crypto", {})
        technicals = market_data.get("technical_indicators", {})
        futures = market_data.get("futures", {})
        fear_greed = market_data.get("fear_greed", {})
        historical = market_data.get("historical_data", {})
        
        # Macroeconomic data
        m2_data = market_data.get("m2_supply", {})
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
        
        prompt = f"""You are a professional crypto trader with 15+ years experience. Provide a CONCISE 12-hour trading outlook.

MARKET DATA ({data_points_used}/47 indicators):
================================

🔸 CRYPTO PRICES & STRUCTURE
• BTC: ${f"{crypto.get('btc'):,}" if crypto.get('btc') else 'N/A'} USD
• ETH: ${f"{crypto.get('eth'):,}" if crypto.get('eth') else 'N/A'} USD  
• BTC Dominance: {btc_dominance:.1f}%
• Global Market Cap: ${market_cap_data[0] if market_cap_data[0] else 0:,.0f} USD ({market_cap_data[1] if market_cap_data[1] else 0:+.1f}% 24h)

🔸 TECHNICAL INDICATORS
BTC: Price ${f"{btc_data.get('price'):,}" if btc_data.get('price') else 'N/A'} | RSI {f"{btc_data.get('rsi14'):.1f}" if btc_data.get('rsi14') is not None else 'N/A'} | Signal: {btc_data.get('signal', 'N/A')} | Trend: {btc_data.get('trend', 'N/A')}
ETH: Price ${f"{eth_data.get('price'):,}" if eth_data.get('price') else 'N/A'} | RSI {f"{eth_data.get('rsi14'):.1f}" if eth_data.get('rsi14') is not None else 'N/A'} | Signal: {eth_data.get('signal', 'N/A')} | Trend: {eth_data.get('trend', 'N/A')}

🔸 MARKET SENTIMENT
• Fear & Greed: {fear_greed.get('index', 'N/A')} ({fear_greed.get('sentiment', 'N/A')})
• BTC Funding: {f"{btc_futures.get('funding_rate'):.3f}" if btc_futures.get('funding_rate') is not None else 'N/A'}% | ETH Funding: {f"{eth_futures.get('funding_rate'):.3f}" if eth_futures.get('funding_rate') is not None else 'N/A'}%

🔸 MACRO DATA
• Inflation: {f"{inflation_data.get('inflation_rate'):.1f}" if inflation_data.get('inflation_rate') is not None else 'N/A'}% | Fed Rate: {f"{rates_data.get('fed_rate'):.2f}" if rates_data.get('fed_rate') is not None else 'N/A'}%
• S&P 500: {f"{stock_indices.get('sp500'):,.0f}" if stock_indices.get('sp500') is not None else 'N/A'} | VIX: {f"{stock_indices.get('vix'):.1f}" if stock_indices.get('vix') is not None else 'N/A'}

REQUIRED FORMAT (be CONCISE):
============================

📊 EXECUTIVE SUMMARY
• Fear & Greed: [value]
• Scenario: [BULLISH/BEARISH/NEUTRAL] ([high/medium/low] confidence)
• Timeframe: [specific period focus]
• Bullish: [XX.X]% | Bearish: [XX.X]%
• Strongest Signal: [key factor]
• Volatility: [High/Medium/Low]

BTC ANALYSIS
💰 Current: $[price]
📈 Resistance: $[level]
📉 Support: $[level]
📊 RSI: [value]
📊 Signal: [BUY/SELL/NEUTRAL]
📈 Trend: [assessment]

🎯 BTC PLAN - [BULLISH/BEARISH/NEUTRAL]
• Entry: $[range]
• Target: $[price] ([+/-]X.X%)
• Stop: $[price] ([+/-]X.X%)
• R/R: [ratio]
• Confidence: [XX]% ([HIGH/MEDIUM/LOW])

ETH ANALYSIS  
💰 Current: $[price]
📈 Resistance: $[level]
📉 Support: $[level]
📊 RSI: [value]
📊 Signal: [BUY/SELL/NEUTRAL]
📈 Trend: [assessment]

🎯 ETH PLAN - [BULLISH/BEARISH/NEUTRAL]
• Entry: $[range]
• Target: $[price] ([+/-]X.X%)
• Stop: $[price] ([+/-]X.X%)
• R/R: [ratio]
• Confidence: [XX]% ([HIGH/MEDIUM/LOW])

STOP HERE. Do not add any market commentary, explanations, or disclaimers after the ETH plan.

Keep response under 800 words. Focus on actionable insights."""
        
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
        
        return count

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

    def format_ai_telegram_message(self, ai_result, market_data):
        """Format AI prediction for Telegram"""
        try:
            prediction = ai_result.get("prediction", "No prediction available")
            data_points = ai_result.get("data_points_used", 0)
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            # Get basic market context for the analysis section only
            fear_greed = market_data.get("fear_greed", {})
            fg_index = fear_greed.get("index", 0)
            
            message = f"""🤖 **AI PREDICTION** 🤖
━━━━━━━━━━━━━━━━━━━━

🧠 **AI Analysis**
{prediction}

━━━━━━━━━━━━━━━━━━━━
📈 Data Points: {data_points}/47
⏰ Generated: {timestamp}
🤖 AI-Only System (No Fallbacks)"""

            return message
            
        except Exception as e:
            print(f"[ERROR] Formatting AI Telegram message: {e}")
            return f"🤖 AI PREDICTION ERROR\n\nFailed to format prediction: {str(e)}\n\n⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

    def send_ai_telegram(self, ai_result, market_data, test_mode=False):
        """Send AI prediction via Telegram"""
        try:
            message = self.format_ai_telegram_message(ai_result, market_data)
            
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
            
            # Send message directly using the specific bot configuration
            from telegram_utils import TelegramBot
            bot = TelegramBot(bot_token=bot_token, chat_id=chat_id)
            result = bot.send_message(f"{prefix}{message}")
            
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
            
            # Save to database (primary storage for both test and production)
            try:
                from database_manager import db_manager
                # DISABLED: This conflicts with the main script's extraction-based saves
                # db_manager.save_prediction(prediction_data)
                print(f"[INFO] ✅ AI prediction data prepared ({'test mode' if test_mode else 'production mode'})")
                print(f"[INFO] Database save handled by main script through extraction")
                
                # Only create files in production mode or if running on local development
                if not test_mode and not os.getenv('RENDER'):
                    # Local development - create backup file
                    filename = f"ai_prediction_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
                    with open(filename, 'w') as f:
                        json.dump(prediction_data, f, indent=2, default=str)
                    print(f"[INFO] ✅ AI prediction backup saved to {filename}")
                elif test_mode:
                    print(f"[INFO] 🧪 Test mode - no file created (database only)")
                else:
                    print(f"[INFO] 🌐 Render.com - database only (no ephemeral files)")
                    
            except ImportError:
                print("[WARN] Database not available")
                
                # Only create files as fallback if not in test mode
                if not test_mode:
                    filename = f"ai_prediction_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
                    with open(filename, 'w') as f:
                        json.dump(prediction_data, f, indent=2, default=str)
                    print(f"[INFO] ✅ AI prediction saved to {filename} (database fallback)")
                else:
                    print(f"[WARN] 🧪 Test mode + no database - prediction not saved")
                    
            except Exception as e:
                print(f"[ERROR] Database preparation failed: {e}")
                
                # Only create files as fallback if not in test mode
                if not test_mode:
                    filename = f"ai_prediction_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
                    with open(filename, 'w') as f:
                        json.dump(prediction_data, f, indent=2, default=str)
                    print(f"[INFO] ✅ AI prediction saved to {filename} (database error fallback)")
                else:
                    print(f"[ERROR] 🧪 Test mode + database error - prediction not saved")
            
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