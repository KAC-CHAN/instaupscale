
from pyrogram import Client, filters
import instaloader
import requests
import subprocess
import os

# Telegram API credentials (replace with your values)
api_id = 26788480       # Your Telegram API ID
api_hash = "858d65155253af8632221240c535c314"  # Your API Hash
bot_token = "7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4"  # Your Bot Token

app = Client("insta_reel_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

@app.on_message(filters.text & filters.private)
async def reel_handler(client, message):
    url = message.text.strip()
    # Basic check for Instagram reel URL
    if "instagram.com/reel/" not in url:
        return  # ignore non-reel messages

    await message.reply("Processing your reel...")

    try:
        # Extract shortcode from URL
        shortcode = url.split("/reel/")[1].split("/")[0]
        # Use Instaloader to get the Post object (public reels only)
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        video_url = post.video_url or post.url  # direct video URL

        # Download video to local file
        input_path = f"{shortcode}_input.mp4"
        output_path = f"{shortcode}_watermarked.mp4"
        with requests.get(video_url, stream=True) as r:
            r.raise_for_status()
            with open(input_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # Add watermark using FFmpeg drawtext filter:contentReference[oaicite:5]{index=5}:
        # watermark text "desi gadgets", white font, black shadow, centered bottom
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf",
            "drawtext=text='desi gadgets':fontcolor=white:fontsize=24:shadowcolor=black:shadowx=2:shadowy=2:"
            "x=(w-text_w)/2:y=h-text_h-10",
            "-c:a", "copy", output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True)

        # Send the watermarked video back
        await app.send_video(message.chat.id, output_path)

    except Exception as e:
        await message.reply(f"Failed to process reel: {e}")

    finally:
        # Cleanup files
        for file in [input_path, output_path]:
            if os.path.exists(file):
                os.remove(file)

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
