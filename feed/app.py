import json
from xml.etree import ElementTree as ET

import boto3
import feedparser

BUCKET_NAME = "podcasts.gtmanfred.com"
BUCKET = boto3.resource("s3").Bucket(name=BUCKET_NAME)
s3 = boto3.client("s3")

client = boto3.client("lambda")

PODCASTS = json.load(BUCKET.Object(key="podcasts.json").get()["Body"])
NAMESPACE = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def _get_feed_url(podcast):
    if playlist := podcast.get("playlist", None):
        return f'https://www.youtube.com/feeds/videos.xml?playlist_id={playlist}'
    return f'https://www.youtube.com/feeds/videos.xml?channel_id={podcast["channel_id"]}'


def main():
    for podcast in PODCASTS:
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
            if item.yt_videoid == last:
                break
            if idx == 0:
                new_last = item.yt_videoid
            queue_video(item.title, item.yt_videoid, podcast["location"])
        BUCKET.Object(key=f'{podcast["location"]}/last.txt').put(
            Body=new_last,
        )


def queue_video(title, videoid, location):
    print(f"Processing: {title}")
    print(
        client.invoke(
            FunctionName="download-youtube-audio",
            InvocationType="Event",
            Payload=json.dumps(
                {
                    "videoid": videoid,
                    "location": location,
                }
            ),
        )
    )


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
                event = {
                    "videoid": videoid,
                    "location": podcast["location"],
                }
                break
        else:
            raise Exception("podcast not tracked")
        queue_video(title, videoid, podcast["location"])
    else:
        main()
    return {"statusCode": 200, "body": ""}


if __name__ == "__main__":
    main()
