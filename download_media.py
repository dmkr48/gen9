import os
import json
import hashlib
import requests
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# === CONFIGURATION ===
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(CURRENT_DIR, "json")
MEDIA_ROOT = os.path.join(CURRENT_DIR, "media")

# Discord CDN session (reuse connection for efficiency)
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Discord-Backup-Bot/1.0"
})

# Map content_type to file extension
EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}

def get_extension(attachment):
    """Determine file extension from content_type or filename fallback."""
    content_type = attachment.get("content_type", "").lower()
    if content_type in EXTENSION_MAP:
        return EXTENSION_MAP[content_type]
    
    # Fallback: extract from filename
    filename = attachment.get("filename", "")
    ext = Path(filename).suffix.lower()
    return ext if ext else ".bin"  # generic fallback

def url_hash(url):
    """Generate a consistent short hash from URL (ignores expiring query params)."""
    # Remove Discord's expiring tokens for consistent hashing
    parsed = urlparse(url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return hashlib.md5(clean_url.encode()).hexdigest()[:12]  # 12 chars = enough uniqueness

def download_file(url, dest_path):
    """Download file with basic error handling and skip if exists."""
    if os.path.exists(dest_path):
        print(f"  ⏭️  Skipping (exists): {Path(dest_path).name}")
        return True
    
    try:
        print(f"  ⬇️  Downloading: {Path(dest_path).name}")
        response = SESSION.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Basic validation: check file isn't empty
        if os.path.getsize(dest_path) == 0:
            print(f"  ❌ Empty file, removing: {Path(dest_path).name}")
            os.remove(dest_path)
            return False
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Failed to download {url}: {e}")
        return False

def process_json_file(json_path):
    """Process a single JSON file and download its attachments."""
    channel_id = None
    downloaded = 0
    skipped = 0
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {json_path}: {e}")
        return 0, 0
    
    # Handle both list of messages or dict with "messages" key
    messages = data if isinstance(data, list) else data.get("messages", [])
    
    for msg in messages:
        channel_id = channel_id or msg.get("channel_id")  # Grab channel_id from first message
        attachments = msg.get("attachments", [])
        
        for att in attachments:
            url = att.get("url")
            if not url:
                continue
            
            ext = get_extension(att)
            filename = f"{url_hash(url)}{ext}"
            channel_media_dir = Path(MEDIA_ROOT) / str(channel_id)
            channel_media_dir.mkdir(parents=True, exist_ok=True)
            
            dest_path = channel_media_dir / filename
            
            if download_file(url, str(dest_path)):
                downloaded += 1
            else:
                skipped += 1
            
            # Be nice to Discord's servers
            time.sleep(0.2)
    
    return downloaded, skipped

def main():
    print(f"📁 JSON Folder: {JSON_FOLDER}")
    print(f"📁 Media Output: {MEDIA_ROOT}\n")
    
    Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
    
    json_files = list(Path(JSON_FOLDER).glob("*.json"))
    if not json_files:
        print(f"⚠️  No JSON files found in {JSON_FOLDER}")
        return
    
    print(f"🔍 Found {len(json_files)} JSON file(s) to process\n")
    
    total_downloaded = 0
    total_skipped = 0
    
    for json_file in json_files:
        print(f"📄 Processing: {json_file.name}")
        downloaded, skipped = process_json_file(json_file)
        total_downloaded += downloaded
        total_skipped += skipped
        print(f"   ✅ {downloaded} downloaded, {skipped} skipped/failed\n")
    
    print(f"🎉 Done! Total: {total_downloaded} downloaded, {total_skipped} skipped/failed")
    print(f"📦 Media saved in: {MEDIA_ROOT}")

if __name__ == "__main__":
    main()