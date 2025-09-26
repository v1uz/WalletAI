#!/usr/bin/env python3
"""
WalletAI Bot Setup Script
This script helps you quickly set up and configure the WalletAI Telegram bot
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*50)
    print(f" {text}")
    print("="*50)

def check_python_version():
    """Check if Python version is 3.8+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ is required!")
        print(f"   Your version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python version: {sys.version.split()[0]}")

def create_virtualenv():
    """Create virtual environment"""
    if os.path.exists("venv"):
        print("✅ Virtual environment already exists")
        return
    
    print("📦 Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
    print("✅ Virtual environment created")

def install_dependencies():
    """Install required packages"""
    print("📦 Installing dependencies...")
    
    # Determine pip path
    if os.name == 'nt':  # Windows
        pip_path = "venv\\Scripts\\pip.exe"
        python_path = "venv\\Scripts\\python.exe"
    else:  # Unix/Linux/MacOS
        pip_path = "venv/bin/pip"
        python_path = "venv/bin/python"
    
    # Upgrade pip
    subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)
    
    # Install requirements
    if os.path.exists("requirements.txt"):
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        print("✅ Dependencies installed")
    else:
        print("❌ requirements.txt not found!")
        return False
    
    return True

def create_env_file():
    """Create .env file from template"""
    if os.path.exists(".env"):
        print("⚠️  .env file already exists")
        response = input("   Do you want to recreate it? (y/N): ")
        if response.lower() != 'y':
            return
    
    print("\n📝 Setting up environment variables...")
    
    # Get bot token
    bot_token = input("Enter your Bot Token from @BotFather: ").strip()
    if not bot_token:
        print("❌ Bot token is required!")
        sys.exit(1)
    
    # Generate encryption key
    from cryptography.fernet import Fernet
    encryption_key = Fernet.generate_key().decode()
    
    # Create .env content
    env_content = f"""# Bot Configuration
BOT_TOKEN={bot_token}

# Database Configuration (SQLite for development)
DATABASE_URL=sqlite+aiosqlite:///./walletai.db

# Redis Configuration (Optional)
REDIS_URL=
USE_REDIS=false

# OpenAI API (Optional - for AI features)
OPENAI_API_KEY=

# Security
ENCRYPTION_KEY={encryption_key}

# Environment Settings
ENVIRONMENT=development
DEBUG=true

# Sentry Error Tracking (Optional)
SENTRY_DSN=
"""
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("✅ .env file created")
    print(f"   Encryption key generated: {encryption_key[:20]}...")

def create_directories():
    """Create necessary directories"""
    directories = [
        "logs",
        "data",
        "exports",
        "src/handlers/commands",
        "src/handlers/transactions",
        "src/handlers/reports",
        "src/handlers/budgets",
        "src/handlers/goals",
        "src/handlers/shared"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print("✅ Directory structure created")

def test_bot_connection():
    """Test if bot token is valid"""
    print("\n🔧 Testing bot connection...")
    
    try:
        import asyncio
        from dotenv import load_dotenv
        load_dotenv()
        
        # Test without importing project files to avoid config issues
        try:
            from aiogram import Bot
        except ImportError:
            print("⚠️  aiogram not installed properly")
            return False
        
        async def test():
            bot_token = os.getenv("BOT_TOKEN")
            if not bot_token:
                return False, "Bot token not found in .env"
            
            try:
                bot = Bot(token=bot_token)
                bot_info = await bot.get_me()
                await bot.session.close()
                return True, f"@{bot_info.username}"
            except Exception as e:
                return False, str(e)
        
        success, result = asyncio.run(test())
        
        if success:
            print(f"✅ Bot connected successfully: {result}")
            return True
        else:
            print(f"❌ Failed to connect: {result}")
            print(f"   Please verify your bot token is correct")
            return False
            
    except Exception as e:
        print(f"⚠️  Could not test connection: {str(e)}")
        print("   This is normal for first setup. The bot should still work.")
        return True  # Don't fail setup just because of test issues

def main():
    """Main setup function"""
    print_header("WalletAI Bot Setup")
    
    # Check Python version
    check_python_version()
    
    # Create virtual environment
    create_virtualenv()
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed: Could not install dependencies")
        sys.exit(1)
    
    # Create .env file
    create_env_file()
    
    # Create directories
    create_directories()
    
    # Test bot connection
    test_success = test_bot_connection()
    
    print_header("Setup Complete!")
    
    if test_success:
        print("\n✅ Your bot is ready to run!")
        print("\n📚 Next steps:")
        print("   1. Activate virtual environment:")
        if os.name == 'nt':  # Windows
            print("      .\\venv\\Scripts\\activate")
        else:
            print("      source venv/bin/activate")
        print("   2. Run the bot:")
        print("      python src/main.py")
        print("\n💡 Bot Commands:")
        print("   /start - Initialize bot")
        print("   /add - Add transaction")
        print("   /balance - Check balance")
        print("   /report - View reports")
        print("   /help - Show help")
    else:
        print("\n⚠️  Setup completed but bot connection failed.")
        print("   Please check your bot token and try again.")
    
    print("\n📖 For more information, see README.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)