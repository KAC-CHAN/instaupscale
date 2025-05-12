
import os
import uuid
import asyncio
import instaloader
from pyrogram import Client, filters
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip

# === Your Telegram Bot API credentials ===
API_ID = 26788480       # Replace with your API ID
API_HASH = "858d65155253af8632221240c535c314"
BOT_TOKEN = "7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4"

# === Pyrogram Bot Setup ===
app = Client("insta_reel_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# === Function to download Instagram Reel ===
def download_instagram_reel(url: str, output_dir: str) -> str:
    loader = instaloader.Instaloader(dirname_pattern=output_dir, save_metadata=False, post_metadata_txt_pattern='')
    shortcode = url.split("/")[-2]  # e.g., 'CwQkfe1LXrO'
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    loader.download_post(post, target="reel")

    # Find the downloaded mp4
    for file in os.listdir(output_dir + "/reel"):
        if file.endswith(".mp4"):
            return os.path.join(output_dir, "reel", file)
    raise Exception("Video not found")

# === Function to add watermark ===
def add_watermark(video_path: str, output_path: str):
    clip = VideoFileClip(video_path)
    txt = TextClip("desi gadgets", fontsize=40, color='white', font="Arial-Bold")
    txt = txt.set_position(("center", "bottom")).set_duration(clip.duration)
    video = CompositeVideoClip([clip, txt])
    video.write_videofile(output_path, codec="libx264", audio_codec="aac")
    clip.close()

# === Telegram Handler ===
@app.on_message(filters.private & filters.text)
async def reel_handler(client, message):
    url = message.text.strip()
    if "instagram.com/reel/" not in url:
        await message.reply("❌ Please send a valid Instagram Reel URL.")
        return

    temp_dir = "downloads"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        await message.reply("⬇️ Downloading the reel... Please wait.")
        downloaded_path = download_instagram_reel(url, temp_dir)
        watermarked_path = os.path.join(temp_dir, f"watermarked_{uuid.uuid4().hex}.mp4")

        await message.reply("🖊️ Adding watermark...")
        add_watermark(downloaded_path, watermarked_path)

        await message.reply_video(watermarked_path, caption="✅ Here is your watermarked reel.")
    except Exception as e:
        await message.reply(f"⚠️ Error: {e}")
    finally:
        # Clean up
        for root, _, files in os.walk(temp_dir):
            for file in files:
                os.remove(os.path.join(root, file))

if __name__ == "__main__":
    app.run()
