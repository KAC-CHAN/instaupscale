
import os
import tempfile
import subprocess
import requests
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from yt_dlp import YoutubeDL

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = "7259559804:AAG3VoiBqnwn8_5BlK51U1UMvccj3urRIdk"
HF_API_TOKEN = "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"
HF_MODEL_URL = 'https://api-inference.huggingface.co/models/xinntao/Real-ESRGAN'  # Real-ESRGAN API endpoint

# YT-DLP options for highest-quality Instagram reel
YDL_OPTS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': '%(id)s.%(ext)s',
    'merge_output_format': 'mp4'
}

async def download_reel(url: str, target_path: str) -> None:
    """
    Download Instagram reel using yt-dlp.
    """
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info)
        ydl.download([url])
    os.rename(filename, target_path)

async def upscale_frame_hf(image_path: str) -> bytes:
    """
    Upscale a single frame via Hugging Face Real-ESRGAN inference API.
    Returns raw image bytes.
    """
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    with open(image_path, 'rb') as f:
        response = requests.post(HF_MODEL_URL, headers=headers, files={"inputs": f})
    response.raise_for_status()
    return response.content

async def process_video(input_path: str, output_path: str, watermark: str = 'desi gadgets') -> None:
    """
    Extract frames, upscale via HF API, reassemble, and watermark.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        frames_dir = os.path.join(tmpdir, 'frames')
        up_dir = os.path.join(tmpdir, 'up')
        os.makedirs(frames_dir)
        os.makedirs(up_dir)
        # Extract frames and fps
        fps_str = subprocess.check_output([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate', '-of', 'default=nokey=1:noprint_wrappers=1',
            input_path
        ]).decode().strip()
        fps = eval(fps_str)
        subprocess.check_call([
            'ffmpeg', '-i', input_path,
            os.path.join(frames_dir, 'frame_%05d.png')
        ])
        # Upscale each frame
        for fname in sorted(os.listdir(frames_dir)):
            src = os.path.join(frames_dir, fname)
            data = await upscale_frame_hf(src)
            with open(os.path.join(up_dir, fname), 'wb') as fout:
                fout.write(data)
        # Reassemble video
        intermediate = os.path.join(tmpdir, 'upscaled.mp4')
        subprocess.check_call([
            'ffmpeg', '-framerate', str(fps), '-i',
            os.path.join(up_dir, 'frame_%05d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', intermediate
        ])
        # Watermark
        subprocess.check_call([
            'ffmpeg', '-i', intermediate,
            '-vf', f"drawtext=text='{watermark}':fontcolor=white@0.8:fontsize=24:x=w-tw-10:y=h-th-10",
            '-codec:a', 'copy', output_path
        ])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message.text.strip()
    if 'instagram.com' not in msg:
        await update.message.reply_text('Please send a valid Instagram Reel link.')
        return
    await update.message.reply_text('Downloading your reel...')
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, 'input.mp4')
        out_path = os.path.join(tmpdir, 'output.mp4')
        try:
            await download_reel(msg, in_path)
            await update.message.reply_text('Upscaling video (may take a while)...')
            await process_video(in_path, out_path)
            with open(out_path, 'rb') as vid:
                await update.message.reply_video(vid)
        except Exception as e:
            logger.error('Error processing reel: %s', e)
            await update.message.reply_text(f'Something went wrong: {e}')

async def main() -> None:
    if not TELEGRAM_TOKEN or not HF_API_TOKEN:
        logger.error('TELEGRAM_TOKEN and HF_API_TOKEN must be set.')
        return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
