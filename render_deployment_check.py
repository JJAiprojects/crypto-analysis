#!/usr/bin/env python3

import os
import sys
import json
import importlib.util
from pathlib import Path

def check_file_exists(filepath, required=True):
    """Check if a file exists"""
    exists = Path(filepath).exists()
    status = "✅" if exists else ("❌" if required else "⚠️")
    requirement = "REQUIRED" if required else "OPTIONAL"
    print(f"  {status} {filepath} ({requirement})")
    return exists

def check_environment_variables():
    """Check if all required environment variables are properly configured"""
    print("\n🔧 ENVIRONMENT VARIABLES CHECK:")
    
    required_vars = [
        "OPENAI_API_KEY",
        "TELEGRAM_BOT_TOKEN", 
        "TELEGRAM_CHAT_ID"
    ]
    
    optional_vars = [
        "TEST_TELEGRAM_BOT_TOKEN",
        "TEST_TELEGRAM_CHAT_ID", 
        "FRED_API_KEY",
        "ALPHAVANTAGE_API_KEY",
        "COINMARKETCAL_API_KEY",
        "NEWS_API_KEY",
        "BINANCE_API_KEY",
        "BINANCE_SECRET",
        "ETHERSCAN_API_KEY",
        "POLYGON_API_KEY"
    ]
    
    missing_required = []
    missing_optional = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value and value not in ["YOUR_API_KEY", "YOUR_BOT_TOKEN", "YOUR_CHAT_ID"]:
            print(f"  ✅ {var}: CONFIGURED")
        else:
            print(f"  ❌ {var}: NOT CONFIGURED")
            missing_required.append(var)
    
    for var in optional_vars:
        value = os.getenv(var)
        if value and value not in ["YOUR_API_KEY", "YOUR_BOT_TOKEN", "YOUR_CHAT_ID"]:
            print(f"  ✅ {var}: CONFIGURED")
        else:
            print(f"  ⚠️ {var}: NOT CONFIGURED (optional)")
            missing_optional.append(var)
    
    return missing_required, missing_optional

def check_deployment_files():
    """Check if all deployment files are present"""
    print("\n📁 DEPLOYMENT FILES CHECK:")
    
    required_files = [
        "requirements.txt",
        "render.yaml",
        "6.py",
        "ai_predictor.py",
        "data_collector.py",
        "telegram_utils.py"
    ]
    
    optional_files = [
        ".gitignore",
        "README.md",
        "config.json"
    ]
    
    missing_required = []
    
    print("  Required files:")
    for file in required_files:
        if not check_file_exists(file, required=True):
            missing_required.append(file)
    
    print("  Optional files:")
    for file in optional_files:
        check_file_exists(file, required=False)
    
    return missing_required

def check_python_dependencies():
    """Check if all Python dependencies can be imported"""
    print("\n🐍 PYTHON DEPENDENCIES CHECK:")
    
    dependencies = [
        "requests",
        "pandas", 
        "numpy",
        "openai",
        "flask",
        "asyncio",
        "json",
        "datetime",
        "os",
        "time",
        "yfinance",
        "beautifulsoup4"
    ]
    
    missing_deps = []
    
    for dep in dependencies:
        try:
            # Handle special cases
            if dep == "beautifulsoup4":
                import bs4
                print(f"  ✅ {dep} (as bs4): Available")
            elif dep == "yfinance":
                import yfinance
                print(f"  ✅ {dep}: Available")
            else:
                __import__(dep)
                print(f"  ✅ {dep}: Available")
        except ImportError:
            print(f"  ❌ {dep}: NOT AVAILABLE")
            missing_deps.append(dep)
    
    return missing_deps

def check_requirements_txt():
    """Check if requirements.txt has all necessary dependencies"""
    print("\n📋 REQUIREMENTS.TXT CHECK:")
    
    required_packages = [
        "requests",
        "pandas", 
        "numpy",
        "openai",
        "flask",
        "python-dotenv",
        "yfinance",
        "beautifulsoup4",
        "aiohttp"
    ]
    
    try:
        with open("requirements.txt", "r", encoding="utf-8") as f:
            content = f.read().lower()
        
        missing_packages = []
        for package in required_packages:
            if package.lower() in content:
                print(f"  ✅ {package}: Listed")
            else:
                print(f"  ❌ {package}: NOT LISTED")
                missing_packages.append(package)
        
        return missing_packages
    except FileNotFoundError:
        print("  ❌ requirements.txt not found!")
        return required_packages

