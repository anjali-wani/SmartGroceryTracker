# Quick verification script for Gemini API key and entity resolution
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

api_key = os.getenv("GEMINI_API_KEY")

print("=" * 60)
print("  Smart Grocery Tracker — LLM Key Verification")
print("=" * 60)

if not api_key or not api_key.strip():
    print("❌ GEMINI_API_KEY is empty or not set in .env")
    print(f"   Please add your key to: {env_path}")
    print("   Example: GEMINI_API_KEY=AIzaSy...")
    sys.exit(1)

print(f"✅ Found GEMINI_API_KEY: {api_key[:6]}...{api_key[-4:]}")
print("📡 Connecting to Google Gemini API (gemini-3.1-flash-lite)...")

try:
    from google import genai
    client = genai.Client(api_key=api_key)
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents="Respond with only: 'Gemini API is active and healthy!'"
    )
    print(f"✅ Connection Successful! Response: {response.text.strip()}")

    print("\n🛒 Testing Grocery Entity Resolution on raw receipt text: 'ORG BBY BOK CHOY 1LB'...")
    from app.services.llm_resolver import resolve_with_gemini
    
    result = resolve_with_gemini("ORG BBY BOK CHOY 1LB", store_name="Trader Joe's")
    print("   --------------------------------------")
    print(f"   Canonical Name : {result.canonical_name}")
    print(f"   Category       : {result.category}")
    print(f"   Standard Unit  : {result.standard_unit}")
    print(f"   Bulk Item?     : {result.is_bulk}")
    print("   --------------------------------------")
    print("🎉 All LLM checks passed! Your key is fully functional.\n")

except Exception as e:
    print(f"❌ Gemini API Call Failed: {e}")
    print("   Please verify that your key is valid and has Gemini 2.5 Flash enabled.")
    sys.exit(1)
