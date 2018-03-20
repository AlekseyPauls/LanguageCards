FROM ubuntu:16.04
RUN apt-get -y update
RUN apt-get install -y python3 && apt-get install -y python3-pip
RUN mkdir /code
WORKDIR /code
ADD requirements.txt /code/
RUN pip3 install -r requirements.txt
ADD . /code/