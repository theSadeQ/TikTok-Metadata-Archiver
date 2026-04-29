# TikTok Metadata Archiver 🎥

An automated tool powered by GitHub Actions and `yt-dlp` to continuously monitor and archive TikTok user and video metadata. 

**Note**: This project extracts *metadata* (descriptions, stats, URLs) and saves them in structured JSON and CSV formats. It does *not* download the heavy video files, ensuring it runs quickly and respects GitHub repository limits.

## 📁 Repository Structure
- `config/users.txt`: The list of TikTok usernames to monitor.
- `config/settings.yml`: Configuration file (rate limits, video caps).
- `scripts/collect_tiktok_metadata.py`: The core Python extraction engine.
- `data/`: The output folder where JSON and CSV files are automatically saved.
- `.github/workflows/`: The GitHub Actions configuration.

## 🚀 How to Use

### 1. Adding Users
Simply edit `config/users.txt` and add the TikTok handles you want to track (one per line).
```text
tiktok
tiktokcreators

### 2. Configuration
Edit `config/settings.yml` to change execution behavior:
- `max_videos_per_user`: Set a cap to prevent scraping timeouts (e.g., `15`). Set to `null` to attempt archiving all videos.
- `sleep_seconds_between_users`: Delay between accounts to avoid rate limiting.

### 3. Automated Runs (GitHub Actions)
Once pushed to GitHub, the workflow runs automatically **every 6 hours**.
You can also run it manually:
1. Go to the **Actions** tab in your repository.
2. Select **TikTok Metadata Archiver**.
3. Click **Run workflow**.

The action will checkout the code, run the scraper, and automatically commit the new data files back to the `data/` folder.

### 4. Setting up Cookies (Optional but Recommended)
TikTok heavily rate-limits anonymous scraping. Providing cookies greatly improves reliability.
1. Use a browser extension like "Get cookies.txt LOCALLY" to export your TikTok cookies.
2. Go to your GitHub repository **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret**.
4. Name: `TIKTOK_COOKIES`
5. Value: Paste the contents of your exported cookies file.

The GitHub Action will automatically detect this and securely pass it to `yt-dlp`.

### 💻 Running Locally
Ensure you have Python 3.8+ installed.
bash
# Clone the repo
git clone <your-repo-url>
cd <repo-name>

# Install requirements
pip install -r requirements.txt

# Run the script
python scripts/collect_tiktok_metadata.py

## ⚠️ Limitations & Disclaimers
* **Rate Limiting**: TikTok actively blocks aggressive automated requests. If `yt-dlp` returns empty arrays, it likely means you are temporarily blocked. Use the `TIKTOK_COOKIES` secret to mitigate this.
* **yt-dlp Maintenance**: Web structures change frequently. Keep `yt-dlp` up to date in the `requirements.txt` to ensure uninterrupted extraction.


---

### Data Flow Overview
1. **Input**: The script reads user lists and configs. 
2. **Processing**: It loops through users, dynamically generating a command for `subprocess` like: `python -m yt_dlp --dump-single-json ...`. 
3. **Execution**: The CLI tool hits TikTok's APIs/HTML. 
4. **Ingestion**: Standard output is captured as a string, loaded into Python as a JSON dictionary, and parsed to extract exactly what we need.
5. **Output**: The dictionary is pushed locally to `.json` and `.csv` files.
6. **Automation**: GitHub Actions looks at the file tree ($ \Delta \text{files} $). If the files have updated content (e.g., view counts changed, new videos added), it creates a commit and pushes it back to the branch.
