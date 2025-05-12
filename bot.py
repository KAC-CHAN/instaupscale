

import os
import tempfile
import logging
import cv2
import shutil
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from yt_dlp import YoutubeDL
from pyanime4k import ac

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram Bot Token
TELEGRAM_TOKEN = "7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4"

# yt-dlp config
YDL_OPTS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': '%(id)s.%(ext)s',
    'merge_output_format': 'mp4'
}

async def download_reel(url: str, target_path: str) -> None:
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info)
        ydl.download([url])
    shutil.move(filename, target_path)

def upscale_video_cpu(input_path: str, output_path: str):
    ac_instance = ac.AC()
    ac_instance.set_arguments(gpu=False)

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise Exception("Cannot open video file.")

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        upscaled_frame = ac_instance.process_image(frame)
        out.write(upscaled_frame)

    cap.release()
    out.release()

def add_watermark(input_path: str, output_path: str, watermark: str = "desi gadgets"):
    vf_chain = f"drawtext=text='{watermark}':fontcolor=white@0.8:fontsize=24:x=w-tw-10:y=h-th-10"
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf_chain,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy", output_path
    ], check=True)

async def process_video(in_vid, out_vid):
    # Paths
    upscaled_vid = in_vid.replace(".mp4", "_upscaled.mp4")
    # Step 1: Upscale
    upscale_video_cpu(in_vid, upscaled_vid)
    # Step 2: Add watermark
    add_watermark(upscaled_vid, out_vid)

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
            await update.message.reply_text('Upscaling and watermarking video... ⏳')
            await process_video(in_vid, out_vid)
            await update.message.reply_video(video=open(out_vid, 'rb'))
        except Exception as e:
            logger.error('Error: %s', e)
            await update.message.reply_text(f'❌ Something went wrong: {e}')

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        logger.error("Missing TELEGRAM_TOKEN.")
        exit(1)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
