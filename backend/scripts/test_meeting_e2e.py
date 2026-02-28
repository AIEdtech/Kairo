"""
End-to-End Meeting Negotiation Test
Tests the complete flow: detect meeting intent → extract time → check calendar → send auto-reply
"""

import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agent_runtime import get_runtime_manager
from models.database import User, AgentConfig, get_engine, create_session_factory
from config import get_settings

settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)

async def main():
    db = SessionLocal()
    rajesh = db.query(User).filter(User.email == "rajesh@kairo.com").first()
    vidya = db.query(User).filter(User.email == "vidya@kairo.com").first()
    db.close()
    
    if not rajesh or not vidya:
        print("❌ Test users not found!")
        return
    
    print("\n" + "="*70)
    print("END-TO-END MEETING NEGOTIATION TEST")
    print("="*70)
    
    # Get runtime manager
    runtime_mgr = get_runtime_manager()
    
    # Ensure agents are running
    print(f"\n📍 Checking agent status...")
    db = SessionLocal()
    rajesh_agent = db.query(AgentConfig).filter(AgentConfig.user_id == rajesh.id).first()
    vidya_agent = db.query(AgentConfig).filter(AgentConfig.user_id == vidya.id).first()
    
    if not rajesh_agent or not vidya_agent:
        print("❌ Agent configs not found!")
        db.close()
        return
    
    print(f"   Rajesh's agent: {rajesh_agent.name} (ID: {rajesh_agent.id})")
    print(f"   Vidya's agent: {vidya_agent.name} (ID: {vidya_agent.id})")
    
    # Launch agents if not running
    if rajesh_agent.status.value != "running":
        print(f"\n🚀 Launching Rajesh's agent...")
        await runtime_mgr.launch_agent(rajesh.id, rajesh_agent.id)
    
    if vidya_agent.status.value != "running":
        print(f"🚀 Launching Vidya's agent...")
        await runtime_mgr.launch_agent(vidya.id, vidya_agent.id)
    
    db.close()
    
    # Get Rajesh's runtime
    rajesh_runtime = runtime_mgr.get_runtime(rajesh_agent.id)
    if not rajesh_runtime:
        print("❌ Could not get Rajesh's runtime!")
        return
    
    print(f"\n✅ Agents ready for testing")
    
    # Test Case 1: Simple meeting request with proposed time
    print("\n" + "-"*70)
    print("TEST 1: Meeting request with explicit time (3pm)")
    print("-"*70)
    
    test_email_1 = {
        "from": vidya.email,  # From Vidya
        "to": rajesh.email,   # To Rajesh
        "subject": "Coffee chat tomorrow?",
        "body": "Hi Rajesh, are you free for coffee at 3pm tomorrow? Would love to sync on the project.",
    }
    
    print(f"\nSending from: {test_email_1['from']}")
    print(f"Subject: {test_email_1['subject']}")
    print(f"Body: {test_email_1['body']}")
    print(f"\nProcessing meeting negotiation...")
    
    result = await rajesh_runtime.detect_and_negotiate_meeting(
        sender=test_email_1['from'],
        message=test_email_1['body'],
        subject=test_email_1['subject']
    )
    
    print(f"\n✉️  Result:")
    print(f"   Is Meeting: {result.get('is_meeting')}")
    print(f"   Action: {result.get('action')}")
    if result.get('reply'):
        print(f"   Reply: {result.get('reply')}")
    print(f"   Status: {result.get('status')}")
    
    # Test Case 2: Meeting request without specific time
    print("\n" + "-"*70)
    print("TEST 2: Meeting request without specific time (flexible)")
    print("-"*70)
    
    test_email_2 = {
        "from": vidya.email,
        "to": rajesh.email,
        "subject": "Let's schedule a meeting",
        "body": "Hey Rajesh, when would be a good time for us to meet next week?",
    }
    
    print(f"\nSending from: {test_email_2['from']}")
    print(f"Subject: {test_email_2['subject']}")
    print(f"Body: {test_email_2['body']}")
    print(f"\nProcessing meeting negotiation...")
    
    result2 = await rajesh_runtime.detect_and_negotiate_meeting(
        sender=test_email_2['from'],
        message=test_email_2['body'],
        subject=test_email_2['subject']
    )
    
    print(f"\n✉️  Result:")
    print(f"   Is Meeting: {result2.get('is_meeting')}")
    print(f"   Action: {result2.get('action')}")
    if result2.get('reply'):
        print(f"   Reply: {result2.get('reply')}")
    print(f"   Status: {result2.get('status')}")
    
    # Test Case 3: Non-meeting email (should not trigger meeting negotiation)
    print("\n" + "-"*70)
    print("TEST 3: Non-meeting email (should NOT trigger negotiation)")
    print("-"*70)
    
    test_email_3 = {
        "from": vidya.email,
        "to": rajesh.email,
        "subject": "Project update",
        "body": "The deployment was successful. All systems operational. Great work on the refactor!",
    }
    
    print(f"\nSending from: {test_email_3['from']}")
    print(f"Subject: {test_email_3['subject']}")
    print(f"Body: {test_email_3['body']}")
    print(f"\nProcessing meeting negotiation...")
    
    result3 = await rajesh_runtime.detect_and_negotiate_meeting(
        sender=test_email_3['from'],
        message=test_email_3['body'],
        subject=test_email_3['subject']
    )
    
    print(f"\n✉️  Result:")
    print(f"   Is Meeting: {result3.get('is_meeting')}")
    print(f"   Status: {result3.get('status')}")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"\n✅ Test 1 (With time): {'PASS' if result.get('is_meeting') else 'FAIL'}")
    print(f"✅ Test 2 (No time): {'PASS' if result2.get('is_meeting') else 'FAIL'}")
    print(f"✅ Test 3 (Non-meeting): {'PASS' if not result3.get('is_meeting') else 'FAIL'}")
    
    print("\n" + "="*70)
    print("INTERPRETATION")
    print("="*70)
    print("""
    If you see:
    - Test 1: is_meeting=True, action='accepted' or 'proposed' → ✅ Meeting detection working
    - Test 2: is_meeting=True, action='proposed' → ✅ Flexible time handling working  
    - Test 3: is_meeting=False → ✅ Non-meetings correctly ignored
    
    If emails are being sent, check your inbox for auto-replies!
    """)
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
