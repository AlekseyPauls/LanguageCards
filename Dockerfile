FROM python:3.6
LABEL description="Image with Language Cards app" \
      maintainer="Aleksey Pauls" \
      source="https://github.com/AlekseyPauls/LanguageCards/"
RUN apt-get -y update
RUN mkdir /code
WORKDIR /code
ADD requirements.txt /code/
RUN pip3 install -r requirements.txt
ADD . /code/
CMD ["python", "app.py"]