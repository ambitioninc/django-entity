FROM python:3.9

WORKDIR /django-entity

COPY requirements/*.txt /tmp

RUN pip install -r /tmp/requirements.txt
RUN pip install -r /tmp/requirements-testing.txt
