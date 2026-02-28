"""
Launch agents via HTTP API with proper JWT authentication.
Run this before testing to load agents into RuntimeManager.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from models.database import AgentConfig, User, get_engine, create_session_factory
from services.auth import create_access_token
from config import get_settings

settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)

API_URL = "http://127.0.0.1:8000"

def main():
    db = SessionLocal()
    
    # Get all agents and users
    agents = db.query(AgentConfig).all()
    users_dict = {u.id: u for u in db.query(User).all()}
    
    print("\n" + "="*70)
    print("LAUNCHING AGENTS VIA API")
    print("="*70)
    
    if not agents:
        print("\n✗ No agents found. Create agents in the dashboard first.")
        db.close()
        return
    
    for agent in agents:
        user = users_dict.get(agent.user_id)
        user_name = user.full_name if user else "Unknown"
        
        print(f"\nLaunching: {agent.name} ({user_name})")
        print(f"  Agent ID: {agent.id}")
        print(f"  User ID: {agent.user_id}")
        
        try:
            # Generate JWT token for this user
            token = create_access_token(agent.user_id, user.email if user else "unknown")
            
            # Make HTTP request to launch endpoint with auth
            response = requests.post(
                f"{API_URL}/api/agents/{agent.id}/launch",
                headers={
                    "Authorization": f"Bearer {token}"
                },
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"  ✓ Launched successfully")
                print(f"    Status: {result.get('runtime', {}).get('status', 'unknown')}")
            else:
                print(f"  ✗ Failed: HTTP {response.status_code}")
                print(f"    {response.text[:200]}")
                
        except requests.exceptions.ConnectionError:
            print(f"  ✗ Cannot connect to {API_URL}")
            print(f"    Is uvicorn running? Start with: uvicorn api.main:app --reload")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    db.close()
    
    print("\n" + "="*70)
    print("AGENTS READY FOR TESTING")
    print("="*70)
    print("\nNow run the webhook test:")
    print("  python scripts/test_meeting_negotiation.py")
    print("\nWatch uvicorn logs for:")
    print("  - 'POST /webhooks/email HTTP/1.1' 200 OK")
    print("  - '[user_id] Meeting detected from ...'")
    print("  - 'Extracted time: HH:MM'")
    print("  - Email replies being sent")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
