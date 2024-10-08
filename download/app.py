import base64
import glob
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from urllib.request import Request
from urllib.request import urlopen

import boto3

BUCKET_NAME = "podcasts.gtmanfred.com"
BUCKET = boto3.resource("s3").Bucket(name=BUCKET_NAME)
QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/599874236268/download-youtube-audio"


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
            "-vvv --cache-dir /tmp/yt-dlp/ -- "
            f"{videoid}"
        ),
        shell=True,
        stderr=subprocess.STDOUT,
    )


def _check_video_exists(videoid, location):
    for obj in BUCKET.objects.filter(Prefix=location):
        if videoid in obj.key:
            return True
    return False


def run(videoid, location):
    if _check_video_exists(videoid, location):
        return

    retries = 5
    while retries and (result := _download_video(videoid)).returncode:
        if "Private video." in result.stderr.decode("utf-8"):
            print(result.stderr)
            return
        time.sleep(5)
        retries -= 1

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
                "description": base64.b64encode(video["snippet"]["description"][:1000].encode("utf-8")).decode("utf-8"),
            },
            "ContentType": "audio/mpeg",
        },
    )


def __msg_keepalive(event, handle):
    client = boto3.client("sqs")
    while True:
        if event.is_set():
            break

        client.change_message_visibility(
            QueueUrl=QUEUE_URL,
            ReceiptHandle=handle,
            VisibilityTimeout=30,
        )
        event.wait(15)


def main():
    timeout = 30
    client = boto3.client("sqs")
    while True:
        messages = client.receive_message(
            QueueUrl=QUEUE_URL,
            VisibilityTimeout=timeout,
            WaitTimeSeconds=5,
        )
        for msg in messages["Messages"]:
            retcode = 1
            stop_event = threading.Event()

            try:
                thread = threading.Thread(
                    target=__msg_keepalive,
                    args=(stop_event, msg["ReceiptHandle"]),
                )
                thread.daemon = True
                thread.start()

                retcode = run(**json.loads(msg["Body"]))

            except Exception:
                pass

            else:
                client.delete_message(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=msg["ReceiptHandle"],
                )

            finally:
                stop_event.set()


if __name__ == "__main__":
    main()
