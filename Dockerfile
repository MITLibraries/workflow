FROM python:3.7-slim
ENV PIP_NO_CACHE_DIR yes
RUN \
  apt-get update -yqq && \
  apt-get install -yqq build-essential && \
  pip install --upgrade pip pipenv && \
  useradd -ms /bin/bash airflow

COPY Pipfile* /
RUN pipenv install --system --ignore-pipfile --deploy
COPY entrypoint.sh /
RUN mkdir -p /airflow/dags
RUN mkdir -p /airflow/plugins
COPY workflows/* /airflow/dags/
COPY mit /airflow/plugins/mit
RUN chown -R airflow:airflow /airflow

USER airflow
ENV AIRFLOW_HOME /airflow
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
