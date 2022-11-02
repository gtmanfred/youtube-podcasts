FROM public.ecr.aws/lambda/python:3.8 as ffmpeg

# add FFMPEG
RUN yum install -y tar xz
RUN curl -s https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar xJ
RUN cp ffmpeg-*/ffmpeg /bin/ffmpeg
RUN rm -rf ffmpeg-*

FROM public.ecr.aws/lambda/python:3.8

COPY --from=ffmpeg /bin/ffmpeg /bin/ffmpeg

# Install the function's dependencies using file requirements.txt
# from your project folder.
ADD requirements.txt  .
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "app.handler" ]
