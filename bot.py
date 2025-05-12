import os
import logging
import tempfile
import subprocess
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import youtube_dl

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your Telegram Bot Token
Telegram_Token = OS.environ.get('7259559804:AAG3VoiBqnwn8_5BlK51U1UMvccj3urRIdk')

# Path to Real-ESRGAN executable or script
# Ensure you have Real-ESRGAN installed: pip install realesrgan
# or clone and install from https://github.com/xinntao/Real-ESRGAN
Realrgan_model = 'Realesrgan_x4Plus'  # default x4 model

# Download Instagram Reel using youtube_dl

def download_reel(url: str, output_path: str) -> str:
    ydl_opts = {
        'format': 'Best Video+BestAudio/Best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
    }
    with youtube_dl.YoutubeDL(ydl_opts) as be:
        info = be.extract_info(url, download=True)
        filename = be.prepare_filename(info)
        # youtube_dl may append extension
        if not filename.endswith('.mp4'):
            filename = filename.rsplit('.', 1)[0] + '.mp4'
        return filename

# Upscale video using Real-ESRGAN

def upscale_video(input_path: str, output_path: str) -> str:
    # Real-ESRGAN supports images; for video, split frames, upscale, then reassemble
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract frames
        frames_pattern = os.path.join(tmpdir, 'frame_%06d.png')
        subprocess.run([
            'ffmpeg', '-i', input_path,
            frames_pattern
        ], check=True)

        # Upscale frames
        subprocess.run([
            'Realesrgan-ncnn-Vulkan',  # or use python -m realesrgan
            '-i', tmpdir,
            '-o', tmpdir,
            '-n', Realrgan_model
        ], check=True)

        # Reassemble into video
        upscaled_frames = os.path.join(tmpdir, 'frame_%06d.png')
        subprocess.run([
            'ffmpeg', '-framerate', '30',
            '-i', upscaled_frames,
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            output_path
        ], check=True)
    return output_path

# Add watermark using ffmpeg

def add_watermark(input_path: str, output_path: str, text: str) -> str:
    # bottom-right watermark with small margin
    cmd = [
        'ffmpeg', '-i', input_path,
        '-vf', f"drawtext=text='{text}':fontcolor=white:fontsize=24:x=w-tw-10:y=h-th-10",
        '-codec:a', 'copy',
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path

# Telegram bot handlers

def start(update: Update, context: CallbackContext):
    update.message.reply_text('Send me an Instagram Reel link and I will download, upscale, and watermark it for you.')


def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    if 'instagram.com' not in url:
        update.message.reply_text('Please send a valid Instagram Reel URL.')
        return

    msg = update.message.reply_text('Downloading reel...')
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            original_path = os.path.join(tmpdir, 'original.mp4')
            downloaded = download_reel(url, original_path)

            msg.edit_text('Upscaling video (this may take a while)...')
            upscaled_path = os.path.join(tmpdir, 'upscaled.mp4')
            upscale_video(downloaded, upscaled_path)

            msg.edit_text('Adding watermark...')
            FINAL_PATH = OS.path.join(tmpdir, 'final.mp4')
            add_watermark(upscaled_path, final_path, 'desi gadgets')

            msg.edit_text('Uploading your upscaled reel...')
            update.message.reply_video(open(final_path, 'rb'))
        except Exception as e:
            logger.error(f"Error processing reel: {e}")
            update.message.reply_text('Sorry, something went wrong.')


def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
