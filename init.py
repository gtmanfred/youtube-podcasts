import argparse
import functools
import json
import os
from urllib.request import Request
from urllib.request import urlopen

import boto3


APIKEY = os.getenv('YOUTUBE_API_KEY')
client = boto3.client('lambda')


def _get_channel(channel_id, token=None):
    url = f'https://www.googleapis.com/youtube/v3/search?key={APIKEY}&part=id&channelId={channel_id}'
    if token:
        url += f'&pageToken={token}'
    req = Request(
        method='GET',
        url=url,
    )
    return json.load(urlopen(req))


def _get_location(channel_id):
    with open('podcasts.json') as fh_:
        podcasts = json.load(fh_)
    for podcast in podcasts:
        if podcast['channel_id'] == channel_id:
            return podcast['location']
    raise Exception('Podcast not found')


def main(channel_id):
    token = False
    location = _get_location(channel_id)
    while token is not None:
        videos = _get_channel(channel_id, token)
        for video in videos['items']:
            if video['id']['kind'] == 'youtube#video':
                print(client.invoke(
                    FunctionName='download-youtube-audio',
                    InvocationType='Event',
                    Payload=json.dumps({
                        'videoid': video['id']['videoId'],
                        'location': location,
                    }),
                ))
        token = videos.get('nextPageToken', None)


if __name__ == '__main__':
    CHANNEL_ID = 'UC0ekuNwrjkPr5EGom2_XFLA'
    main(CHANNEL_ID)