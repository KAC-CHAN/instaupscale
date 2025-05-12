
import os
import re
import requests
from pyrogram import Client, filters
from bs4 import BeautifulSoup

# Initialize bot
app = Client(
    "instagram_reel_bot",
    bot_token="7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4",
    api_id=26788480,
    api_hash="858d65155253af8632221240c535c314"
)

# Regex pattern for Instagram Reel/POST URLs
INSTAGRAM_REGEX = r"(https?://)?(www\.)?instagram\.com/(reel|p)/([a-zA-Z0-9_-]+)/?.*"

def extract_shortcode(url: str) -> str | None:
    """Extract Instagram shortcode from URL"""
    match = re.search(INSTAGRAM_REGEX, url)
    return match.group(4) if match else None

def get_video_url(shortcode: str) -> str | None:
    """Get video URL from Instagram using Open Graph metadata"""
    url = f"https://www.instagram.com/reel/{shortcode}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        video_tag = soup.find("meta", property="og:video")
        
        return video_tag["content"] if video_tag else None
    except Exception as e:
        print(f"Error fetching video URL: {e}")
        return None

@app.on_message(filters.regex(INSTAGRAM_REGEX))
async def handle_reel(client, message):
    """Handle incoming Instagram URLs"""
    try:
        url = message.text
        shortcode = extract_shortcode(url)
        
        if not shortcode:
            await message.reply_text("❌ Invalid Instagram URL")
            return

        await message.reply_chat_action("upload_video")
        
        video_url = get_video_url(shortcode)
        if not video_url:
            await message.reply_text("❌ Could not fetch video URL")
            return

        # Download video
        temp_file = f"{shortcode}.mp4"
        with requests.get(video_url, stream=True) as r:
            r.raise_for_status()
            with open(temp_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # Send video to user
        await message.reply_video(
            temp_file,
            caption="📥 Downloaded via Instagram Reel Bot",
            supports_streaming=True
        )

        # Cleanup
        os.remove(temp_file)
        
    except Exception as e:
        await message.reply_text(f"⚠️ Error: {str(e)}")
    finally:
        await message.reply_chat_action("cancel")

if __name__ == "__main__":
    print("Bot started...")
    app.run()
