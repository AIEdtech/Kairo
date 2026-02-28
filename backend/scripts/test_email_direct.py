"""
Direct test — try sending an email via Composio
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.composio_tools import ComposioClient
from models.database import User, get_engine, create_session_factory
from config import get_settings

settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)

async def main():
    db = SessionLocal()
    rajesh = db.query(User).filter(User.email == "rajesh@kairo.com").first()
    db.close()
    
    if not rajesh:
        print("❌ Rajesh user not found!")
        return
    
    print("\n" + "="*70)
    print("DIRECT EMAIL TEST")
    print("="*70)
    print(f"\nUser: {rajesh.full_name}")
    print(f"User ID: {rajesh.id}")
    
    # Create Composio client with Rajesh's entity
    composio = ComposioClient()
    entity_id = f"kairo_{rajesh.id}"
    print(f"Entity ID: {entity_id}")
    
    composio.initialize(entity_id)
    
    # Try to send an email
    print("\nAttempting to send test email...")
    success = await composio.send_email(
        to="kulkarniphani@gmail.com",
        subject="Test Email",
        body="This is a test email from Composio"
    )
    
    if success:
        print("✅ EMAIL SENT SUCCESSFULLY!")
    else:
        print("❌ Email send failed (check uvicorn logs for error details)")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
