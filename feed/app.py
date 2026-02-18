import json
import traceback
from urllib.parse import urlparse, parse_qs
from xml.etree import ElementTree as ET

import boto3
import feedparser
import requests

BUCKET_NAME = "podcasts.gtmanfred.com"
BUCKET = boto3.resource("s3").Bucket(name=BUCKET_NAME)
s3 = boto3.client("s3")

client = boto3.client("sqs")

PODCASTS = json.load(BUCKET.Object(key="podcasts.json").get()["Body"])
NAMESPACE = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def _get_feed_url(podcast):
    if playlist := podcast.get("playlist", None):
        if podcast.get("unlisted", False) is True:
            return requests.get(f"https://rsshub.cups.moe/youtube/playlist/{playlist}").text
        return f'https://www.youtube.com/feeds/videos.xml?playlist_id={playlist}'
    return f'https://www.youtube.com/feeds/videos.xml?channel_id={podcast["channel_id"]}'


def main():
    for podcast in PODCASTS:
        new_last = None
        feed = feedparser.parse(_get_feed_url(podcast))

        try:
            new_last = last = (
                BUCKET.Object(key=f'{podcast["location"]}/last.txt')
                .get()["Body"]
                .read()
                .decode("utf-8")
                .strip()
            )
        except s3.exceptions.NoSuchKey:
            last = None
        for idx, item in enumerate(feed.entries):
            unlisted = podcast.get("unlisted", False)
            if unlisted is True:
                videoid = parse_qs(urlparse(item.link).query)["v"][0]
            else:
                videoid = item.yt_videoid

            if unlisted is not True and videoid == last:
                break
            if idx == 0:
                new_last = videoid

            queue_video(item.title, videoid, podcast["location"])
        if new_last is not None:
            BUCKET.Object(key=f'{podcast["location"]}/last.txt').put(
                Body=new_last,
            )


def queue_video(title, videoid, location):
    try:
        print(f"Processing: {title}")
        print(
            client.send_message(
                QueueUrl="https://sqs.us-east-1.amazonaws.com/599874236268/download-youtube-audio",
                MessageBody=json.dumps({
                    "videoid": videoid,
                    "location": location,
                }),
            )
        )
    except Exception:
        print(traceback.format_exc())


def handler(event, context):
    print(event, context)

    params = event.get("queryStringParameters")
    body = event.get("body")
    headers = event.get("headers", {})

    if params:
        return {"statusCode": 200, "body": params["hub.challenge"]}
    elif headers.get("Content-Type", "") == "application/atom+xml" and body:
        entry = ET.fromstring(body).find("atom:entry", NAMESPACE)
        videoid = entry.find("yt:videoId", NAMESPACE).text
        title = entry.find("atom:title", NAMESPACE).text
        channel_id = entry.find("yt:channelId", NAMESPACE).text
        for podcast in PODCASTS:
            if podcast["channel_id"] == channel_id:
                break
        else:
            raise Exception("podcast not tracked")
        queue_video(title, videoid, podcast["location"])
    else:
        main()
    return {"statusCode": 200, "body": ""}


if __name__ == "__main__":
    main()
