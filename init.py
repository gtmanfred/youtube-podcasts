import argparse
import functools
import json
import os
import time
from urllib.request import Request
from urllib.request import urlopen

import boto3


APIKEY = os.getenv("YOUTUBE_API_KEY")
client = boto3.client("lambda")


def _get_channel(channel_id, token=None):
    url = f"https://www.googleapis.com/youtube/v3/search?key={APIKEY}&part=id&type=video&channelId={channel_id}"
    if token:
        url += f"&pageToken={token}"
    req = Request(
        method="GET",
        url=url,
    )
    return json.load(urlopen(req))


def _get_playlist(playlist_id, token=None):
    url = f"https://www.googleapis.com/youtube/v3/playlistItems?key={APIKEY}&part=snippet&playlistId={playlist_id}"
    if token:
        url += f"&pageToken={token}"
    req = Request(
        method="GET",
        url=url,
    )
    return json.load(urlopen(req))


def _get_location(channel_id):
    with open("podcasts.json") as fh_:
        podcasts = json.load(fh_)
    for podcast in podcasts:
        if podcast["channel_id"] == channel_id:
            return podcast["location"]
    raise Exception("Podcast not found")


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel-id", "-c")
    parser.add_argument("--playlist-id", "-p", default=None)
    return parser.parse_args()


def _queue_video(video, location):
    return client.invoke(
        FunctionName="download-youtube-audio",
        InvocationType="Event",
        Payload=json.dumps(
            {
                "videoid": video,
                "location": location,
            }
        ),
    )


def main():
    args = _parse_args()
    token = False
    location = _get_location(args.channel_id)
    while token is not None:
        if args.playlist_id:
            videos = _get_playlist(args.playlist_id, token)
            for video in videos["items"]:
                print(_queue_video(video["snippet"]["resourceId"]["videoId"], location))
        else:
            videos = _get_channel(args.channel_id, token)
            for video in videos["items"]:
                if video["id"]["kind"] == "youtube#video":
                    print(_queue_video(video["id"]["videoId"], location))
        token = videos.get("nextPageToken", None)


if __name__ == "__main__":
    main()
