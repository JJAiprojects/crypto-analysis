# Crypto Analysis System

A comprehensive cryptocurrency analysis and prediction system that combines AI insights with technical analysis.

## Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your credentials:
```
# Production credentials
TELEGRAM_BOT_TOKEN=your_production_bot_token
TELEGRAM_CHAT_ID=your_production_chat_id

# Test credentials
TEST_TELEGRAM_BOT_TOKEN=your_test_bot_token
TEST_TELEGRAM_CHAT_ID=your_test_chat_id

# API Keys
OPENAI_API_KEY=your_openai_api_key
FRED_API_KEY=your_fred_api_key
ALPHAVANTAGE_API_KEY=your_alphavantage_api_key
```

## Testing

To test the system locally:

```bash
# Test the main prediction script
python 6.py --test

# Test the validation script
python validation_script.py --test
```

The `--test` flag will:
- Use test bot token
- Save data to test files (prefixed with "test_")
- Send messages to test chat

## Production

The system runs on Render.com with the following schedule:
- Main script: 1 AM and 1 PM UTC (8 AM and 8 PM Vietnam time)
- Validation script: Every hour

## Files

- `6.py`: Main prediction script
- `validation_script.py`: Validation and accuracy tracking
- `ml_enhancer.py`: Machine learning components
- `risk_manager.py`: Risk management system
- `config.json`: Non-sensitive configuration
- `.env`: Sensitive credentials (not in git) 