import os
import json
import subprocess
import csv
import argparse
import concurrent.futures
import yaml
from datetime import datetime, timezone

# --- Configuration Paths ---
CONFIG_DIR = 'config'
DATA_DIR = 'data'
USERS_FILE = os.path.join(CONFIG_DIR, 'users.txt')
SETTINGS_FILE = os.path.join(CONFIG_DIR, 'settings.yml')
USERS_DATA_DIR = os.path.join(DATA_DIR, 'users')
ALL_JSON_FILE = os.path.join(DATA_DIR, 'tiktok-all.json')
SUMMARY_CSV_FILE = os.path.join(DATA_DIR, 'tiktok-summary.csv')


def setup_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(USERS_DATA_DIR, exist_ok=True)


def load_settings():
    default_settings = {
        'download_profile_images': False,
        'sleep_seconds_between_users': 5,
        'max_videos_per_user': None,
        'max_workers': 5
    }
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            user_settings = yaml.safe_load(f) or {}
            default_settings.update(user_settings)
    return default_settings


def load_usernames():
    usernames = []
    if not os.path.exists(USERS_FILE):
        print(f"[-] Warning: {USERS_FILE} not found.")
        return usernames
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('@'):
                line = line[1:]
            if line:
                usernames.append(line)
    return usernames


def fetch_user_data(username, settings):
    """
    Execute yt-dlp via subprocess.
    Using subprocess provides strict isolation and prevents library-level
    stdout pollution, making JSON extraction highly reliable.
    Safe to call from multiple threads simultaneously.
    """
    url = f"https://www.tiktok.com/@{username}"

    cmd = [
        "python", "-m", "yt_dlp",
        "--dump-single-json",
        "--no-flat-playlist",
        "--ignore-errors",
        "--quiet",
        "--no-warnings"
    ]

    if os.path.exists("cookies.txt"):
        cmd.extend(["--cookies", "cookies.txt"])

    max_videos = settings.get('max_videos_per_user')
    if max_videos:
        cmd.extend(["--playlist-end", str(max_videos)])

    cmd.append(url)

    print(f"[*] Fetching metadata for @{username}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if not result.stdout.strip():
            print(f"[-] No data returned for @{username}. (stderr: {result.stderr[:200]})")
            return None

        raw_data = json.loads(result.stdout)
        entries = raw_data.get('entries', [])
        videos = [v for v in entries if v is not None]

        user_obj = {
            "username": username,
            "source_url": url,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "videos": extract_video_metadata(videos)
        }
        return user_obj

    except json.JSONDecodeError as e:
        print(f"[-] Failed to parse JSON for @{username}: {e}")
        return {"username": username, "error": "JSONDecodeError", "collected_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        print(f"[-] Unexpected error for @{username}: {e}")
        return {"username": username, "error": str(e), "collected_at": datetime.now(timezone.utc).isoformat()}


def extract_video_metadata(raw_videos):
    desired_keys = [
        "id", "title", "description", "webpage_url", "original_url",
        "uploader", "uploader_id", "uploader_url", "channel", "channel_id",
        "duration", "timestamp", "upload_date", "view_count", "like_count",
        "comment_count", "repost_count", "thumbnail", "thumbnails", "tags",
        "categories", "music", "extractor", "extractor_key"
    ]
    cleaned_videos = []
    for rv in raw_videos:
        cleaned_vid = {key: rv[key] for key in desired_keys if key in rv}
        cleaned_videos.append(cleaned_vid)
    return cleaned_videos


def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def update_summary_csv(all_users_data):
    csv_headers = [
        "username", "video_id", "title", "webpage_url", "upload_date",
        "timestamp", "duration", "view_count", "like_count", "comment_count",
        "repost_count", "thumbnail", "collected_at"
    ]
    with open(SUMMARY_CSV_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers, extrasaction='ignore')
        writer.writeheader()
        for user in all_users_data:
            if "error" in user:
                continue
            username = user.get("username", "unknown")
            collected_at = user.get("collected_at", "")
            for vid in user.get("videos", []):
                row = {
                    "username": username,
                    "video_id": vid.get("id", ""),
                    "title": vid.get("title", ""),
                    "webpage_url": vid.get("webpage_url", ""),
                    "upload_date": vid.get("upload_date", ""),
                    "timestamp": vid.get("timestamp", ""),
                    "duration": vid.get("duration", ""),
                    "view_count": vid.get("view_count", ""),
                    "like_count": vid.get("like_count", ""),
                    "comment_count": vid.get("comment_count", ""),
                    "repost_count": vid.get("repost_count", ""),
                    "thumbnail": vid.get("thumbnail", ""),
                    "collected_at": collected_at
                }
                if isinstance(row["title"], str):
                    row["title"] = row["title"].replace("\n", " ").replace("\r", " ")
                writer.writerow(row)


def main():
    # --- Fix 4: CLI argument to override users.txt ---
    parser = argparse.ArgumentParser(description="Collect TikTok metadata via yt-dlp")
    parser.add_argument(
        "--users",
        help="Comma-separated TikTok usernames to override config/users.txt",
        default=None
    )
    args = parser.parse_args()

    setup_directories()
    settings = load_settings()

    if args.users:
        usernames = [u.strip().lstrip("@") for u in args.users.split(",") if u.strip()]
        print(f"[*] Using CLI-provided usernames: {usernames}")
    else:
        usernames = load_usernames()

    if not usernames:
        print("[-] No usernames found. Exiting.")
        return

    print(f"[*] Collecting metadata for {len(usernames)} user(s) in parallel...")

    # --- Fix 1: Parallel fetching with ThreadPoolExecutor ---
    # sleep_seconds_between_users is no longer needed; removed.
    # max_workers controls concurrency (default 5, configurable in settings.yml).
    max_workers = int(settings.get('max_workers', 5))
    all_data = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_user_data, username, settings): username
            for username in usernames
        }
        for future in concurrent.futures.as_completed(futures):
            username = futures[future]
            user_data = future.result()
            if user_data:
                user_file = os.path.join(USERS_DATA_DIR, f"{username}.json")
                save_json(user_data, user_file)
                all_data.append(user_data)
                print(f"[+] Saved @{username} ({len(user_data.get('videos', []))} videos)")

    save_json(all_data, ALL_JSON_FILE)
    print(f"[+] Saved aggregated data to {ALL_JSON_FILE}")

    update_summary_csv(all_data)
    print(f"[+] Saved CSV summary to {SUMMARY_CSV_FILE}")
    print("[+] Archival run complete!")


if __name__ == "__main__":
    main()
