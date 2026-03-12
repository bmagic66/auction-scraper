#!/usr/bin/env python3
"""
One-time migration: Move all auction images from Supabase Storage to Cloudflare R2.

Usage:
    python migrate_images.py                  # Migrate all lots with Supabase image URLs
    python migrate_images.py --dry-run        # Preview what would be migrated
    python migrate_images.py --auction-id 5   # Migrate only a specific auction
"""
import os
import argparse
import requests
import boto3
from botocore.config import Config as BotoConfig
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_STORAGE_PREFIX = "supabase.co/storage"


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def get_supabase_client():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SECRET_KEY"),
    )


def extract_filename_from_url(url: str) -> str:
    """Extract the filename from a Supabase storage URL.

    Example: https://xxx.supabase.co/storage/v1/object/public/auction-images/5_1001.jpg
    Returns: 5_1001.jpg
    """
    return url.rstrip("/").split("/")[-1]


def migrate(auction_id=None, dry_run=False):
    db = get_supabase_client()
    bucket = os.getenv("R2_BUCKET_NAME", "auction-images")
    public_url = os.getenv("R2_PUBLIC_URL").rstrip("/")

    # Fetch lots with Supabase image URLs
    query = db.table("lots").select("id, image_url, auction_id, lot_number")
    if auction_id:
        query = query.eq("auction_id", auction_id)
    query = query.like("image_url", f"%{SUPABASE_STORAGE_PREFIX}%")

    result = query.execute()
    lots = result.data

    if not lots:
        print("No lots found with Supabase image URLs.")
        return

    print(f"Found {len(lots)} lots to migrate.")

    if dry_run:
        for lot in lots[:10]:
            filename = extract_filename_from_url(lot["image_url"])
            print(f"  Lot {lot['lot_number']} (auction {lot['auction_id']}): {filename}")
        if len(lots) > 10:
            print(f"  ... and {len(lots) - 10} more")
        return

    r2 = get_r2_client()
    migrated = 0
    failed = 0

    for i, lot in enumerate(lots):
        old_url = lot["image_url"]
        filename = extract_filename_from_url(old_url)
        new_url = f"{public_url}/{filename}"

        try:
            # 1. Download from Supabase
            resp = requests.get(old_url, timeout=15)
            resp.raise_for_status()
            image_bytes = resp.content

            # 2. Upload to R2
            r2.put_object(
                Bucket=bucket,
                Key=filename,
                Body=image_bytes,
                ContentType="image/jpeg",
            )

            # 3. Update database row
            db.table("lots").update({"image_url": new_url}).eq("id", lot["id"]).execute()

            migrated += 1

        except Exception as e:
            print(f"  FAILED lot {lot['id']} ({filename}): {e}")
            failed += 1

        if (i + 1) % 50 == 0 or (i + 1) == len(lots):
            print(f"  Progress: {i + 1}/{len(lots)} (migrated: {migrated}, failed: {failed})")

    print(f"\nMigration complete: {migrated} migrated, {failed} failed out of {len(lots)} total.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate images from Supabase Storage to Cloudflare R2")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--auction-id", type=int, help="Only migrate a specific auction")
    args = parser.parse_args()

    migrate(auction_id=args.auction_id, dry_run=args.dry_run)
