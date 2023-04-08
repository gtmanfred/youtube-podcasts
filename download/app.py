import glob
import json
import os
import subprocess
import time
from datetime import datetime
from urllib.request import Request
from urllib.request import urlopen
from xml.etree import ElementTree as ET

import boto3

BUCKET_NAME = 'podcasts.gtmanfred.com'
BUCKET = boto3.resource('s3').Bucket(name=BUCKET_NAME)

NAMESPACE = {
    'atom': 'http://www.w3.org/2005/Atom',
    'yt': 'http://www.youtube.com/xml/schemas/2015',
}
PODCASTS = json.load(BUCKET.Object(key='podcasts.json').get()['Body'])

APIKEY = os.getenv('YOUTUBE_API_KEY')


def _get_video_mp3(videoid):
    files = glob.glob(f'/tmp/*{videoid}*.mp3')
    if not files:
        return None
    return files[0]


def _duration(duration):
    try:
        return datetime.strptime(duration, 'PT%HH%MM%SS').strftime('%H:%M:%S')
    except ValueError:
        try:
            return datetime.strptime(duration, 'PT%MM%SS').strftime('%M:%S')
        except ValueError:
            try:
                return datetime.strptime(duration, 'PT%HH%SS').strftime('%H:%M:%S')
            except ValueError:
                return datetime.strptime(duration, 'PT%HH%MM').strftime('%H:%M:%S')



def _publish_date(date):
    return datetime.strptime(
        date, '%Y-%m-%dT%H:%M:%SZ'
    ).strftime('%Y-%m-%d %H:%M:%S')


def _get_video(videoid):
    url = f'https://www.googleapis.com/youtube/v3/videos?id={videoid}&key={APIKEY}&part=contentDetails,snippet'
    req = Request(
        method='GET',
        url=url,
    )
    return json.load(urlopen(req))['items'][0]


def main(videoid, location):
    while subprocess.run((
        'python3 -m yt_dlp -c -x --embed-thumbnail '
        '--audio-format mp3 -o "/tmp/%(title)s[%(id)s].%(ext)s" '
        '--cache-dir /tmp/yt-dlp/ -- '
        f'{videoid}'
    ), shell=True).returncode:
        time.sleep(5)

    mp3_file = _get_video_mp3(videoid)

    video = _get_video(videoid)

    BUCKET.upload_file(
        Filename=mp3_file,
        Key=f'{location}/{os.path.basename(mp3_file)}',
        ExtraArgs={
            'Metadata': {
                'videoid': videoid,
                'pubdate': _publish_date(video['snippet']['publishedAt']),
                'title': video['snippet']['title'],
                'duration': _duration(video['contentDetails']['duration']),
                'image': video['snippet']['thumbnails']['default']['url'],
            },
            'ContentType': 'audio/mpeg',
        },
    )


def handler(event, context):
    print(event, context)

    if isinstance(event, dict):
        if params := event.get('queryStringParameters'):
            return {'statusCode': 200, 'body': params['hub.challenge']}
    else:
        entry = ET.fromstring(event).find("atom:entry", NAMESPACE)
        videoid = entry.get('yt:videoId', NAMESPACE)
        channel_id = entry.get('yt:channelId', NAMESPACE)
        for podcast in PODCASTS:
            if podcast['channel_id'] == channel_id:
                event = {
                    'videoid': videoid,
                    'location': podcast['location'],
                }
                break
        else:
            raise Exception('podcast not tracked')

    main(**event)


if __name__ == '__main__':
    main()
