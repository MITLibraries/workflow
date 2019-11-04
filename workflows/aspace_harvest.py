import base64
from datetime import datetime
import json
import os

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.mit import ECSOperator
from airflow.sensors.mit import ECSTaskSensor


network_config = json.loads(base64.b64decode(os.getenv('ECS_NETWORK_CONFIG')))
cluster = os.getenv('ECS_CLUSTER')
es_url = os.getenv('ES_URL')


def set_s3():
    today = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    return "s3://aspace-oai-s3-stage/{file}.xml".format(file=today)

dag = DAG('timdex_aspace_harvest',
          description='Harvests from aspace then ingests to TIMDEX.',
          start_date=datetime(2019, 10, 28))

set_s3 = PythonOperator(
    task_id='set_s3',
    dag=dag,
    python_callable=set_s3,
)

# Kick off oaiharvester fargate task
harvest = ECSOperator(task_id='harvest_step_1',
                      dag=dag,
                      cluster=cluster,
                      task_definition='airflow-stage-oaiharvester',
                      overrides={'containerOverrides': [{
                                 'command': ["--out={{ task_instance.xcom_pull(task_ids='set_s3', key='aspace_oai_s3_key') }}",
                                             '--host=https://archivesspace.mit.edu/oai',
                                             '--format=oai_ead',
                                             '--verbose', ],
                                 'name': 'airflow-stage-oaiharvester',
                                 }]},
                      network_configuration=network_config)

# Monitor oaiharvester fargate task
monitor_harvest = ECSTaskSensor(task_id='harvest_step_2',
                                dag=dag,
                                cluster=cluster,
                                ecs_task_id='harvest_step_1')

# ingest with mario fargate task
ingest = ECSOperator(task_id='harvest_step_3',
                     dag=dag,
                     cluster=cluster,
                     task_definition='airflow-stage-mario',
                     overrides={'containerOverrides': [{
                                  'command': ['--url=' + es_url,
                                              'ingest',
                                              '--prefix=aspace',
                                              '--type=archives',
                                              '--auto',
                                              '--debug',
                                              "{{ task_instance.xcom_pull(task_ids='set_s3') }}", ],
                                  'name': 'airflow-stage-mario',
                                  }]},
                     network_configuration=network_config)

# monitor mario fargate task
monitor_ingest = ECSTaskSensor(task_id='harvest_step_4',
                               dag=dag,
                               cluster=cluster,
                               ecs_task_id='harvest_step_3')

# alert to slack or something. longterm this is probs annoying. short term
# this seems prudent.

set_s3 >> harvest >> monitor_harvest >> ingest >> monitor_ingest
