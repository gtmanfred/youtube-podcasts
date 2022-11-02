==========================
Podcast Feeds from Youtube
==========================

This repo contains the lambda container functions information for the operation
of <podcasts.gtmanfred.com>.

Workflow
========

Every day at 1am UTC, the feed lambda starts, and it will check podcasts.json
for a list of youtube channels to process. It will then invoke one download
event for every video it finds. The download lambda uses yt-dlp to download the
audio and convert it to mp3 and then upload it to s3 with the video file
metadata attached. When a new file is created in the s3 bucket, an event
triggers which will start the update lambda, which checks the location of the
s3 file, and rebuilds the podcast feed for that subdirectory in s3.

Deploying
=========

Hopefully this will automatically deploy on all changes using github actions.
