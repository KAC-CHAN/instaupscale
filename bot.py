
import os
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Initialize bot with your token from BotFather
TOKEN = "7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Send /download [xHamster_URL] to download a video.')

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.split()[1]
    chat_id = update.effective_chat.id
    
    try:
        # Get video info and download using yt-dlp (modern fork of youtube-dl)
        await update.message.reply_text("Processing...")
        result = subprocess.run(
            ["yt-dlp", "-g", url],
            capture_output=True,
            text=True
        )
        video_url = result.stdout.strip()
        
        # Download the video
        await update.message.reply_text("Downloading...")
        temp_file = "video.mp4"
        subprocess.run(["wget", "-O", temp_file, video_url])
        
        # Send video to user (Telegram limits to 50MB)
        await update.message.reply_video(video=open(temp_file, 'rb'))
        
        # Cleanup
        os.remove(temp_file)
        
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")
        os.remove(temp_file) if os.path.exists(temp_file) else None

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download_video))
    app.run_polling()
