#!/usr/bin/env python3

import os
import json
from datetime import datetime
from database_manager import db_manager

def test_database_integration():
    """Test database integration functionality"""
    print("=== DATABASE INTEGRATION TEST ===\n")
    
    # Check database health
    print("1. Testing database connection...")
    health = db_manager.health_check()
    print(f"   Database Available: {health['database_available']}")
    print(f"   Connection Type: {health['connection_type']}")
    print(f"   Tables Exist: {health['tables_exist']}")
    print(f"   Current Predictions: {health['total_predictions']}")
    print(f"   Current Insights: {health['total_insights']}")
    
    if health.get('error'):
        print(f"   Error: {health['error']}")
    
    print()
    
    # Test saving a prediction
    print("2. Testing prediction save...")
    test_prediction = {
        "date": "2025-05-23",
        "session": "test",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_data": {
            "btc_price": 110000.0,
            "eth_price": 2600.0,
            "btc_rsi": 65.5,
            "eth_rsi": 62.3,
            "fear_greed": 75
        },
        "predictions": {
            "ai_prediction": "Test prediction for database integration",
            "professional_analysis": {
                "primary_scenario": "bullish",
                "confidence_level": "medium"
            },
            "ml_predictions": {
                "direction": {"prediction": "bullish", "confidence": 0.7}
            }
        },
        "validation_points": [],
        "final_accuracy": None
    }
    
    success = db_manager.save_prediction(test_prediction)
    print(f"   Prediction Save Success: {success}")
    print()
    
    # Test loading predictions
    print("3. Testing prediction load...")
    predictions = db_manager.load_predictions(limit=3)
    print(f"   Loaded {len(predictions)} predictions")
    if predictions:
        latest = predictions[0]
        print(f"   Latest Prediction Date: {latest.get('date', 'Unknown')}")
        print(f"   Latest Session: {latest.get('session', 'Unknown')}")
    print()
    
    # Test saving learning insight
    print("4. Testing learning insight save...")
    test_insight = {
        "period_type": "test",
        "analysis_date": datetime.now().isoformat(),
        "performance_summary": {
            "overall_win_rate": "65%",
            "total_trades": 10,
            "r_expectancy": "0.25R"
        },
        "test_data": True
    }
    
    period = datetime.now().strftime("%Y-W%U")  # Weekly format
    insight_success = db_manager.save_learning_insight("test", period, test_insight)
    print(f"   Learning Insight Save Success: {insight_success}")
    print()
    
    # Test loading insights
    print("5. Testing learning insight load...")
    insights = db_manager.get_learning_insights("test")
    print(f"   Loaded {len(insights)} insights")
    if insights:
        latest_insight = insights[0]
        print(f"   Latest Insight Period: {latest_insight.get('period', 'Unknown')}")
        print(f"   Latest Insight Type: {latest_insight.get('insight_type', 'Unknown')}")
    print()
    
    # Test validation update
    print("6. Testing validation update...")
    if predictions:
        test_validation = [
            {
                "coin": "BTC",
                "type": "TEST_VALIDATION",
                "predicted_level": 110000,
                "actual_price": 110500,
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        update_success = db_manager.update_prediction_validation(
            predictions[0]["timestamp"], 
            test_validation, 
            0.8
        )
        print(f"   Validation Update Success: {update_success}")
    else:
        print("   Skipped - no predictions to update")
    print()
    
    # Final health check
    print("7. Final database status...")
    final_health = db_manager.health_check()
    print(f"   Final Predictions Count: {final_health['total_predictions']}")
    print(f"   Final Insights Count: {final_health['total_insights']}")
    print()
    
    print("=== TEST COMPLETED ===")
    
    # Summary
    if health['database_available']:
        print("✅ Database integration is WORKING")
        print(f"   - Connection: {health['connection_type']}")
        print(f"   - Engine: {health.get('engine_url', 'Unknown')}")
    else:
        print("⚠️  Database not available - using JSON fallback")
    
    return health['database_available']

if __name__ == "__main__":
    try:
        test_database_integration()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc() 