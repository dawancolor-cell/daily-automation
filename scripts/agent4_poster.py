"""
agent4_poster.py — Poster Agent
Posts final video to Instagram Reels, TikTok, YouTube Shorts, and Facebook Reels.
"""

import os
import time
import requests
from pathlib import Path

OUTPUT_DIR = Path("output")

def build_caption(script: dict, topic: str) -> str:
    hook = script.get("hook", "")
    verse1 = script.get("verses", [[]])[0]
    first_line = verse1[0] if verse1 else ""
    fact = script.get("educational_fact", "")

    return (
        f"{hook} 🎵✨\n\n"
        f"{first_line}\n\n"
        f"📚 Today's topic: {topic}\n"
        f"💡 Fun fact: {fact}\n"
        f"🎶 Educational music for kids!\n\n"
        f"#KidsEducation #AnimatedSongs #LearnWithMusic #KidsTV "
        f"#EducationalReels #KidsAnimation #FunLearning #ChildrenSongs "
        f"#{topic.replace(' ', '')} #KidsYouTube"
    )


def run(video_filename: str, script: dict, topic: str) -> dict:
    """Post to all 4 platforms. Returns dict of platform → post URL."""
    video_path = OUTPUT_DIR / video_filename
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    caption = build_caption(script, topic)
    results = {}

    # Post to each platform
    for platform, fn in [
        ("instagram", post_instagram),
        ("facebook",  post_facebook),
        ("tiktok",    post_tiktok),
        ("youtube",   post_youtube),
    ]:
        try:
            url = fn(str(video_path), caption, topic)
            results[platform] = url or "posted_ok"
            print(f"[Poster] {platform} ✅")
        except Exception as e:
            results[platform] = f"FAILED: {e}"
            print(f"[Poster] {platform} ❌ {e}")
        time.sleep(3)  # Pause between platform calls

    return results


# ── Instagram Reels ────────────────────────────────────────────────────────────
def post_instagram(video_path: str, caption: str, topic: str) -> str:
    ig_user_id = os.getenv("INSTAGRAM_USER_ID")
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")

    if not ig_user_id or not access_token:
        raise ValueError("Missing INSTAGRAM_USER_ID or INSTAGRAM_ACCESS_TOKEN")

    # Step 1: Upload video container
    r = requests.post(
        f"https://graph.instagram.com/v21.0/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": _get_public_video_url(video_path),
            "caption": caption,
            "share_to_feed": "true",
            "access_token": access_token,
        }
    )
    r.raise_for_status()
    container_id = r.json()["id"]

    # Step 2: Wait for processing
    _wait_for_ig_container(container_id, access_token)

    # Step 3: Publish
    r2 = requests.post(
        f"https://graph.instagram.com/v21.0/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": access_token}
    )
    r2.raise_for_status()
    post_id = r2.json()["id"]
    return f"https://www.instagram.com/p/{post_id}/"


def _wait_for_ig_container(container_id: str, token: str, max_wait: int = 120):
    for _ in range(max_wait // 5):
        r = requests.get(
            f"https://graph.instagram.com/v21.0/{container_id}",
            params={"fields": "status_code", "access_token": token}
        )
        status = r.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError("Instagram container processing failed")
        time.sleep(5)
    raise TimeoutError("Instagram container processing timed out")


# ── Facebook Reels ─────────────────────────────────────────────────────────────
def post_facebook(video_path: str, caption: str, topic: str) -> str:
    page_id = os.getenv("FACEBOOK_PAGE_ID")
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")

    if not page_id or not access_token:
        raise ValueError("Missing FACEBOOK_PAGE_ID or FACEBOOK_ACCESS_TOKEN")

    # Upload video as Reel
    r = requests.post(
        f"https://graph.facebook.com/v21.0/{page_id}/video_reels",
        data={
            "upload_phase": "start",
            "access_token": access_token,
        }
    )
    r.raise_for_status()
    upload_url = r.json().get("upload_url")
    video_id = r.json().get("video_id")

    # Upload binary
    with open(video_path, "rb") as f:
        requests.post(upload_url, files={"file": f})

    # Finish / publish
    r2 = requests.post(
        f"https://graph.facebook.com/v21.0/{page_id}/video_reels",
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "title": topic,
            "description": caption,
            "video_state": "PUBLISHED",
            "access_token": access_token,
        }
    )
    r2.raise_for_status()
    return f"https://www.facebook.com/reel/{video_id}"


# ── TikTok ─────────────────────────────────────────────────────────────────────
def post_tiktok(video_path: str, caption: str, topic: str) -> str:
    access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        raise ValueError("Missing TIKTOK_ACCESS_TOKEN")

    # Initialize upload
    r = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        },
        json={
            "post_info": {
                "title": f"{topic} 🎵 #KidsEducation",
                "description": caption[:2200],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": Path(video_path).stat().st_size,
                "chunk_size": Path(video_path).stat().st_size,
                "total_chunk_count": 1,
            }
        }
    )
    r.raise_for_status()
    data = r.json().get("data", {})
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")

    # Upload video
    video_size = Path(video_path).stat().st_size
    with open(video_path, "rb") as f:
        requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(video_size),
                "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
            },
            data=f
        )

    return f"https://www.tiktok.com/ (publish_id: {publish_id})"


# ── YouTube Shorts ─────────────────────────────────────────────────────────────
def post_youtube(video_path: str, caption: str, topic: str) -> str:
    """Upload to YouTube using google-api-python-client."""
    import pickle
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None

    # Load saved token
    if Path("token.pickle").exists():
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)

    # Refresh or re-auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secret_path = os.getenv("YOUTUBE_CLIENT_SECRET_JSON", "client_secret.json")
            flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)

    youtube = build("youtube", "v3", credentials=creds)

    # Use horizontal version for YouTube
    yt_video = video_path.replace("vertical", "horizontal")
    if not Path(yt_video).exists():
        yt_video = video_path

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": f"{topic} 🎵 Kids Educational Song #Shorts",
                "description": caption,
                "tags": ["kids", "education", "animation", "shorts", "learning", topic.lower()],
                "categoryId": "27",  # Education
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": True,
            }
        },
        media_body=MediaFileUpload(yt_video, chunksize=-1, resumable=True)
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]
    return f"https://www.youtube.com/shorts/{video_id}"


# ── Utility ────────────────────────────────────────────────────────────────────
def _get_public_video_url(video_path: str) -> str:
    """
    Instagram requires a publicly accessible video URL.
    Options: upload to S3, Cloudinary, or use ngrok for local testing.
    Set PUBLIC_VIDEO_BASE_URL in .env to your hosting base URL.
    """
    base_url = os.getenv("PUBLIC_VIDEO_BASE_URL", "")
    if not base_url:
        raise ValueError(
            "Set PUBLIC_VIDEO_BASE_URL in .env (e.g., your S3 bucket or Cloudinary URL). "
            "Instagram requires a public URL for video uploads."
        )
    filename = Path(video_path).name
    return f"{base_url.rstrip('/')}/{filename}"
