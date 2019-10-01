#!/bin/sh
set -e


trap flush_logs EXIT

# Make sure ECS does not drop our logs
flush_logs()
{
  code=$?
  sleep 5
  exit $code
}

initialize()
{
  if [ -n "$AIRFLOW_FIRST_RUN" ]; then
    airflow initdb
    exit
  else
    airflow upgradedb
  fi
}

initialize && airflow "$@"
