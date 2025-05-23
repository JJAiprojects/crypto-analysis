# MarketAI Crypto Analysis - Render Deployment Guide

## Prerequisites

1. **Render Account**: Sign up at [render.com](https://render.com)
2. **OpenAI API Key**: Get from [platform.openai.com](https://platform.openai.com/api-keys)
3. **Telegram Bot**: Create via [@BotFather](https://t.me/botfather)
4. **GitHub Repository**: Push your code to GitHub

## Step 1: Prepare Your Repository

### 1.1 Required Files (Already Created)
- ✅ `requirements.txt` - Python dependencies
- ✅ `main_scheduler.py` - Main scheduler script
- ✅ `render.yaml` - Render configuration
- ✅ `runtime.txt` - Python version
- ✅ `env_example.txt` - Environment variables template

### 1.2 Push to GitHub
```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

## Step 2: Set Up Telegram Bot

### 2.1 Create Main Bot
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot`
3. Choose a name: `YourName MarketAI Bot`
4. Choose a username: `yourname_marketai_bot`
5. Save the **Bot Token**

### 2.2 Get Your Chat ID
1. Message your bot: `/start`
2. Visit: `https://api.telegram.org/bot{YOUR_BOT_TOKEN}/getUpdates`
3. Find your chat ID in the response
4. Save the **Chat ID**

### 2.3 Create Test Bot (Optional)
1. Repeat steps 2.1-2.2 for a test bot
2. Use different name: `YourName MarketAI Test Bot`

## Step 3: Deploy on Render

### 3.1 Create New Service
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Worker"**
3. Connect your GitHub repository
4. Select your crypto-analysis repository

### 3.2 Configure Service
- **Name**: `crypto-analysis`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main_scheduler.py`
- **Plan**: `Starter` (Free tier)

### 3.3 Set Environment Variables
Go to **Environment** tab and add:

#### Required Variables:
```
OPENAI_API_KEY=sk-your_actual_openai_key_here
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
TELEGRAM_CHAT_ID=your_actual_chat_id_here
```

#### Optional Variables:
```
TEST_TELEGRAM_BOT_TOKEN=your_test_bot_token_here
TEST_TELEGRAM_CHAT_ID=your_test_chat_id_here
FRED_API_KEY=your_fred_api_key_here
ALPHAVANTAGE_API_KEY=your_alphavantage_api_key_here
TZ=Asia/Ho_Chi_Minh
```

### 3.4 Deploy
1. Click **"Create Worker"**
2. Wait for deployment to complete
3. Check logs for any errors

## Step 4: Verify Deployment

### 4.1 Check Logs
1. Go to your service dashboard
2. Click **"Logs"** tab
3. Look for:
   ```
   Starting MarketAI Crypto Analysis Scheduler
   Analysis schedule: 8:00 AM and 8:00 PM daily
   Validation schedule: Every hour
   ```

### 4.2 Test Telegram Notifications
1. Wait for next hour (validation runs hourly)
2. Check your Telegram for validation messages
3. Wait for 8 AM or 8 PM for analysis messages

## Step 5: Monitor and Troubleshoot

### 5.1 Common Issues

#### "OpenAI API Key not configured"
- Check environment variable: `OPENAI_API_KEY`
- Ensure no extra spaces or quotes
- Verify key is valid at OpenAI platform

#### "Telegram credentials not configured"
- Check: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Verify bot token format: `123456789:ABCdef...`
- Verify chat ID is numerical

#### "Module not found" errors
- Check `requirements.txt` has all dependencies
- Redeploy if needed

#### Time zone issues
- Set `TZ=Asia/Ho_Chi_Minh` environment variable
- Times in logs should match your local time

### 5.2 Monitoring
- **Logs**: Real-time monitoring via Render dashboard
- **Telegram**: You'll receive notifications for system status
- **Performance**: Check logs for execution times

## Step 6: Schedule Overview

### Automatic Schedule
- **8:00 AM**: Market analysis + predictions
- **8:00 PM**: Market analysis + predictions  
- **Every hour**: Validation + accuracy reports
- **Sundays 8 PM**: Weekly deep analysis
- **1st of month 8 PM**: Monthly deep analysis

### Manual Testing
To test the system manually, check the logs and look for:
```
Starting crypto analysis...
Crypto analysis completed successfully
Starting prediction validation...
Validation completed successfully
```

## Step 7: Data Persistence

### Files Created (Stored on Render):
- `crypto_data_history.csv` - Historical market data
- `detailed_predictions.json` - AI predictions with metrics
- `deep_learning_insights.json` - Learning insights
- `ai_improvement_log.json` - Improvement suggestions
- `scheduler.log` - System logs

**Note**: Render's free tier has ephemeral storage. Files persist during runtime but may be lost on restart. For permanent storage, consider upgrading to paid plan with persistent disks.

## Step 8: Scaling and Optimization

### Free Tier Limits
- ✅ Sufficient for 2 daily analyses + hourly validation
- ✅ Handles all API calls and processing
- ✅ Good for testing and initial use

### Upgrade Considerations
- **Starter Plan ($7/month)**: More reliable, better performance
- **Standard Plan ($25/month)**: Persistent storage, more CPU/RAM

## Support

### If You Need Help:
1. Check Render logs first
2. Verify environment variables
3. Test Telegram bot separately
4. Check API key validity

### Expected Behavior:
- System starts automatically
- Runs 24/7 on schedule
- Sends Telegram notifications
- Learns and improves over time
- Professional trader-style reporting

### Success Indicators:
✅ Logs show successful starts
✅ Telegram messages received
✅ No error messages in logs
✅ Analysis runs at 8 AM/PM
✅ Validation runs hourly

## Next Steps

Once deployed and working:
1. Monitor for 24-48 hours
2. Check Telegram notifications
3. Review accuracy reports
4. System will start learning from data
5. Weekly/monthly insights will improve predictions

Your MarketAI system is now running professionally on cloud infrastructure! 🚀 