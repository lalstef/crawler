FROM python:3
ENV PYTHONUNBUFFERED 1

RUN mkdir /crawler
WORKDIR /crawler
COPY ./requirements.txt /crawler/
RUN pip install -r requirements.txt
COPY . /crawler/

CMD python crawl.py data/urls.csv