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
    "eft_guru": "https://www.youtube.com/@EFTGuru-ql8dk/live", 
    "unacademy_ias": "https://www.youtube.com/@UnacademyIASEnglish/live",   
    "studyiq_hindi": "https://www.youtube.com/@StudyIQEducationLtd/live",  
    "aljazeera_arabic": "https://www.youtube.com/@aljazeera/live",  
    "aljazeera_english": "https://www.youtube.com/@AlJazeeraEnglish/live",
    "entri_degree": "https://www.youtube.com/@EntriDegreeLevelExams/live",
    "xylem_psc": "https://www.youtube.com/@XylemPSC/live",
    "xylem_sslc": "https://www.youtube.com/@XylemSSLC2023/live",
    "entri_app": "https://www.youtube.com/@entriapp/live",
    "entri_ias": "https://www.youtube.com/@EntriIAS/live",
    "studyiq_english": "https://www.youtube.com/@studyiqiasenglish/live"
}

# 🌍 Store the latest audio stream URLs
stream_cache = {}
cache_lock = threading.Lock()
failed_stations = set()  # Tracks stations that failed to get a stream URL

def get_audio_url(youtube_url):
    """Fetch the latest direct audio URL from YouTube and check if live."""
    command = [
        "yt-dlp",
        "--no-check-certificate",
        "--cookies", "/mnt/data/cookies.txt",
        "--force-generic-extractor",
        "-f", "91",
        "-g", youtube_url
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)  # ✅ Added timeout
        audio_url = result.stdout.strip() if result.stdout else None

        if audio_url:
            print(f"✅ LIVE: {youtube_url}")
            return audio_url
        else:
            print(f"❌ OFFLINE: {youtube_url}")
            return None

    except subprocess.TimeoutExpired:
        print(f"⚠️ yt-dlp timeout for {youtube_url}, skipping...")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ yt-dlp error for {youtube_url}: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error fetching audio URL for {youtube_url}: {e}")

    return None

def refresh_stream_url():
    """Refresh YouTube stream URLs every 60 minutes, retrying failed ones every 2 hours."""
    global failed_stations

    while True:
        with cache_lock:
            for station, url in YOUTUBE_STREAMS.items():
                if station in failed_stations:
                    continue  # Skip recently failed stations

                new_url = get_audio_url(url)
                if new_url:
                    stream_cache[station] = new_url
                    if station in failed_stations:
                        failed_stations.remove(station)  # ✅ Remove from failed list
                else:
                    failed_stations.add(station)  # ❌ Mark as failed

        retry_time = 3600 if not failed_stations else 7200  # ✅ Retry failed ones in 2 hours
        print(f"🔄 Next refresh in {retry_time // 60} minutes.")
        time.sleep(retry_time)

def generate_stream(station_name, max_retries=5):
    """Streams audio using FFmpeg, automatically updating the URL when it expires."""
    retries = 0

    while retries < max_retries:
        with cache_lock:
            stream_url = stream_cache.get(station_name)

        if not stream_url:
            print(f"⚠️ No valid stream URL for {station_name}, fetching a new one...")
            with cache_lock:
                youtube_url = YOUTUBE_STREAMS.get(station_name)
                if youtube_url:
                    stream_url = get_audio_url(youtube_url)
                    if stream_url:
                        stream_cache[station_name] = stream_url

        if not stream_url:
            retries += 1
            print(f"❌ Failed to fetch stream URL for {station_name}, retrying in {retries * 30}s ({retries}/{max_retries})...")
            time.sleep(retries * 30)
            continue  # Retry fetching

        process = subprocess.Popen(
            ["ffmpeg", "-re", "-i", stream_url,
             "-vn", "-acodec", "libmp3lame", "-b:a", "64k",
             "-f", "mp3", "-"],
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

        print("🔄 FFmpeg stopped, retrying in 5s...")
        process.kill()
        time.sleep(5)

    print(f"❌ Max retries reached for {station_name}. Stopping.")

@app.route("/play/<station_name>")
def stream(station_name):
    if station_name not in YOUTUBE_STREAMS:
        return "⚠️ Station not found", 404

    return Response(generate_stream(station_name), mimetype="audio/mpeg")

# 🚀 Start the URL refresher thread
threading.Thread(target=refresh_stream_url, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)