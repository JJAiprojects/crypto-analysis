# Data Storage in Crypto Dual Prediction System

## 📊 **WHERE IS DATA STORED?**

### **1. Runtime Data (Temporary)**
- **Location**: In memory during script execution
- **Format**: Python dictionaries and objects
- **Lifespan**: Until script completes
- **Purpose**: Processing and analysis

### **2. Database Storage (Persistent)**
- **Location**: `crypto_predictions.db` (SQLite database)
- **What's Stored**:
  - ✅ **AI Predictions**: Complete predictions from OpenAI
  - ✅ **Calculation Predictions**: Mathematical analysis results
  - ✅ **Market Context**: BTC/ETH prices, Fear & Greed index, BTC dominance
  - ✅ **Metadata**: Timestamps, test_mode flags, data points used
  - ✅ **Performance Tracking**: Accuracy validation (if implemented)

### **3. JSON File Storage (Persistent)**
- **Location**: Current working directory
- **Files Created**:
  ```
  ai_prediction_YYYYMMDD_HHMMSS.json          # AI prediction results
  calculation_prediction_YYYYMMDD_HHMMSS.json # Calculation results  
  prediction_comparison_YYYYMMDD_HHMMSS.json  # Comparison summary
  ```
- **What's Stored**: Complete prediction data with all metadata

### **4. Historical Data Cache (Temporary)**
- **Location**: In memory during execution
- **What's Cached**:
  - ✅ **50+ Data Points**: All collected market data
  - ✅ **API Responses**: Raw data from CoinGecko, Binance, FRED, etc.
  - ✅ **Technical Analysis**: RSI, support/resistance, trends
  - ✅ **Macroeconomic Data**: M2 supply, inflation, interest rates
  - ✅ **Social Metrics**: GitHub stars, forum activity

---

## 🔍 **DETAILED DATA STORAGE BREAKDOWN**

### **Raw Market Data (Memory Only)**
```json
{
  "crypto": {
    "btc": 45000,
    "eth": 2800
  },
  "technical_indicators": {
    "BTC": {
      "price": 45000,
      "rsi14": 45.2,
      "signal": "BUY",
      "support": 44000,
      "resistance": 46000,
      "volatility": "medium"
    }
  },
  "fear_greed": {
    "index": 35,
    "sentiment": "Fear"
  },
  "m2_supply": {
    "m2_supply": 21000000000000,
    "m2_date": "2024-12-01"
  }
  // ... and 40+ more data points
}
```

### **Database Schema (crypto_predictions.db)**
```sql
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    test_mode BOOLEAN,
    type TEXT,  -- 'ai_prediction' or 'calculation_prediction'
    btc_price REAL,
    eth_price REAL,
    fear_greed INTEGER,
    btc_dominance REAL,
    data_points_used INTEGER,
    predictions_data TEXT,  -- JSON of full prediction
    created_at DATETIME,
    updated_at DATETIME
);
```

### **JSON File Structure**
```json
{
  "timestamp": "2025-05-30T10:42:23.123456+00:00",
  "type": "ai_prediction",
  "test_mode": true,
  "prediction": "Complete AI analysis text...",
  "model": "gpt-4",
  "data_points_used": 47,
  "market_context": {
    "btc_price": 45000,
    "eth_price": 2800,
    "fear_greed": 35,
    "btc_dominance": 52.5
  }
}
```

---

## 📁 **FILE LOCATIONS**

### **Local Development**
```
crypto-analysis/
├── crypto_predictions.db                    # SQLite database
├── ai_prediction_20250530_104223.json      # AI prediction
├── calculation_prediction_20250530_104224.json # Calc prediction
├── prediction_comparison_20250530_104225.json  # Summary
├── .env                                     # Your credentials
└── config.json                            # Optional settings
```

### **Render.com Deployment**
```
/opt/render/project/src/
├── crypto_predictions.db                    # Persistent SQLite
├── ai_prediction_*.json                    # Generated files
├── calculation_prediction_*.json           # Generated files
└── prediction_comparison_*.json            # Summary files
```

---

## 🗃️ **DATA RETENTION**

### **Database Records**
- ✅ **Persistent**: Stored indefinitely
- ✅ **Queryable**: Can filter by test_mode, date, type
- ✅ **Indexed**: Efficient searches by timestamp

### **JSON Files**
- ✅ **Accumulate**: New files created each run
- ⚠️ **Manual Cleanup**: Old files not automatically deleted
- ✅ **Backup**: Complete data backup in human-readable format

### **Memory Data**
- ❌ **Temporary**: Lost when script ends
- ✅ **Real-time**: Available during execution
- ✅ **Processing**: Used for analysis and predictions

---

## 🔍 **HOW TO ACCESS STORED DATA**

### **Query Database**
```python
import sqlite3

# Connect to database
conn = sqlite3.connect('crypto_predictions.db')
cursor = conn.cursor()

# Get all test predictions
cursor.execute("SELECT * FROM predictions WHERE test_mode = 1")
test_predictions = cursor.fetchall()

# Get recent predictions
cursor.execute("SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 10")
recent = cursor.fetchall()

conn.close()
```

### **Read JSON Files**
```python
import json
import glob

# Get all AI predictions
ai_files = glob.glob("ai_prediction_*.json")
for file in ai_files:
    with open(file, 'r') as f:
        prediction = json.load(f)
        print(f"Prediction: {prediction['prediction'][:100]}...")
```

### **View Files in Directory**
```bash
# List all prediction files
ls -la *prediction*.json

# View latest AI prediction
cat $(ls ai_prediction_*.json | tail -1)

# Count total predictions
ls *prediction*.json | wc -l
```

---

## 📊 **DATA FLOW SUMMARY**

```
1. API Calls → 2. Memory Cache → 3. Analysis → 4. Storage
   ↓              ↓               ↓           ↓
CoinGecko      Raw Data        AI/Calc     Database
Binance        50+ Points      Predictions  + JSON Files
FRED           Technical       Results      + Telegram
Alpha Vantage  Analysis        
GitHub         Social Data     
```

### **Storage Timeline**
1. **Collection**: Data fetched and cached in memory
2. **Processing**: AI and calculation analysis performed
3. **Database Save**: Predictions stored in SQLite
4. **File Backup**: JSON files created as backup
5. **Telegram Send**: Messages sent to appropriate groups
6. **Cleanup**: Memory cleared when script ends

---

## 💡 **TIPS**

- **Test vs Production**: Same storage format, marked with `test_mode` flag
- **File Organization**: Use timestamps to track prediction history
- **Database Queries**: Filter by date, test_mode, or prediction type
- **Backup Strategy**: JSON files serve as human-readable backups
- **Monitoring**: Check file timestamps to verify system is running 