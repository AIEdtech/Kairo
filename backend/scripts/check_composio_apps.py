"""Check what Composio apps and actions are available"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
settings = get_settings()

# Method 1: Try ComposioToolSet to list apps
try:
    from composio import ComposioToolSet
    toolset = ComposioToolSet(api_key=settings.composio_api_key)
    
    # Try to get entity and list connections
    entity = toolset.get_entity("kairo_0da3b001-bb77-46dd-a4f7-2356533a22ed")
    print("Entity obtained successfully")
    
    # Check connections
    try:
        connections = entity.get_connections()
        print(f"\nConnections ({len(connections)}):")
        for c in connections:
            print(f"  {c}")
            print(f"  Type: {type(c)}")
            print(f"  Attrs: {[a for a in dir(c) if not a.startswith('_')]}")
    except Exception as e:
        print(f"get_connections error: {e}")
    
    # Try to initiate connection with string name
    print("\n--- Testing initiate_connection ---")
    try:
        conn = entity.initiate_connection(app_name="GMAIL")
        print(f"Gmail connection: {conn}")
        print(f"Type: {type(conn)}")
        print(f"Attrs: {[a for a in dir(conn) if not a.startswith('_')]}")
    except Exception as e:
        print(f"Gmail initiate error: {e}")
    
    try:
        conn = entity.initiate_connection(app_name="GOOGLECALENDAR")
        print(f"\nGoogleCalendar connection: {conn}")
    except Exception as e:
        print(f"GoogleCalendar initiate error: {e}")
    
    try:
        conn = entity.initiate_connection(app_name="GOOGLE_CALENDAR") 
        print(f"\nGoogle_Calendar connection: {conn}")
    except Exception as e:
        print(f"Google_Calendar initiate error: {e}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
