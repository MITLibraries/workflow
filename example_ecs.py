import base64
from datetime import datetime
import json
import os

from airflow import DAG
from airflow.operators.mit import ECSOperator
from airflow.sensors.mit import ECSTaskSensor


network_config = json.loads(base64.b64decode(os.getenv('ECS_NETWORK_CONFIG')))
cluster = os.getenv('ECS_CLUSTER')

dag = DAG('example',
          description='An example for running containerized workflows.',
          start_date=datetime.now())

task1 = ECSOperator(task_id='ex_step_1',
                    dag=dag,
                    cluster=cluster,
                    task_definition='example_task_definition',
                    overrides={},
                    network_configuration=network_config)

task2 = ECSTaskSensor(task_id='ex_step_2',
                      dag=dag,
                      cluster=cluster,
                      ecs_task_id='ex_step_1')

task1 >> task2
