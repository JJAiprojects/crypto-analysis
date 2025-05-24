# Database Integration Setup Guide

## Overview

The crypto analysis system now supports **persistent data storage** using PostgreSQL (on Render) or SQLite (locally). This solves the data loss issue on cloud platforms with ephemeral storage.

## Architecture

```
Local Development:
JSON Files ← fallback ← SQLite Database ← Python Scripts

Production (Render):
JSON Files ← fallback ← PostgreSQL ← Python Scripts
```

## Local Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test Database Locally
```bash
python test_database.py
```

Expected output:
```
✅ Database integration is WORKING
   - Connection: database
   - Engine: sqlite:///crypto_predictions.db
```

## Render.com Production Setup

### 1. Add PostgreSQL Database

1. **Go to Render Dashboard**
2. **Create PostgreSQL Database:**
   - Click "New +"
   - Select "PostgreSQL"
   - Choose plan (Free tier available)
   - Note the database name

### 2. Environment Variables

Render automatically provides `DATABASE_URL` for PostgreSQL services. Ensure these environment variables are set:

**Required:**
- `DATABASE_URL` - Automatically provided by Render PostgreSQL
- `OPENAI_API_KEY` - Your OpenAI API key
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

**Optional:**
- `BINANCE_API_KEY` - For enhanced data
- `COINMARKETCAP_API_KEY` - For market data

### 3. Connect Database to Web Service

1. **In your Web Service:**
   - Go to "Environment" tab
   - Add environment variable:
     - Key: `DATABASE_URL`
     - Value: `[Copy from your PostgreSQL service]`

2. **Or use Auto-Connect:**
   - In PostgreSQL service, go to "Connect"
   - Click "Connect to Web Service"
   - Select your crypto analysis web service

### 4. Deploy

The system will automatically:
- Detect `DATABASE_URL` environment variable
- Connect to PostgreSQL
- Create necessary tables
- Fall back to JSON files if database fails

## Database Schema

### Tables Created Automatically

**1. predictions**
```sql
- id (Primary Key)
- date, session, timestamp
- btc_price, eth_price, btc_rsi, eth_rsi, fear_greed
- predictions_data (JSON)
- validation_points (JSON)
- final_accuracy
- ml_processed, hourly_validated
- trade_metrics, risk_analysis (JSON)
```

**2. learning_insights**
```sql
- id (Primary Key)
- insight_type (weekly/monthly)
- period (2025-W20, 2025-05)
- data (JSON)
- created_at, updated_at
```

**3. prediction_history**
```sql
- id (Primary Key)
- timestamp
- prediction_data (JSON)
- accuracy_score
- created_at
```

## Migration from JSON Files

### Automatic Migration (Recommended)

When you first deploy with database, existing JSON data will remain as fallback. New data will go to database.

### Manual Migration (Optional)

If you want to migrate existing JSON data to database:

```python
from database_manager import db_manager
import json

# Load existing JSON data
with open('detailed_predictions.json', 'r') as f:
    predictions = json.load(f)

# Save each prediction to database
for pred in predictions:
    db_manager.save_prediction(pred)

print(f"Migrated {len(predictions)} predictions to database")
```

## Verification

### Test Database Connection

```bash
python test_database.py
```

### Check Health Status

Add this to any script:
```python
from database_manager import db_manager

health = db_manager.health_check()
print(f"Database Status: {health}")
```

### Monitor Logs

On Render, check your service logs for:
- `[INFO] Database initialized successfully!`
- `[INFO] Prediction saved to database successfully`
- `[ERROR]` messages if issues occur

## Benefits

### ✅ Solved Problems
- **Data Persistence**: No more data loss on Render restarts
- **Scalability**: PostgreSQL handles concurrent access
- **Reliability**: Automatic fallback to JSON files
- **Performance**: Faster queries for large datasets

### 📊 Enhanced Features
- **Learning History**: Persistent ML training data
- **Advanced Analytics**: Complex queries on prediction data
- **Backup Strategy**: JSON files remain as secondary storage

## Troubleshooting

### Database Connection Issues

1. **Check Environment Variables:**
   ```python
   import os
   print("DATABASE_URL:", os.getenv('DATABASE_URL'))
   ```

2. **Verify PostgreSQL Service:**
   - Ensure PostgreSQL service is running
   - Check connection info is correct

3. **Network Issues:**
   - Render PostgreSQL requires internal connection
   - External connections need IP whitelisting

### Fallback to JSON

If database fails, system automatically uses JSON files:
```
[ERROR] Database initialization failed: connection error
[INFO] Falling back to JSON file storage...
```

### Migration Issues

If you see duplicate data:
```python
# Clear database tables (careful!)
from database_manager import db_manager, Base
Base.metadata.drop_all(bind=db_manager.engine)
Base.metadata.create_all(bind=db_manager.engine)
```

## Cost Considerations

### Free Tier Limits
- **Render PostgreSQL Free**: 1GB storage, 100 hours/month
- **Sufficient for**: ~100,000 predictions + insights

### Scaling Options
- **Starter Plan**: $7/month - 10GB storage
- **Pro Plan**: $15/month - 100GB storage

## Support

For issues:
1. Check Render service logs
2. Run `python test_database.py` locally
3. Verify all environment variables are set
4. Check PostgreSQL service status

The system gracefully handles failures and will continue working with JSON files even if database is unavailable. 