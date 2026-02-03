#!/usr/bin/env python3
"""
Hotel AI Operations Assistant - Interactive Chat Test Script

Test conversations with the AI directly via OpenRouter API.
Supports multi-turn conversations with bilingual (Thai/English) responses.

Usage:
    python scripts/test_chat.py

Environment variables:
    OPENROUTER_API_KEY - OpenRouter API key
    APP_LLM_MODELNAME - Model to use (default: qwen/qwen3-max)
"""

import os
import sys
import time
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed. Run: pip install openai")
    sys.exit(1)

# Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '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')
MODEL_NAME = os.getenv('APP_LLM_MODELNAME', 'qwen/qwen3-max')
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

# Hotel Assistant System Prompt (Bilingual)
SYSTEM_PROMPT = """You are a helpful hotel assistant for a luxury hotel in Thailand.
You can communicate in both Thai and English. Respond in the same language the guest uses.

คุณเป็นผู้ช่วยโรงแรมหรูในประเทศไทย สามารถสื่อสารได้ทั้งภาษาไทยและอังกฤษ
ตอบกลับในภาษาเดียวกับที่แขกใช้

Your capabilities include:
- Checking room availability
- Making, confirming, updating, and canceling reservations
- Handling service requests (room service, spa, transportation, etc.)
- Providing information about hotel amenities and services
- Answering questions about check-in/check-out policies

ความสามารถของคุณ:
- ตรวจสอบห้องว่าง
- จอง ยืนยัน แก้ไข และยกเลิกการจอง
- รับคำขอบริการ (รูมเซอร์วิส สปา รถรับส่ง ฯลฯ)
- ให้ข้อมูลสิ่งอำนวยความสะดวกและบริการของโรงแรม
- ตอบคำถามเกี่ยวกับนโยบายเช็คอิน/เช็คเอาท์

Room Types Available:
1. Standard Room (ห้องสแตนดาร์ด) - 2,500 THB/night
2. Deluxe Room (ห้องดีลักซ์) - 4,500 THB/night
3. Suite (ห้องสวีท) - 8,500 THB/night
4. Penthouse (ห้องเพนท์เฮาส์) - 25,000 THB/night

Always be polite, professional, and helpful. Use appropriate Thai honorifics (ครับ/ค่ะ) when responding in Thai.
เป็นมืออาชีพ สุภาพ และเป็นประโยชน์เสมอ ใช้คำลงท้ายที่เหมาะสม (ครับ/ค่ะ) เมื่อตอบเป็นภาษาไทย

Today's date: """ + datetime.now().strftime("%Y-%m-%d")


def create_client():
    """Create OpenRouter client."""
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )


def chat(client, messages: list, user_input: str) -> str:
    """Send message and get response."""
    messages.append({"role": "user", "content": user_input})

    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        elapsed = time.time() - start_time
        assistant_message = response.choices[0].message.content

        # Add assistant response to history
        messages.append({"role": "assistant", "content": assistant_message})

        # Print stats
        usage = response.usage
        print(f"\n[{elapsed:.2f}s | Tokens: {usage.prompt_tokens}+{usage.completion_tokens}={usage.total_tokens}]")

        return assistant_message

    except Exception as e:
        print(f"\nError: {e}")
        return None


def print_welcome():
    """Print welcome message."""
    print("\n" + "=" * 60)
    print("Hotel AI Assistant - Interactive Chat Test")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    print(f"API: OpenRouter")
    print("-" * 60)
    print("Commands:")
    print("  /quit, /exit, /q - Exit the chat")
    print("  /clear, /reset   - Clear conversation history")
    print("  /help            - Show this help message")
    print("-" * 60)
    print("Start chatting! (Thai or English)")
    print("เริ่มสนทนาได้เลย! (ภาษาไทยหรืออังกฤษ)")
    print("=" * 60 + "\n")


def main():
    """Main chat loop."""
    print_welcome()

    # Initialize client and conversation
    client = create_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ['/quit', '/exit', '/q', 'quit', 'exit']:
                print("\nGoodbye! ลาก่อน!")
                break

            if user_input.lower() in ['/clear', '/reset']:
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                print("\n[Conversation cleared]")
                continue

            if user_input.lower() == '/help':
                print_welcome()
                continue

            # Get response
            response = chat(client, messages, user_input)
            if response:
                print(f"\nAssistant: {response}")

        except KeyboardInterrupt:
            print("\n\nGoodbye! ลาก่อน!")
            break
        except EOFError:
            print("\n\nGoodbye! ลาก่อน!")
            break


if __name__ == "__main__":
    main()
