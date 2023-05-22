import base64
import glob
import json
import os
import subprocess
import time
from datetime import datetime
from urllib.request import Request
from urllib.request import urlopen

import boto3

BUCKET_NAME = "podcasts.gtmanfred.com"
BUCKET = boto3.resource("s3").Bucket(name=BUCKET_NAME)


APIKEY = os.getenv("YOUTUBE_API_KEY")


def _get_video_mp3(videoid):
    files = glob.glob(f"/tmp/*{videoid}*.mp3")
    if not files:
        return None
    return files[0]


def _duration(duration):
    try:
        return datetime.strptime(duration, "PT%HH%MM%SS").strftime("%H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(duration, "PT%MM%SS").strftime("%M:%S")
        except ValueError:
            try:
                return datetime.strptime(duration, "PT%HH%SS").strftime("%H:%M:%S")
            except ValueError:
                return datetime.strptime(duration, "PT%HH%MM").strftime("%H:%M:%S")


def _publish_date(date):
    return datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")


def _get_video(videoid):
    url = f"https://www.googleapis.com/youtube/v3/videos?id={videoid}&key={APIKEY}&part=contentDetails,snippet"
    req = Request(
        method="GET",
        url=url,
    )
    return json.load(urlopen(req))["items"][0]


def _download_video(videoid):
    return subprocess.run(
        (
            "python3 -m yt_dlp -c -x "
            '--audio-format mp3 -o "/tmp/%(title)s[%(id)s].%(ext)s" '
            "--cache-dir /tmp/yt-dlp/ -- "
            f"{videoid}"
        ),
        shell=True,
        stderr=subprocess.PIPE,
    )


def main(videoid, location):
    while (result := _download_video(videoid)).returncode:
        if "Private video." in result.stderr.decode("utf-8"):
            print(result.stderr)
            return
        time.sleep(5)

    mp3_file = _get_video_mp3(videoid)

    video = _get_video(videoid)

    BUCKET.upload_file(
        Filename=mp3_file,
        Key=f"{location}/{os.path.basename(mp3_file)}",
        ExtraArgs={
            "Metadata": {
                "videoid": videoid,
                "pubdate": _publish_date(video["snippet"]["publishedAt"]),
                "title": video["snippet"]["title"],
                "duration": _duration(video["contentDetails"]["duration"]),
                "image": video["snippet"]["thumbnails"]["default"]["url"],
                "description": base64.b64encode(video["snippet"]["description"].encode("utf-8")).decode("utf-8")[:1900],
            },
            "ContentType": "audio/mpeg",
        },
    )


def handler(event, context):
    print(event, context)

    main(**event)


if __name__ == "__main__":
    main()
