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

airflow "$@"
