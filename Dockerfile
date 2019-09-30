FROM python:3.7-slim
ENV PIP_NO_CACHE_DIR yes
RUN apt-get update -yqq && apt-get install -yqq build-essential
RUN pip install --upgrade pip
RUN pip install pipenv

COPY Pipfile* /
RUN pipenv install --system --ignore-pipfile --deploy
COPY entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
