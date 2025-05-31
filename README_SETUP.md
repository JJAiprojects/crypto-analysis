# Crypto Dual Prediction System - Setup Guide

## 🚀 **QUICK START**

### **1. Local Development Setup**

#### **Step 1: Create Environment File**
```bash
# Copy the template
cp env_template.txt .env

# Edit .env with your actual credentials
nano .env
```

#### **Step 2: Fill in Environment Variables**
```bash
# API Keys (Required)
OPENAI_API_KEY=sk-your-actual-openai-key
FRED_API_KEY=your-actual-fred-key
ALPHAVANTAGE_API_KEY=your-actual-alphavantage-key

# Production Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABC-your-production-bot-token
TELEGRAM_CHAT_ID=-1001234567890

# Test Telegram (Different bot and group!)
TEST_TELEGRAM_BOT_TOKEN=0987654321:XYZ-your-test-bot-token
TEST_TELEGRAM_CHAT_ID=-1009876543210
```

#### **Step 3: Install Dependencies**
```bash
pip install -r requirements.txt
```

#### **Step 4: Run the System**
```bash
# Production mode
python 6.py

# Test mode (uses test Telegram bot/group)
python 6.py --test

# Analysis only (no predictions sent)
python 6.py --analysis
```

---

## 🌐 **RENDER.COM DEPLOYMENT**

### **Step 1: Environment Variables Setup**
In your Render.com dashboard, set these environment variables:

| Variable | Value | Required |
|----------|-------|----------|
| `OPENAI_API_KEY` | sk-your-openai-key | ✅ Yes |
| `FRED_API_KEY` | your-fred-key | ✅ Yes |
| `ALPHAVANTAGE_API_KEY` | your-alphavantage-key | ✅ Yes |
| `TELEGRAM_BOT_TOKEN` | Production bot token | ✅ Yes |
| `TELEGRAM_CHAT_ID` | Production chat ID | ✅ Yes |
| `TEST_TELEGRAM_BOT_TOKEN` | Test bot token | ⚠️ Optional |
| `TEST_TELEGRAM_CHAT_ID` | Test chat ID | ⚠️ Optional |

### **Step 2: Deploy Configuration**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python 6.py`
- **Environment**: Python 3.11+

---

## 🧪 **TEST MODE EXPLAINED**

### **What Test Mode Does:**
✅ **IDENTICAL FUNCTIONALITY**: Full data collection, AI predictions, database saves, file creation  
✅ **SAME API CALLS**: OpenAI, CoinGecko, Binance, FRED, Alpha Vantage  
✅ **SAME FILE STRUCTURE**: Same filenames and content (marked with `test_mode: true`)  
✅ **SAME DATABASE**: Saves to same database (marked with `test_mode: true`)  

### **ONLY DIFFERENCE:**
🧪 **Different Telegram Bot**: Uses `TEST_TELEGRAM_BOT_TOKEN` instead of `TELEGRAM_BOT_TOKEN`  
🧪 **Different Chat Group**: Uses `TEST_TELEGRAM_CHAT_ID` instead of `TELEGRAM_CHAT_ID`  
🧪 **Message Prefix**: Adds `🧪 [TEST]` prefix to telegram messages  

### **Why This Design?**
- **Safe Testing**: Test messages don't clutter production channels
- **Full Validation**: Test mode validates entire system functionality
- **Easy Switching**: Single `--test` flag switches modes
- **Data Integrity**: Test data clearly marked in database and files

---

## 📱 **TELEGRAM SETUP**

### **Step 1: Create Bots**

#### **Production Bot:**
1. Message `@BotFather` on Telegram
2. Send `/newbot`
3. Name: "Crypto Prediction Bot"
4. Get token (format: `1234567890:ABC...`)
5. Save as `TELEGRAM_BOT_TOKEN`

#### **Test Bot:**
1. Message `@BotFather` again
2. Send `/newbot`  
3. Name: "Crypto Prediction TEST Bot"
4. Get token
5. Save as `TEST_TELEGRAM_BOT_TOKEN`

