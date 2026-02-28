"""
Diagnostic script — check if agents are ready to receive webhooks
"""

import sys
import os
import asyncio

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
    
    if not rajesh or not vidya:
        print("❌ Users not found")
        db.close()
        return
    
    print("\n" + "="*70)
    print("AGENT DIAGNOSTICS")
    print("="*70)
    
    # Check agents in DB
    print("\n1️⃣  DATABASE AGENTS")
    print("-"*70)
    rajesh_agent = db.query(AgentConfig).filter(AgentConfig.user_id == rajesh.id).first()
    vidya_agent = db.query(AgentConfig).filter(AgentConfig.user_id == vidya.id).first()
    
    if rajesh_agent:
        print(f"✓ Rajesh's agent:")
        print(f"  Name: {rajesh_agent.name}")
        print(f"  ID: {rajesh_agent.id}")
        print(f"  Status: {rajesh_agent.status}")
    else:
        print(f"✗ Rajesh has no agent")
    
    if vidya_agent:
        print(f"✓ Vidya's agent:")
        print(f"  Name: {vidya_agent.name}")
        print(f"  ID: {vidya_agent.id}")
        print(f"  Status: {vidya_agent.status}")
    else:
        print(f"✗ Vidya has no agent")
    
    db.close()
    
    # Check RuntimeManager
    print("\n2️⃣  RUNTIME MANAGER")
    print("-"*70)
    runtime_mgr = get_runtime_manager()
    
    if rajesh_agent:
        is_running = runtime_mgr.is_running(rajesh_agent.id)
        print(f"Rajesh's agent running? {is_running}")
        
        if is_running:
            runtime = runtime_mgr.get_runtime(rajesh_agent.id)
            print(f"  ✓ Runtime exists")
            print(f"  Composio initialized? {hasattr(runtime, '_composio') and runtime._composio is not None}")
        else:
            print(f"  ✗ NOT RUNNING - Agent won't receive webhooks!")
    
    if vidya_agent:
        is_running = runtime_mgr.is_running(vidya_agent.id)
        print(f"Vidya's agent running? {is_running}")
    
    # Suggest fix
    print("\n" + "="*70)
    print("WHAT TO DO NEXT")
    print("="*70)
    
    if rajesh_agent:
        if not runtime_mgr.is_running(rajesh_agent.id):
            print(f"""
❌ PROBLEM: Rajesh's agent is NOT RUNNING

To fix: Launch the agent via the dashboard or API:

1. Go to http://localhost:3000
2. Log in as rajesh@kairo.com (password: demo1234)
3. Click "Agents" in the left menu
4. Click "Launch Agent" button
5. Wait for status to show "Running"

OR via API:
  curl -X POST http://localhost:8000/api/agents/{rajesh_agent.id}/launch \\
    -H "Authorization: Bearer <token>"

Then send the test email again.
""")
        else:
            print(f"""
✅ GOOD: Rajesh's agent IS RUNNING

The agent is ready to receive webhooks.

When you send an email to {rajesh.email}:
1. Gmail will trigger a webhook to the backend
2. Backend will call detect_and_negotiate_meeting()
3. Auto-reply should be sent

Troubleshooting if still no reply:
- Check uvicorn logs for webhook reception (look for "Webhook received" or "Meeting detected")
- Make sure Gmail connection shows as True in debug_composio.py
- Check spam folder for auto-reply
""")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
