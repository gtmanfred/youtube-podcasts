FROM python:3.12

COPY --from=mwader/static-ffmpeg /ffmpeg /bin/ffmpeg

ADD requirements.txt  .
RUN pip3 install -r requirements.txt

COPY app.py app.py

CMD [ "python", "-m", "app" ]
