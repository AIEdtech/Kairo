"""
Debug script — Show what happens during agent launch
"""

import sys
import os
import asyncio
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import AgentConfig, User, get_engine, create_session_factory
from services.agent_runtime import get_runtime_manager
from config import get_settings

settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)

async def main():
    db = SessionLocal()
    
    # Get agents (extract data while session is open)
    agents = db.query(AgentConfig).all()
    agent_data = [
        {
            "id": agent.id,
            "user_id": agent.user_id,
            "name": agent.name,
        }
        for agent in agents
    ]
    
    users_dict = {u.id: u for u in db.query(User).all()}
    db.close()
    
    print("\n" + "="*70)
    print("DEBUG: DETAILED AGENT LAUNCH")
    print("="*70)
    
    runtime_mgr = get_runtime_manager()
    
    for agent_info in agent_data:
        user = users_dict.get(agent_info["user_id"])
        user_name = user.full_name if user else "Unknown"
        
        print(f"\n📋 Launching: {agent_info['name']} ({user_name})")
        print(f"   Agent ID: {agent_info['id']}")
        print(f"   User ID: {agent_info['user_id']}")
        
        try:
            result = await runtime_mgr.launch_agent(agent_info["user_id"], agent_info["id"])
            print(f"   ✓ Success: {result.get('status')}")
            
            # Verify it's in RuntimeManager
            runtime = runtime_mgr.get_runtime(agent_info["id"])
            if runtime:
                print(f"   ✓ Confirmed in RuntimeManager (is_running={runtime.is_running})")
            else:
                print(f"   ✗ NOT in RuntimeManager (but launch returned success!)")
                
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            print(f"\n   Traceback:")
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("RUNTIME MANAGER STATE")
    print("="*70)
    print(f"Active agents: {runtime_mgr.active_count}")
    print(f"Loaded agents: {list(runtime_mgr._runtimes.keys())}")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
