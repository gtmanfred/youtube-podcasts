import base64
import json
import os
import uuid
from datetime import datetime
from urllib.parse import quote
from urllib.request import Request
from urllib.request import urlopen

import boto3
import pytz
from feedgen.feed import FeedGenerator

BUCKET_NAME = "podcasts.gtmanfred.com"
BUCKET = boto3.resource("s3").Bucket(name=BUCKET_NAME)

CLOUDFRONT = boto3.client("cloudfront")


UUID = uuid.UUID("ad6a3bfa-299a-4618-a84c-da2b145b26fd")

APIKEY = os.getenv("YOUTUBE_API_KEY")


def _get_video(videoid):
    url = f"https://www.googleapis.com/youtube/v3/videos?id={videoid}&key={APIKEY}&part=contentDetails,snippet"
    req = Request(
        method="GET",
        url=url,
    )
    return json.load(urlopen(req))["items"][0]


def main(location):
    fg = FeedGenerator()
    fg.load_extension("podcast")

    podcasts = json.load(BUCKET.Object(key="podcasts.json").get()["Body"])
    for podcast in podcasts:
        if podcast["location"] == location:
            break
    else:
        return

    base_url = f"http://podcasts.gtmanfred.com/{location}"
    fg.title(podcast["title"])
    fg.author(podcast["author"])
    fg.language("en")
    fg.link(href=base_url, rel="self")
    fg.description("Youtube feed converted to audio only")

    for objsum in BUCKET.objects.all():
        if not objsum.key.endswith("mp3"):
            continue
        if not objsum.key.startswith(location):
            continue
        obj = objsum.Object()
        print(obj.metadata)
        fe = fg.add_entry()
        name = os.path.basename(obj.key)
        fe.id(uuid.uuid5(UUID, name).hex)
        fe.title(obj.metadata["title"])
        description = obj.metadata.get("description", None)
        if description is not None and " " not in description:
            description = base64.b64decode(description).decode("utf-8")
        else:
            video = _get_video(obj.metadata["videoid"])
            description = video["snippet"]["description"]
            obj.metadata.update({"description": base64.b64encode(description.encode("utf-8")).decode("utf-8")})
            obj.copy_from(
                CopySource={
                    'Bucket': BUCKET_NAME,
                    'Key': obj.key,
                },
                Metadata=obj.metadata,
                MetadataDirective='REPLACE',
            )
        fe.description(description)
        fe.enclosure(f"{base_url}/{quote(name)}", 0, "audio/mpeg")
        fe.pubDate(
            datetime.strptime(
                obj.metadata["pubdate"],
                "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=pytz.UTC)
        )
        fe.podcast.itunes_duration(obj.metadata["duration"])
        fe.podcast.itunes_image(obj.metadata["image"])

    xml = "/tmp/podcast.xml"
    fg.rss_file(xml)
    BUCKET.upload_file(
        Filename=xml,
        Key=f"{location}/{os.path.basename(xml)}",
        ExtraArgs={
            "ContentType": "text/xml",
        },
    )
    CLOUDFRONT.create_invalidation(
        DistributionId="E31WFS9CP7QRX1",
        InvalidationBatch={
            "Paths": {
                "Quantity": 1,
                "Items": [f"/{location}/{os.path.basename(xml)}"],
            },
        },
    )


def handler(event, context):
    print(event, context)
    return
    location = os.path.dirname(event["Records"][0]["s3"]["object"]["key"])
    main(location)


if __name__ == "__main__":
    main("podcasts/tpk")
