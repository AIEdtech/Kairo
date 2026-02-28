"""
Test script — Mock webhook calls to test meeting negotiation locally

This script simulates incoming emails with meeting requests and
sends them to the local webhook endpoint to trigger meeting negotiation.

Usage:
  cd backend
  python scripts/test_meeting_negotiation.py

Expected output in uvicorn logs:
  - POST /webhooks/email HTTP/1.1 200 OK
  - [user_id] Meeting detected from ...
  - Extracted time: 15:00
  - Accepted meeting / Proposed alternatives / Declined
"""

import requests
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

WEBHOOK_URL = "http://127.0.0.1:8000/webhooks/email"


def create_email_payload(user_id: str, sender: str, subject: str, message: str) -> dict:
    """Create a realistic email webhook payload."""
    return {
        "user_id": user_id,
        "channel": "email",
        "sender": sender,
        "subject": subject,
        "message": message,
        "language": "en",
        "sentiment": 0.7,
        "estimated_confidence": 0.85,
        "timestamp": datetime.now().isoformat(),
        "summary": message[:100],
    }


def send_webhook(payload: dict, test_name: str):
    """Send a mock webhook request."""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print(f"{'='*70}")
    print(f"Sender: {payload['sender']}")
    print(f"Subject: {payload['subject']}")
    print(f"Message: {payload['message']}")

    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        print(f"\n✓ Response: {response.status_code} {response.text}")

        if response.status_code == 200:
            print("✓ WEBHOOK ACCEPTED (check uvicorn logs for processing)")
        else:
            print(f"✗ WEBHOOK ERROR: {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("✗ ERROR: Cannot connect to backend at http://127.0.0.1:8000")
        print("  Make sure uvicorn is running:")
        print("  cd backend && uvicorn api.main:app --reload")
    except Exception as e:
        print(f"✗ ERROR: {e}")


def main():
    print("\n" + "="*70)
    print("MEETING NEGOTIATION WEBHOOK TEST")
    print("="*70)
    print("\nThis test simulates incoming meeting request emails.")
    print("Watch the uvicorn logs for:")
    print("  - 'POST /webhooks/email HTTP/1.1' 200 OK")
    print("  - Meeting intent detection logs")
    print("  - Email reply sending logs")

    # Get user IDs from user input
    print("\n⚠️  IMPORTANT: Enter your test user IDs")
    print("Find them from: sqlite3 kairo.db \"SELECT id, email, full_name FROM user;\"")

    rajesh_input = input("\nEnter Rajesh's user ID: ").strip()
    vidya_input = input("Enter Vidya's user ID: ").strip()

    if not rajesh_input or not vidya_input:
        print("\n✗ User IDs are required. Exiting.")
        return

    RAJESH_USER_ID = rajesh_input
    VIDYA_USER_ID = vidya_input
    RAJESH_EMAIL = "kulkarniphani@gmail.com"
    VIDYA_EMAIL = "phanikulkarni7@gmail.com"

    # Test 1: Rajesh receives meeting request from Vidya
    print("\n\n📧 TEST 1: Rajesh receives meeting request at specific time")
    payload1 = create_email_payload(
        user_id=RAJESH_USER_ID,
        sender=VIDYA_EMAIL,
        subject="Can we schedule a meeting?",
        message="Hi Rajesh, can we meet at 3pm tomorrow to discuss the project? Let me know if that works.",
    )
    send_webhook(payload1, "Rajesh gets meeting at 3pm")
    time.sleep(2)

    # Test 2: Another meeting with different time
    print("\n\n📧 TEST 2: Meeting request at specific time")
    payload2 = create_email_payload(
        user_id=RAJESH_USER_ID,
        sender="john@example.com",
        subject="Quick sync?",
        message="Hey, are you free at 1:30 PM on Friday? Would love to sync up.",
    )
    send_webhook(payload2, "Meeting request at 1:30 PM")
    time.sleep(2)

    # Test 3: Vidya receives meeting request
    print("\n\n📧 TEST 3: Vidya receives meeting request")
    payload3 = create_email_payload(
        user_id=VIDYA_USER_ID,
        sender=RAJESH_EMAIL,
        subject="Let's grab coffee",
        message="Vidya, when are you free for coffee? Thinking tomorrow afternoon around 4pm?",
    )
    send_webhook(payload3, "Vidya gets coffee meeting request")
    time.sleep(2)

    # Test 4: Meeting request with keyword variation
    print("\n\n📧 TEST 4: Phone call request")
    payload4 = create_email_payload(
        user_id=RAJESH_USER_ID,
        sender="emma@example.com",
        subject="Available for a call?",
        message="Hi, want to jump on a call this afternoon at 2:00 PM? We can discuss the proposal.",
    )
    send_webhook(payload4, "Phone call request at 2:00 PM")
    time.sleep(2)

    # Test 5: Non-meeting email
    print("\n\n📧 TEST 5: Regular email (should NOT trigger meeting negotiation)")
    payload5 = create_email_payload(
        user_id=RAJESH_USER_ID,
        sender="newsletter@company.com",
        subject="Company Newsletter - February",
        message="Here are the latest updates from our company blog...",
    )
    send_webhook(payload5, "Regular email (no meeting intent)")

    print("\n\n" + "="*70)
    print("TESTS COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print("1. Check uvicorn logs for webhook processing")
    print("2. Look for:")
    print("   - '[user_id] Meeting detected from ...'")
    print("   - 'Extracted time: HH:MM'")
    print("   - 'Accepted meeting / Proposed alternatives / Declined'")
    print("3. Check if emails were sent (would be logged in Composio)")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
