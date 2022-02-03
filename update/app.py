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

BUCKET_NAME = 'podcasts.gtmanfred.com'
BUCKET = boto3.resource('s3').Bucket(name=BUCKET_NAME)
PODCASTS = json.load(BUCKET.Object(key='podcasts.json').get()['Body'])

UUID = uuid.UUID('ad6a3bfa-299a-4618-a84c-da2b145b26fd')

APIKEY = os.getenv('YOUTUBE_API_KEY')


def _get_video(videoid):
    url = f'https://www.googleapis.com/youtube/v3/videos?id={videoid}&key={APIKEY}&part=contentDetails,snippet'
    req = Request(
        method='GET',
        url=url,
    )
    return json.load(urlopen(req))['items'][0]


def main(location):
    fg = FeedGenerator()
    fg.load_extension('podcast')

    for podcast in PODCASTS:
        if podcast['location'] == location:
            break
    else:
        return

    base_url = f'http://podcasts.gtmanfred.com/{location}'
    fg.title(podcast['title'])
    fg.author(podcast['author'])
    fg.language('en')
    fg.link(href=base_url, rel='self')
    fg.description('Youtube feed converted to audio only')

    for objsum in BUCKET.objects.all():
        if not objsum.key.endswith('mp3'):
            continue
        obj = objsum.Object()
        print(obj.metadata)
        video = _get_video(obj.metadata['videoid'])
        fe = fg.add_entry()
        name = os.path.basename(obj.key)
        fe.id(uuid.uuid5(UUID, name).hex)
        fe.title(obj.metadata['title'])
        description = video['snippet']['description']
        if isinstance(description, bytes):
            description = description.decode('utf-8')
        fe.description(description)
        fe.enclosure(f'{base_url}/{quote(name)}', 0, 'audio/mpeg')
        fe.pubDate(
            datetime.strptime(
                obj.metadata['pubdate'],
                '%Y-%m-%d %H:%M:%S',
            ).replace(tzinfo=pytz.UTC)
        )
        fe.podcast.itunes_duration(obj.metadata['duration'])
        fe.podcast.itunes_image(obj.metadata['image'])

    xml = '/tmp/podcast.xml'
    fg.rss_file(xml)
    BUCKET.upload_file(
        Filename=xml,
        Key=f'{location}/{os.path.basename(xml)}',
        ExtraArgs={
            'ContentType': 'text/xml',
        },
    )


def handler(event, context):
    print(event, context)
    location = os.path.dirname(event['Records'][0]['s3']['object']['key'])
    main(location)


if __name__ == '__main__':
    main('podcasts/jasoncordova')
