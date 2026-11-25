#!/usr/bin/env python3
"""
Cloud Shorts Renderer (runs in GitHub Actions, 100% free, no laptop).
Downloads .wav voiceover + .srt Hindi captions from Google Drive,
fetches 9:16 stock clips from Pexels, renders a 1080x1920 MP4 with
burned-in Hindi Noto Sans Devanagari captions via ffmpeg, uploads it
back to Google Drive (automate_video), and updates the Google Sheet.
"""

import json
import os
import re
import subprocess
import tempfile
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_google_services():
    raw_sa = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw_sa)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)
    return drive, sheets


def download_drive_file(drive, file_id, dest_path):
    request = drive.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def get_audio_duration(wav_path):
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            wav_path,
        ],
        text=True,
    ).strip()
    return max(5.0, float(out))


def fetch_pexels_clips(api_key, query, workdir, min_clips=3):
    headers = {"Authorization": api_key}
    queries = [query, "technology abstract", "futuristic circuit"]
    clip_paths = []

    for q in queries:
        if len(clip_paths) >= min_clips:
            break
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": q, "orientation": "portrait", "per_page": 6},
            timeout=30,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        for vid in videos:
            if len(clip_paths) >= min_clips:
                break
            files = sorted(
                [vf for vf in vid.get("video_files", []) if vf.get("file_type") == "video/mp4"],
                key=lambda x: abs((x.get("height") or 0) - 1920),
            )
            if not files:
                continue
            dl_url = files[0]["link"]
            out_path = os.path.join(workdir, f"clip_{len(clip_paths)}.mp4")
            with requests.get(dl_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            clip_paths.append(out_path)

    if not clip_paths:
        raise RuntimeError("No Pexels video clips found.")
    return clip_paths


def normalize_and_concat_clips(clip_paths, target_duration, workdir):
    norm_paths = []
    for idx, src in enumerate(clip_paths):
        dst = os.path.join(workdir, f"norm_{idx}.mp4")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                src,
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                dst,
            ],
            check=True,
        )
        norm_paths.append(dst)

    concat_list = os.path.join(workdir, "concat.txt")
    # Repeat clip list enough times to cover target_duration
    with open(concat_list, "w", encoding="utf-8") as f:
        for _ in range(6):
            for p in norm_paths:
                f.write(f"file '{p}'\n")

    bg_video = os.path.join(workdir, "bg_loop.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-t",
            f"{target_duration:.2f}",
            "-c:v",
            "copy",
            bg_video,
        ],
        check=True,
    )
    return bg_video


def render_final_video(bg_video, wav_path, srt_path, out_mp4):
    # Escape path for ffmpeg subtitles filter
    escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
    style = (
        "FontName=Noto Sans Devanagari,FontSize=15,Bold=1,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BackColour=&H64000000,BorderStyle=3,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=55"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            bg_video,
            "-i",
            wav_path,
            "-vf",
            f"subtitles='{escaped_srt}':force_style='{style}'",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            out_mp4,
        ],
        check=True,
    )


def slugify(text):
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", text or "short").strip("_")
    return (clean[:45] or "short")


def main():
    drive, sheets = get_google_services()
    folder_id = os.environ["DRIVE_FOLDER_ID"]
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    row_num = os.environ["ROW_NUM"]
    title = os.environ["VIDEO_TITLE"]
    search_query = os.environ.get("SEARCH_QUERY", "technology abstract")
    wav_id = os.environ["WAV_FILE_ID"]
    srt_id = os.environ["SRT_FILE_ID"]
    pexels_key = os.environ["PEXELS_API_KEY"]

    with tempfile.TemporaryDirectory() as workdir:
        wav_path = os.path.join(workdir, "voiceover.wav")
        srt_path = os.path.join(workdir, "captions.srt")
        out_name = f"{slugify(title)}.mp4"
        out_mp4 = os.path.join(workdir, out_name)

        download_drive_file(drive, wav_id, wav_path)
        download_drive_file(drive, srt_id, srt_path)

        duration = get_audio_duration(wav_path)
        clips = fetch_pexels_clips(pexels_key, search_query, workdir)
        bg_video = normalize_and_concat_clips(clips, duration, workdir)
        render_final_video(bg_video, wav_path, srt_path, out_mp4)

        file_metadata = {"name": out_name, "parents": [folder_id]}
        media = MediaFileUpload(out_mp4, mimetype="video/mp4", resumable=True)
        uploaded = drive.files().create(
            body=file_metadata, media_body=media, fields="id, webViewLink"
        ).execute()

        # Make readable via link so Zapier can also fetch it if needed
        drive.permissions().create(
            fileId=uploaded["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        drive_url = f"https://drive.google.com/file/d/{uploaded['id']}/view"
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"I{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": [[drive_url]]},
        ).execute()

        print(f"Uploaded {out_name} -> {drive_url} (updated Sheet row {row_num})")


if __name__ == "__main__":
    main()
