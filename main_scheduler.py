#!/usr/bin/env python3

import schedule
import time
import subprocess
import os
import sys
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

def run_analysis():
    """Run the main crypto analysis"""
    try:
        logging.info("Starting crypto analysis...")
        result = subprocess.run([sys.executable, "6.py"], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logging.info("Crypto analysis completed successfully")
            if result.stdout:
                logging.info(f"Output: {result.stdout}")
        else:
            logging.error(f"Crypto analysis failed with return code {result.returncode}")
            if result.stderr:
                logging.error(f"Error: {result.stderr}")
                
    except subprocess.TimeoutExpired:
        logging.error("Crypto analysis timed out after 5 minutes")
    except Exception as e:
        logging.error(f"Error running crypto analysis: {e}")

def run_validation():
    """Run the prediction validation"""
    try:
        logging.info("Starting prediction validation...")
        result = subprocess.run([sys.executable, "validation_script.py"], 
                              capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0:
            logging.info("Validation completed successfully")
            if result.stdout:
                logging.info(f"Output: {result.stdout}")
        else:
            logging.error(f"Validation failed with return code {result.returncode}")
            if result.stderr:
                logging.error(f"Error: {result.stderr}")
                
    except subprocess.TimeoutExpired:
        logging.error("Validation timed out after 3 minutes")
    except Exception as e:
        logging.error(f"Error running validation: {e}")

def main():
    """Main scheduler function"""
    logging.info("Starting MarketAI Crypto Analysis Scheduler")
    logging.info(f"Current time: {datetime.now()}")
    
    # Schedule main analysis twice daily (8 AM and 8 PM)
    schedule.every().day.at("08:00").do(run_analysis)
    schedule.every().day.at("20:00").do(run_analysis)
    
    # Schedule validation every hour (to check predictions)
    schedule.every().hour.do(run_validation)
    
    # Run initial analysis if starting for the first time
    current_hour = datetime.now().hour
    if current_hour in [8, 20]:  # If starting at prediction time
        logging.info("Running initial analysis...")
        run_analysis()
    
    # Run initial validation
    logging.info("Running initial validation...")
    run_validation()
    
    logging.info("Scheduler started. Waiting for scheduled tasks...")
    logging.info("Analysis schedule: 8:00 AM and 8:00 PM daily")
    logging.info("Validation schedule: Every hour")
    
    # Keep the scheduler running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logging.info("Scheduler stopped by user")
            break
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
            time.sleep(60)  # Continue running even if there's an error

if __name__ == "__main__":
    main() 