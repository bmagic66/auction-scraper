import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def get_client() -> Client:
    """Get Supabase client with service role key for Lambda operations."""
    url = os.getenv("SUPABASE_URL")
    # In Lambda, we always use the secret key because this is a backend process
    key = os.getenv("SUPABASE_SECRET_KEY")
    
    if not url:
        raise ValueError("Missing SUPABASE_URL environment variable")
    if not key:
        raise ValueError("Missing SUPABASE_SECRET_KEY environment variable")
        
    return create_client(url, key)
