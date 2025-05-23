# 📅 Cron Job Setup Guide for Professional Crypto Analysis System

## 🚨 IMPORTANT: Your System Has Changed!

The professional crypto analysis system now requires different cron job configuration due to major enhancements.

## 🔧 What's New and Why Cron Jobs Need Updates:

1. **Environment Variables Required** - System now uses `.env` file for security
2. **New Dependencies** - ML models, professional analysis, additional Python packages
3. **Longer Execution Time** - Professional analysis takes more time
4. **New File Structure** - Models directory, new Python modules
5. **Enhanced Error Handling** - Better logging and failure detection

## 📋 Prerequisites Checklist:

### ✅ Before Setting Up Cron Jobs:

1. **Environment File** - Ensure `.env` file exists with:
   ```bash
   OPENAI_API_KEY=your_openai_key
   TELEGRAM_BOT_TOKEN=your_production_bot_token
   TELEGRAM_CHAT_ID=your_production_chat_id
   TEST_TELEGRAM_BOT_TOKEN=your_test_bot_token
   TEST_TELEGRAM_CHAT_ID=your_test_chat_id
   FRED_API_KEY=your_fred_key
   ALPHAVANTAGE_API_KEY=your_alphavantage_key
   ```

2. **Dependencies Installed**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Directory Structure**:
   ```
   crypto-analysis/
   ├── .env (CRITICAL!)
   ├── 6.py
   ├── professional_analysis.py
   ├── ml_enhancer.py
   ├── risk_manager.py
   ├── telegram_utils.py
   ├── models/ (will be created automatically)
   ├── run_main.sh
   ├── run_test.sh
   └── requirements.txt
   ```

## ⏰ Recommended Cron Schedule:

### Production Schedule (Institutional Grade):
```bash
# Professional Crypto Analysis - Morning Session (7 AM UTC / 2 PM Vietnam)
0 7 * * * /path/to/crypto-analysis/run_main.sh >> /var/log/crypto-analysis.log 2>&1

# Professional Crypto Analysis - Evening Session (19 PM UTC / 2 AM Vietnam)
0 19 * * * /path/to/crypto-analysis/run_main.sh >> /var/log/crypto-analysis.log 2>&1
```

### Alternative Schedules:

**High Frequency (Every 4 hours):**
```bash
0 */4 * * * /path/to/crypto-analysis/run_main.sh >> /var/log/crypto-analysis.log 2>&1
```

**Conservative (Once Daily):**
```bash
0 8 * * * /path/to/crypto-analysis/run_main.sh >> /var/log/crypto-analysis.log 2>&1
```

**Test Mode (for debugging):**
```bash
*/15 * * * * /path/to/crypto-analysis/run_test.sh >> /var/log/crypto-test.log 2>&1
```

## 🛠️ Setting Up Cron Jobs:

### 1. Edit Crontab:
```bash
crontab -e
```

### 2. Add Your Schedule:
```bash
# Professional Crypto Analysis System v2.0
# Morning analysis (7 AM UTC)
0 7 * * * cd /full/path/to/crypto-analysis && ./run_main.sh >> /var/log/crypto-analysis.log 2>&1

# Evening analysis (7 PM UTC)  
0 19 * * * cd /full/path/to/crypto-analysis && ./run_main.sh >> /var/log/crypto-analysis.log 2>&1

# Weekly test to ensure system is working (Sundays at 6 AM UTC)
0 6 * * 0 cd /full/path/to/crypto-analysis && ./run_test.sh >> /var/log/crypto-test.log 2>&1
```

### 3. Important Cron Environment Setup:
Add these lines at the top of your crontab:
```bash
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
HOME=/your/home/directory
```

## 🔍 Monitoring & Troubleshooting:

### Log File Locations:
- **Main logs**: `/var/log/crypto-analysis.log`
- **Test logs**: `/var/log/crypto-test.log`
- **System logs**: Check with `journalctl -f`

### Check Cron Status:
```bash
# View cron service status
systemctl status cron

# View recent cron jobs
grep CRON /var/log/syslog | tail -20

# Test your script manually
cd /path/to/crypto-analysis
./run_main.sh
```

### Common Issues & Solutions:

#### ❌ "Environment variables not found"
**Solution**: Make sure `.env` file exists and is readable
```bash
ls -la .env
cat .env  # Verify content
```

#### ❌ "Python module not found"
**Solution**: Install dependencies in the same environment cron uses
```bash
which python  # Check Python path
pip install -r requirements.txt
```

#### ❌ "Permission denied"
**Solution**: Make scripts executable
```bash
chmod +x run_main.sh run_test.sh
```

#### ❌ "No Telegram messages sent"
**Solution**: Verify bot tokens and chat IDs
```bash
./run_test.sh  # Test with test bot first
```

## 📊 Performance Expectations:

- **Execution Time**: 2-5 minutes (vs 30 seconds for old version)
- **Memory Usage**: 100-200MB (due to ML models)
- **Network**: Multiple API calls for comprehensive analysis
- **Success Rate**: Should be >95% with proper setup

## 🔄 Updating Your Existing Cron Jobs:

### If You Had Old Cron Jobs:
1. **Remove old entries**: `crontab -e` and delete old lines
2. **Clear old logs**: `sudo rm /var/log/old-crypto-*.log`
3. **Add new entries**: Use the schedules above
4. **Test thoroughly**: Run `./run_test.sh` first

### Migration Checklist:
- [ ] Old cron jobs removed
- [ ] New scripts tested manually
- [ ] Environment variables configured
- [ ] Dependencies installed
- [ ] New cron jobs added
- [ ] Test run successful
- [ ] Production run successful
- [ ] Logs monitoring setup

## 🚀 Production Deployment:

### Final Steps:
1. Test in test mode: `./run_test.sh`
2. Verify test messages received
3. Run production once manually: `./run_main.sh`
4. Verify production messages received
5. Add to cron
6. Monitor first few automated runs

Your professional crypto analysis system is now ready for automated institutional-grade trading analysis! 🏆 