def check_render_yaml():
    """Check if render.yaml is properly configured"""
    print("\n⚙️ RENDER.YAML CHECK:")
    
    try:
        with open("render.yaml", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = {
            "cron service": "type: cron" in content,
            "python runtime": "python3" in content,
            "build command": "pip install -r requirements.txt" in content,
            "start command": "python 6.py" in content,
            "environment variables": "OPENAI_API_KEY" in content and "TELEGRAM_BOT_TOKEN" in content
        }
        
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
        
        return all(checks.values())
    except FileNotFoundError:
        print("  ❌ render.yaml not found!")
        return False

def check_code_structure():
    """Check if the main code files have proper structure"""
    print("\n🏗️ CODE STRUCTURE CHECK:")
    
    checks = []
    
    # Check 6.py
    try:
        with open("6.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        main_checks = {
            "Flask web service": "Flask" in content and "app.run" in content,
            "Environment detection": "os.getenv('PORT')" in content,
            "Async support": "asyncio.run" in content,
            "Error handling": "try:" in content and ("except Exception" in content or "except:" in content)
        }
        
        print("  6.py main file:")
        for check, passed in main_checks.items():
            status = "✅" if passed else "❌"
            print(f"    {status} {check}")
        
        checks.extend(main_checks.values())
    except FileNotFoundError:
        print("  ❌ 6.py not found!")
        checks.append(False)
    
    # Check ai_predictor.py
    try:
        with open("ai_predictor.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        ai_checks = {
            "OpenAI integration": "OpenAI" in content,
            "Telegram formatting": "format_ai_telegram_message" in content,
            "Error handling": "try:" in content and ("except Exception" in content or "except:" in content)
        }
        
        print("  ai_predictor.py:")
        for check, passed in ai_checks.items():
            status = "✅" if passed else "❌"
            print(f"    {status} {check}")
        
        checks.extend(ai_checks.values())
    except FileNotFoundError:
        print("  ❌ ai_predictor.py not found!")
        checks.append(False)
    
    return all(checks)

def main():
    """Run all deployment readiness checks"""
    print("🚀 RENDER.COM DEPLOYMENT READINESS CHECK")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Check 1: Environment Variables
    missing_required_env, missing_optional_env = check_environment_variables()
    if missing_required_env:
        all_checks_passed = False
        print(f"\n❌ Missing required environment variables: {', '.join(missing_required_env)}")
    
    # Check 2: Deployment Files
    missing_files = check_deployment_files()
    if missing_files:
        all_checks_passed = False
        print(f"\n❌ Missing required files: {', '.join(missing_files)}")
    
    # Check 3: Python Dependencies
    missing_deps = check_python_dependencies()
    if missing_deps:
        print(f"\n⚠️ Missing dependencies (may be available on Render): {', '.join(missing_deps)}")
    
    # Check 4: Requirements.txt
    missing_packages = check_requirements_txt()
    if missing_packages:
        print(f"\n❌ Missing packages in requirements.txt: {', '.join(missing_packages)}")
        all_checks_passed = False
    
    # Check 5: Render.yaml
    render_yaml_ok = check_render_yaml()
    if not render_yaml_ok:
        all_checks_passed = False
    
    # Check 6: Code Structure
    code_structure_ok = check_code_structure()
    if not code_structure_ok:
        all_checks_passed = False
    
    # Final Summary
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("🎉 DEPLOYMENT READY!")
        print("✅ All critical checks passed")
        print("📝 Next steps:")
        print("  1. Set environment variables in Render.com dashboard")
        print("  2. Push to GitHub repository")
        print("  3. Connect repository to Render.com")
        print("  4. Deploy!")
        
        if missing_optional_env:
            print(f"\n💡 Optional API keys not configured: {', '.join(missing_optional_env)}")
            print("   System will work with reduced functionality")
    else:
        print("❌ DEPLOYMENT NOT READY!")
        print("🔧 Please fix the issues above before deploying")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 