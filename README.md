100% Free Cloud YouTube Shorts Pipeline (Apps Script + GitHub Actions ffmpeg)

Runs completely in the cloud (no laptop or local hardware required):

Google Apps Script (ShortsPipeline.gs): Finds trending/tech topics, writes Hindi script + captions + metadata (gemini-4-hydrogen / gemini-3.5-flash-lite Free Tier), generates Hindi .wav voiceover (gemini-3.8-flash-tts Free Tier), and triggers GitHub Actions.
GitHub Actions (.github/workflows/render-short.yml + render_short.py): Fetches 9:16 stock clips from Pexels, renders the MP4 with ffmpeg + burned-in Hindi Noto Devanagari captions, saves it to automate_video on Google Drive, and writes the Drive link into Column I of your Google Sheet.
Upload to YouTube: Either uploadReadyVideosToYouTube in Apps Script (free, Private until verified) or your Zapier Zap watching automate_video (Public).
One-Time Setup
A. GitHub Repo & Secrets
Create a GitHub repository (public = unlimited free Actions minutes; private = 2,000 free mins/month) and push:
.github/workflows/render-short.yml
render_short.py
Get a free Pexels API key at https://www.pexels.com/api/.
Create a Google Cloud Service Account (in your Google Cloud Console -> IAM & Admin -> Service Accounts -> Create Key -> JSON):
Enable Google Drive API and Google Sheets API in that Google Cloud project.
Share your automate_video Google Drive folder AND your Google Sheet with the Service Account's ...@...iam.gserviceaccount.com email as Editor.
In your GitHub repo -> Settings -> Secrets and variables -> Actions, add:
PEXELS_API_KEY: your Pexels API key
GOOGLE_SERVICE_ACCOUNT_JSON: the full contents of your Service Account JSON key file
B. Google Apps Script
Paste ShortsPipeline.gs into Apps Script and click Save.
In Project Settings -> Script Properties, add:
GEMINI_API_KEY: your Gemini API key
GITHUB_REPO: your-username/your-repo-name
GITHUB_TOKEN: a GitHub Fine-Grained Personal Access Token with Actions: Read and write permission on that repo
Enable Services (+) -> YouTube Data API v3 (if using uploadReadyVideosToYouTube).
Add Time-driven Triggers for generateDailyShortsPackage (daily) and uploadReadyVideosToYouTube (hourly).
