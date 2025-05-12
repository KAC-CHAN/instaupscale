import os
import tempfile
import subprocess
import requests
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from yt_dlp import YoutubeDL

# Configuration
TELEGRAM_TOKEN = "7259559804:AAG3VoiBqnwn8_5BlK51U1UMvccj3urRIdk"
HF_API_TOKEN = "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"
HF_MODEL = 'https://api-inference.huggingface.co/models/xinntao/Real-ESRGAN'  # Real-ESRGAN model endpoint

# YT-DLP options for highest quality Instagram reel
YDL_OPTS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': '%(id)s.%(ext)s',
    'merge_output_format': 'mp4'
}


def download_reel(url: str, target_path: str) -> None:
    """
    Download Instagram reel using yt-dlp.
    """
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info)
        ydl.download([url])
    os.rename(filename, target_path)


def upscale_frame_hf(image_path: str) -> bytes:
    """
    Upscale a single frame via Hugging Face Real-ESRGAN inference API.
    Returns raw image bytes.
    """
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    with open(image_path, 'rb') as f:
        response = requests.post(HF_MODEL, headers=headers, files={"inputs": f})
    response.raise_for_status()
    return response.content


def process_video(input_path: str, output_path: str, watermark: str = 'desi gadgets') -> None:
    """
    Extract frames, upscale via HF API, reassemble, and watermark.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        frames_dir = os.path.join(tmpdir, 'frames')
        up_dir = os.path.join(tmpdir, 'up')
        os.makedirs(frames_dir)
        os.makedirs(up_dir)
        # Extract frames
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
            data = upscale_frame_hf(src)
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


def handle_message(update: Update, context: CallbackContext) -> None:
    msg = update.message.text.strip()
    if 'instagram.com' not in msg:
        update.message.reply_text('Please send a valid Instagram Reel link.')
        return
    update.message.reply_text('Downloading your reel...')
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, 'input.mp4')
        out_path = os.path.join(tmpdir, 'output.mp4')
        try:
            download_reel(msg, in_path)
            update.message.reply_text('Upscaling video (may take a while)...')
            process_video(in_path, out_path)
            with open(out_path, 'rb') as vid:
                update.message.reply_video(vid)
        except Exception as e:
            update.message.reply_text(f'Something went wrong: {e}')


def main():
    if not TELEGRAM_TOKEN or not HF_API_TOKEN:
        print('Error: TELEGRAM_TOKEN and HF_API_TOKEN must be set.')
        exit(1)
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
```
