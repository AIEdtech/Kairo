"""
Debug Composio connections — check what's actually connected
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.composio_tools import ComposioClient
from models.database import User, get_engine, create_session_factory
from config import get_settings

settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)

db = SessionLocal()
users = db.query(User).all()
db.close()

print("\n" + "="*70)
print("COMPOSIO CONNECTIONS DEBUG")
print("="*70)

for user in users:
    print(f"\n👤 User: {user.full_name} ({user.email})")
    print(f"   User ID: {user.id}")
    
    # Create a Composio client and check connections
    composio = ComposioClient()
    
    # Test 1: Default entity
    print(f"\n   Testing entity: 'default'")
    composio.initialize("default")
    status = composio.get_connection_status()
    print(f"   Connections: {status}")
    
    # Test 2: Per-user entity (matches dashboard format)
    entity_id = f"kairo_{user.id}"
    print(f"\n   Testing entity: '{entity_id}'")
    composio2 = ComposioClient()
    composio2.initialize(entity_id)
    status2 = composio2.get_connection_status()
    print(f"   Connections: {status2}")

print("\n" + "="*70)
print("ACTION REQUIRED")
print("="*70)
print("\nIf all connections show False:")
print("1. Go to dashboard: http://localhost:3000")
print("2. Log in as each user")
print("3. Settings → Connect Gmail & Calendar")
print("4. Complete the OAuth flow")
print("5. Re-run this script to verify")
print("="*70 + "\n")
