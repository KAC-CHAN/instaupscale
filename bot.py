
import os
import tempfile
import subprocess
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from yt_dlp import YoutubeDL
import shutil

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = "7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4"

# YT-DLP options for highest-quality Instagram reel
YDL_OPTS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': '%(id)s.%(ext)s',
    'merge_output_format': 'mp4'
}

async def download_reel(url: str, target_path: str) -> None:
    '''Download Instagram reel using yt-dlp.'''
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info)
        ydl.download([url])
    shutil.move(filename, target_path)

async def process_video(input_path: str, output_path: str, watermark: str = 'desi gadgets') -> None:
    '''Upscale video via FFmpeg Lanczos scaling and add watermark.'''
    # 2x upscale with high-quality Lanczos filter
    vf_chain = (
        'scale=iw*2:ih*2:flags=lanczos,'
        f"drawtext=text='{watermark}':fontcolor=white@0.8:fontsize=24:x=w-tw-10:y=h-th-10"
    )
    subprocess.check_call([
        'ffmpeg', '-i', input_path,
        '-vf', vf_chain,
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-c:a', 'copy', output_path
    ])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message.text.strip()
    if 'instagram.com' not in msg:
        await update.message.reply_text('Please send a valid Instagram Reel link.')
        return
    await update.message.reply_text('Downloading your reel...')
    with tempfile.TemporaryDirectory() as tmpdir:
        in_vid = os.path.join(tmpdir, 'input.mp4')
        out_vid = os.path.join(tmpdir, 'output.mp4')
        try:
            await download_reel(msg, in_vid)
            await update.message.reply_text('Upscaling video (CPU-only, may take a few seconds)...')
            await process_video(in_vid, out_vid)
            with open(out_vid, 'rb') as f:
                await update.message.reply_video(f)
        except Exception as e:
            logger.error('Processing error: %s', e)
            await update.message.reply_text(f'Something went wrong: {e}')

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        logger.error('Missing TELEGRAM_TOKEN.')
        exit(1)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