### **Step 2: Create Groups**

#### **Production Group:**
1. Create group: "Crypto Predictions"
2. Add production bot to group
3. Send a message in group
4. Visit: `https://api.telegram.org/bot<PRODUCTION_TOKEN>/getUpdates`
5. Find `"chat":{"id": -1001234567890}`
6. Save as `TELEGRAM_CHAT_ID`

#### **Test Group:**
1. Create group: "Crypto Predictions TEST"
2. Add test bot to group
3. Send a message in group
4. Visit: `https://api.telegram.org/bot<TEST_TOKEN>/getUpdates`
5. Find chat ID
6. Save as `TEST_TELEGRAM_CHAT_ID`

---

## 🔑 **API KEYS SETUP**

### **OpenAI API Key**
1. Visit: https://platform.openai.com/api-keys
2. Create new secret key
3. Copy key (starts with `sk-`)
4. Save as `OPENAI_API_KEY`

### **FRED API Key**
1. Visit: https://fred.stlouisfed.org/docs/api/api_key.html
2. Register for free account
3. Generate API key
4. Save as `FRED_API_KEY`

### **Alpha Vantage API Key**
1. Visit: https://www.alphavantage.co/support/#api-key
2. Get free API key
3. Save as `ALPHAVANTAGE_API_KEY`

---

## 🧪 **TESTING THE SYSTEM**

### **Run Comprehensive Tests**
```bash
# Test all components
python test_system.py

# Test mode demonstration
python test_mode_example.py --test
python test_mode_example.py --production
python test_mode_example.py --setup
```

### **Test Modes**
```bash
# Test with all functionality
python 6.py --test

# Production mode
python 6.py

# Data analysis only
python 6.py --analysis
```

---

## 📁 **FILE STRUCTURE**

### **Generated Files:**
```
ai_prediction_YYYYMMDD_HHMMSS.json          # AI predictions
calculation_prediction_YYYYMMDD_HHMMSS.json # Calculation predictions  
prediction_comparison_YYYYMMDD_HHMMSS.json  # Comparison summary
crypto_predictions.db                        # SQLite database
```

### **Configuration Files:**
```
.env                    # Your credentials (local only)
env_template.txt        # Template for .env
config.json            # Additional settings (optional)
```

---

## 🔍 **IDENTIFYING TEST vs PRODUCTION**

### **In Files:**
```json
{
  "timestamp": "2025-05-30T10:42:23.123456+00:00",
  "test_mode": true,  // ← This identifies test mode
  "type": "ai_prediction",
  "prediction": "..."
}
```

### **In Database:**
- Records contain `test_mode` field
- Query: `SELECT * FROM predictions WHERE test_mode = 1`

### **In Telegram:**
- **Production**: "📊 AI PREDICTION"
- **Test**: "🧪 [TEST] 📊 AI PREDICTION"

---

## ⚠️ **SECURITY NOTES**

### **Environment Variables:**
- ❌ **Never commit `.env` file to git**
- ✅ Use environment variables on render.com
- ✅ Rotate API keys periodically
- ✅ Keep test and production tokens separate

### **Telegram Security:**
- ✅ Use different groups for test and production
- ✅ Restrict bot permissions appropriately
- ✅ Monitor bot usage regularly

---

## 🐛 **TROUBLESHOOTING**

### **Common Issues:**

#### **"Missing environment variables"**
- Check `.env` file exists and has correct values
- Verify environment variables are set on render.com

#### **"Telegram configuration missing"**
- Verify bot tokens are correct
- Check chat IDs are negative numbers for groups
- Ensure bots are added to respective groups

#### **"AI prediction failed"**
- Check OpenAI API key is valid
- Verify sufficient OpenAI credits
- Check internet connectivity

#### **"Insufficient data points"**
- Check API keys for CoinGecko, FRED, Alpha Vantage
- Verify internet connectivity
- Try running `python 6.py --analysis` to debug

### **Support:**
- Check logs for detailed error messages
- Run test suite: `python test_system.py`
- Use analysis mode: `python 6.py --analysis` 