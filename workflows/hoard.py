import base64
from datetime import datetime
import json
import os

from airflow import DAG
from airflow.operators.mit import ECSOperator
from airflow.sensors.mit import ECSTaskSensor


network_config = json.loads(base64.b64decode(os.getenv("ECS_NETWORK_CONFIG")))
cluster = os.getenv("ECS_CLUSTER")
air_env = os.getenv("AIRFLOW_ENVIRONMENT", "stage")
rdr_urls = {"stage": "https://rdr-demo-stage-app.mitlib.net/"}

jpal = DAG(
    "hoard_jpal_harvest",
    description="Harvests data from JPAL",
    start_date=datetime(2020, 10, 20),
    schedule_interval="@weekly",
    catchup=False,
)

jpal_task = ECSOperator(
    task_id="jpal_harvest",
    dag=jpal,
    cluster=cluster,
    task_definition=f"airflow-{air_env}-hoard",
    overrides={
        "containerOverrides": [
            {
                "command": [
                    "ingest",
                    "jpal",
                    "https://dataverse.harvard.edu/oai",
                    "-u",
                    rdr_urls[air_env],
                ],
                "name": f"airflow-{air_env}-hoard",
            }
        ]
    },
    network_configuration=network_config,
)

jpal_monitor = ECSTaskSensor(
    task_id="jpal_monitor", dag=jpal, cluster=cluster, ecs_task_id="jpal_harvest"
)

jpal_task >> jpal_monitor
