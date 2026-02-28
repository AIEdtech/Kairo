"""
Direct webhook simulator — manually send a webhook payload like Gmail would
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
    
    if not rajesh:
        print("❌ Rajesh user not found")
        db.close()
        return
    
    print("\n" + "="*70)
    print("WEBHOOK SIMULATOR - Direct Email Processing")
    print("="*70)
    
    # Simulate the webhook payload that Gmail would send
    webhook_payload = {
        "integrationId": "gmail",
        "data": {
            "id": "18c8f2a4c8a98e78",
            "threadId": "18c8f2a4c8a98e78",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Can we meet at 3pm tomorrow? Would love to sync on the project.",
            "internalDate": "1709048736000",
            "payload": {
                "headers": [
                    {"name": "From", "value": vidya.email},
                    {"name": "To", "value": rajesh.email},
                    {"name": "Subject", "value": "Coffee chat tomorrow?"},
                    {"name": "Date", "value": "Thu, 27 Feb 2026 18:05:36 +0000"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": "Hi Rajesh, are you free for coffee at 3pm tomorrow? Would love to sync on the project.",
                        }
                    }
                ]
            }
        }
    }
    
    print(f"\nSimulating webhook from: {vidya.email}")
    print(f"To: {rajesh.email}")
    print(f"Subject: Coffee chat tomorrow?")
    print(f"Message: Hi Rajesh, are you free for coffee at 3pm tomorrow?")
    
    # Get runtime manager and Rajesh's agent
    runtime_mgr = get_runtime_manager()
    rajesh_agent = db.query(AgentConfig).filter(AgentConfig.user_id == rajesh.id).first()
    db.close()
    
    if not rajesh_agent:
        print("❌ Rajesh agent not found")
        return
    
    print(f"\nTarget agent: {rajesh_agent.name} (ID: {rajesh_agent.id})")
    print(f"Agent running? {runtime_mgr.is_running(rajesh_agent.id)}")
    
    # Get the runtime
    runtime = runtime_mgr.get_runtime(rajesh_agent.id)
    if not runtime:
        print("❌ Could not get runtime")
        return
    
    print("\n" + "-"*70)
    print("Processing webhook...")
    print("-"*70)
    
    try:
        # Call process_incoming which is what the webhook handler calls
        result = await runtime.process_incoming(
            source="email",
            sender=vidya.email,
            subject="Coffee chat tomorrow?",
            message="Hi Rajesh, are you free for coffee at 3pm tomorrow? Would love to sync on the project.",
        )
        
        print(f"\n✅ Webhook processed successfully!")
        print(f"\nResult:")
        print(json.dumps(result, indent=2, default=str))
        
    except Exception as e:
        print(f"\n❌ Error processing webhook:")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
If you see ✅ above:
  - Meeting was detected and processed
  - Auto-reply was sent
  - Check Rajesh's inbox for the reply (or spam folder)

If you see ❌ error:
  - That error is blocking webhook processing
  - Check uvicorn logs for more details
  - Look for "ERROR" or "Traceback" lines
""")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
