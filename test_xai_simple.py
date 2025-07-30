#!/usr/bin/env python3

import os
import requests
import json
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def test_xai_simple():
    """Test xAI API with a simple prompt"""
    
    # Get API key
    api_key = os.getenv("XAI_API_KEY")
    print(f"[DEBUG] XAI_API_KEY found: {'Yes' if api_key else 'No'}")
    if api_key:
        print(f"[DEBUG] API key starts with: {api_key[:10]}...")
    
    if not api_key:
        print("[ERROR] XAI_API_KEY not set")
        print("[DEBUG] Available environment variables:")
        for key, value in os.environ.items():
            if 'XAI' in key or 'API' in key:
                print(f"  {key}: {value[:10] if value else 'None'}...")
        return False
    
    print(f"[INFO] Testing xAI API with simple prompt...")
    
    # Simple API call
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "grok-4",
        "messages": [
            {
                "role": "user",
                "content": "Say hello in one sentence."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 50
    }
    
    try:
        print("[INFO] Making simple API call...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"[INFO] Status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"[SUCCESS] ✅ xAI API works! Response: {content}")
            return True
        else:
            print(f"[ERROR] API call failed: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out")
        return False
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return False

if __name__ == "__main__":
    test_xai_simple() 