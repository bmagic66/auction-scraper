import os

def generate_config():
    """
    Generates frontend/config.js from environment variables.
    Falls back to .env file reading if vars not found in os.environ (local dev).
    """
    
    # Try to load from .env manually if not in environment
    # We do manual parsing to avoid strict dependency on python-dotenv for the build script
    if not os.environ.get("SUPABASE_URL") and os.path.exists(".env"):
        print("Loading from .env file...")
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

    # Get values
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    lambda_url = os.environ.get("LAMBDA_URL", "") # Optional

    # Create config content
    config_content = f"""const CONFIG = {{
    SUPABASE_URL: '{supabase_url}',
    SUPABASE_ANON_KEY: '{supabase_anon_key}',
    LAMBDA_URL: '{lambda_url}'
}};
"""

    # Write to file
    output_path = os.path.join("frontend", "config.js")
    with open(output_path, "w") as f:
        f.write(config_content)
    
    print(f"✅ Generated {output_path}")

if __name__ == "__main__":
    generate_config()
