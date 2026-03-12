"""
Supabase database client for auction data storage.
Image storage uses Cloudflare R2.
"""
import os
import boto3
from botocore.config import Config as BotoConfig
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


def get_client(use_secret: bool = False) -> Client:
    """
    Get Supabase client instance.
    
    Args:
        use_secret: If True, use service_role key for admin operations.
                   If False, use anon key for regular operations.
    """
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    secret_key = os.getenv("SUPABASE_SECRET_KEY")
    
    if not url:
        raise ValueError("Missing SUPABASE_URL in .env file")
    
    if use_secret:
        if not secret_key:
            raise ValueError("Missing SUPABASE_SECRET_KEY in .env file")
        return create_client(url, secret_key)
    else:
        if not anon_key:
            raise ValueError("Missing SUPABASE_ANON_KEY in .env file")
        return create_client(url, anon_key)


def get_or_create_auction(client: Client, auction_url: str, auction_name: str = None) -> int:
    """Get existing auction or create new one. Returns auction ID."""
    # Check if auction already exists
    result = client.table("auctions").select("id").eq("auction_url", auction_url).execute()
    
    if result.data:
        return result.data[0]["id"]
    
    # Create new auction
    result = client.table("auctions").insert({
        "auction_url": auction_url,
        "auction_name": auction_name
    }).execute()
    
    return result.data[0]["id"]


def save_lot(client: Client, auction_id: int, lot_data: dict) -> dict:
    """Save or update a lot. Returns the saved lot data."""
    lot_data["auction_id"] = auction_id
    
    # Upsert (insert or update on conflict)
    result = client.table("lots").upsert(
        lot_data,
        on_conflict="auction_id,lot_number"
    ).execute()
    
    return result.data[0] if result.data else None


def _get_r2_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def upload_image(image_bytes: bytes, filename: str) -> str:
    """Upload image to Cloudflare R2. Returns public URL."""
    s3 = _get_r2_client()
    bucket = os.getenv("R2_BUCKET_NAME", "auction-images")

    s3.put_object(
        Bucket=bucket,
        Key=filename,
        Body=image_bytes,
        ContentType="image/jpeg",
    )

    public_url = os.getenv("R2_PUBLIC_URL").rstrip("/")
    return f"{public_url}/{filename}"


def get_lots_by_auction(client: Client, auction_id: int) -> list:
    """Get all lots for an auction."""
    result = client.table("lots").select("*").eq("auction_id", auction_id).execute()
    return result.data


def get_or_create_auction_by_catalogue(client: Client, catalogue_id: str, auction_url: str, auction_name: str = None) -> int:
    """Get existing auction by catalogue ID or create new one. Returns auction ID."""
    # Check if auction already exists by catalogue_id
    result = client.table("auctions").select("id").eq("catalogue_id", catalogue_id).execute()
    
    if result.data:
        auction_id = result.data[0]["id"]
        # If name is provided, update it
        if auction_name:
             client.table("auctions").update({"auction_name": auction_name}).eq("id", auction_id).execute()
        return auction_id
    
    # Create new auction with catalogue_id
    result = client.table("auctions").insert({
        "auction_url": auction_url,
        "auction_name": auction_name,
        "catalogue_id": catalogue_id
    }).execute()
    
    return result.data[0]["id"]


def save_catalogue_lot(client: Client, auction_id: int, lot_data: dict) -> dict:
    """Save a catalogue lot (pre-auction). Uses lot_guid as unique identifier."""
    from datetime import datetime, timezone
    
    lot_data["auction_id"] = auction_id
    lot_data["catalogue_scraped_at"] = datetime.now(timezone.utc).isoformat()
    
    # Upsert using lot_guid as the conflict key
    result = client.table("lots").upsert(
        lot_data,
        on_conflict="auction_id,lot_number"
    ).execute()
    
    return result.data[0] if result.data else None


def update_lot_results(client: Client, auction_id: int, lot_guid: str, results: dict) -> dict:
    """Update a lot with auction results (post-auction)."""
    from datetime import datetime, timezone
    
    results["results_scraped_at"] = datetime.now(timezone.utc).isoformat()
    
    result = client.table("lots").update(results).eq("auction_id", auction_id).eq("lot_guid", lot_guid).execute()
    
    return result.data[0] if result.data else None


def get_pending_lots(client: Client, auction_id: int) -> list:
    """Get all pending lots for an auction awaiting results."""
    result = client.table("lots").select("*").eq("auction_id", auction_id).eq("status", "pending").execute()
    return result.data

