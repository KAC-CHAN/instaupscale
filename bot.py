
import os
import tempfile
import subprocess
import logging
import shutil
import urllib.request
import cv2
import numpy as np
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
TELEGRAM_TOKEN = "7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4"

# YT-DLP options for highest-quality Instagram reel
YDL_OPTS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': '%(id)s.%(ext)s',
    'merge_output_format': 'mp4'
}

# Super-resolution model settings
# Using OpenCV DNN SuperRes EDSR x2 (free, CPU-based)
MODEL_URL = 'https://github.com/opencv/opencv_contrib/raw/4.7.0/modules/dnn_superres/testdata/EDSR_x2.pb'
MODEL_PATH = 'EDSR_x2.pb'
MODEL_SCALE = 2
MODEL_NAME = 'edsr'

# Download SR model if missing
if not os.path.isfile(MODEL_PATH):
    try:
        logger.info('Downloading super-resolution model...')
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    except Exception as e:
        logger.error('Failed to download model: %s', e)
        raise RuntimeError('Could not fetch the super-resolution model.')

# Initialize SuperRes engine
sr = cv2.dnn_superres.DnnSuperResImpl_create()
sr.readModel(MODEL_PATH)
sr.setModel(MODEL_NAME, MODEL_SCALE)

async def download_reel(url: str, target_path: str) -> None:
    '''Download Instagram reel using yt-dlp.'''
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info)
        ydl.download([url])
    shutil.move(filename, target_path)

def upscale_frame_local(image_path: str) -> bytes:
    '''Upscale a single frame using OpenCV DNN SuperRes.'''
    img = cv2.imread(image_path)
    result = sr.upsample(img)
    success, encoded = cv2.imencode('.png', result)
    if not success:
        raise RuntimeError('Failed to encode upscaled frame')
    return encoded.tobytes()

async def process_video(input_path: str, output_path: str, watermark: str = 'desi gadgets') -> None:
    '''Extract frames, upscale locally, reassemble, and watermark.'''
    with tempfile.TemporaryDirectory() as tmpdir:
        frames_dir = os.path.join(tmpdir, 'frames')
        up_dir = os.path.join(tmpdir, 'up')
        os.makedirs(frames_dir, exist_ok=True)
        os.makedirs(up_dir, exist_ok=True)

        fps_str = subprocess.check_output([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate',
            '-of', 'default=nokey=1:noprint_wrappers=1', input_path
        ]).decode().strip()
        fps = eval(fps_str)

        subprocess.check_call([
            'ffmpeg', '-i', input_path,
            os.path.join(frames_dir, 'frame_%05d.png')
        ])

        for fname in sorted(os.listdir(frames_dir)):
            src = os.path.join(frames_dir, fname)
            data = upscale_frame_local(src)
            with open(os.path.join(up_dir, fname), 'wb') as f:
                f.write(data)

        temp_video = os.path.join(tmpdir, 'upscaled.mp4')
        subprocess.check_call([
            'ffmpeg', '-framerate', str(fps),
            '-i', os.path.join(up_dir, 'frame_%05d.png'),
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', temp_video
        ])

        subprocess.check_call([
            'ffmpeg', '-i', temp_video,
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
        in_vid = os.path.join(tmpdir, 'input.mp4')
        out_vid = os.path.join(tmpdir, 'output.mp4')
        try:
            await download_reel(msg, in_vid)
            await update.message.reply_text('Upscaling video (CPU-only, may take time)...')
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
