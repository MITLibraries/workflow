import base64
from datetime import datetime
import json
import logging
import os

from airflow import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import BranchPythonOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.mit import ECSOperator
from airflow.sensors.mit import ECSTaskSensor
from airflow.hooks.S3_hook import S3Hook


network_config = json.loads(base64.b64decode(os.getenv('ECS_NETWORK_CONFIG')))
cluster = os.getenv('ECS_CLUSTER')
es_url = os.getenv('ES_URL')


def set_s3():
    today = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    s3_key = "s3://aspace-oai-s3-stage/{file}.xml".format(file=today)
    logging.info(s3_key)
    return s3_key


def check_if_records(**context):
    ti = context['ti']
    s3_key = ti.xcom_pull(task_ids='set_s3')
    logging.info(s3_key)
    hook = S3Hook()

    if hook.check_for_key(s3_key) is False:
        return 'no_records_to_harvest'
    return 'harvest_step_3'


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
                                 'command': ["--out={{ task_instance.xcom_pull(task_ids='set_s3') }}",
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

check_records = BranchPythonOperator(task_id='records_check',
                                     dag=dag,
                                     provide_context=True,
                                     python_callable=check_if_records,)

no_records_to_harvest = DummyOperator(
    task_id='no_records_to_harvest'
)

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

set_s3 >> harvest >> monitor_harvest >> check_records
check_records >> ingest >> monitor_ingest
check_records >> no_records_to_harvest
