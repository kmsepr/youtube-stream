import subprocess
import time
import threading
from flask import Flask, Response

app = Flask(__name__)

# 📡 List of YouTube Live Streams
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
    "qsc_mukkam": "https://www.youtube.com/c/quranstudycentremukkam/live",
    "valiyudheen_faizy": "https://www.youtube.com/@voiceofvaliyudheenfaizy600/live",
    "skicr_tv": "https://www.youtube.com/@SKICRTV/live",
    "yaqeen_institute": "https://www.youtube.com/@yaqeeninstituteofficial/live",
    "bayyinah_tv": "https://www.youtube.com/@bayyinah/live",
}

# 🌍 Store the latest audio stream URLs
stream_cache = {}
cache_lock = threading.Lock()

def get_audio_url(youtube_url):
    """Fetch the latest direct audio URL from YouTube."""
    command = [
        "yt-dlp",
        "--cookies", "/mnt/data/cookies.txt",
        "--force-generic-extractor",
        "-f", "91",  # Audio format
        "-g", youtube_url
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        audio_url = result.stdout.strip() if result.stdout else None
        return audio_url
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Error fetching audio URL: {e}")
        return None

def refresh_stream_url():
    """Refresh YouTube stream URLs every 2 minutes to avoid expiration."""
    while True:
        with cache_lock:
            for station, url in YOUTUBE_STREAMS.items():
                new_url = get_audio_url(url)
                if new_url:
                    stream_cache[station] = new_url
        time.sleep(120)  # Refresh every 2 minutes

def generate_stream(youtube_url):
    """Streams audio using FFmpeg, automatically updating the URL when it expires."""
    while True:
        with cache_lock:
            stream_url = stream_cache.get(youtube_url, None)
        
        if not stream_url:
            print("⚠️ No valid stream URL, trying to fetch a new one...")
            with cache_lock:
                stream_url = get_audio_url(youtube_url)
                if stream_url:
                    stream_cache[youtube_url] = stream_url

        if not stream_url:
            print("❌ Failed to fetch stream URL")
            return

        process = subprocess.Popen(
            ["ffmpeg", "-re", "-i", stream_url,
             "-vn", "-acodec", "libmp3lame", "-b:a", "64k",
             "-buffer_size", "1024k", "-f", "mp3", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=8192
        )

        print(f"🎵 Streaming from: {stream_url}")

        try:
            for chunk in iter(lambda: process.stdout.read(8192), b""):
                yield chunk
        except GeneratorExit:
            process.kill()
            break
        except Exception as e:
            print(f"⚠️ Stream error: {e}")

        print("🔄 FFmpeg stopped, retrying...")
        time.sleep(5)

@app.route("/play/<station_name>")
def stream(station_name):
    youtube_url = YOUTUBE_STREAMS.get(station_name)
    if not youtube_url:
        return "⚠️ Station not found", 404

    return Response(generate_stream(youtube_url), mimetype="audio/mpeg")

# 🚀 Start the URL refresher thread
threading.Thread(target=refresh_stream_url, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)