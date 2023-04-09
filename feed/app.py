import json

import boto3
import feedparser

BUCKET_NAME = 'podcasts.gtmanfred.com'
BUCKET = boto3.resource('s3').Bucket(name=BUCKET_NAME)
s3 = boto3.client('s3')

client = boto3.client('lambda')

PODCASTS = json.load(BUCKET.Object(key='podcasts.json').get()['Body'])


def main():
    for podcast in PODCASTS:
        feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={podcast["channel_id"]}'
        feed = feedparser.parse(feed_url)

        try:
            new_last = last = BUCKET.Object(key=f'{podcast["location"]}/last.txt').get()['Body'].read().decode('utf-8').strip()
        except s3.exceptions.NoSuchKey:
            last = None
        for idx, item in enumerate(feed.entries):
            if item.yt_videoid == last:
                break
            if idx == 0:
                new_last = item.yt_videoid
            print(f'Processing: {item.title}')
            print(client.invoke(
                FunctionName='download-youtube-audio',
                InvocationType='Event',
                Payload=json.dumps({
                    'videoid': item.yt_videoid,
                    'location': podcast['location'],
                })
            ))
        BUCKET.Object(key=f'{podcast["location"]}/last.txt').put(Body=new_last.encode('utf-8'))


def handler(event, context):
    print(event, context)
    main()
    return {'statusCode': 200, 'body': ''}


if __name__ == '__main__':
    main()
