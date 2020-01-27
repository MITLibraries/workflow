import base64
from datetime import datetime
import json
import os

from airflow import DAG
from airflow.operators.mit import ECSOperator
from airflow.operators.mit import ECSTaskSensor
from airflow.operators.python_operator import PythonOperator
import boto3


env = os.getenv('AIRFLOW_ENVIRONMENT')
bucket = 'dip-aleph-s3-prod' if env == 'prod' else 'dip-aleph-s3-stage'
cluster = os.getenv('ECS_CLUSTER')
netconfig = json.loads(base64.b64decode(os.getenv('ECS_NETWORK_CONFIG', '')))


dag = DAG('geoweb_marc_load',
          description='Loads MARC records into GeoWeb',
          start_date=datetime(2019, 12, 1),
          schedule_interval='0 0 2 * *')


def get_filepath():
    s3 = boto3.resource('s3')
    b = s3.Bucket(bucket)
    prefix = datetime.utcnow().strftime('%Y%m01')
    fnames = [o.key for o in b.objects.filter(Prefix=prefix)
              if o.key.endswith('edsall.mrc')]
    return f's3://{bucket}/{fnames[0]}'


s3_filepath = PythonOperator(task_id='s3_filepath',
                             python_callable=get_filepath,
                             dag=dag)


overrides = {
    'containerOverrides': [{
        'command': [
            'marc',
            '--solr', f'http://solr-{env}.mitlib.net:8983/solr/geoweb',
            '{{ task_instance.xcom_pull(task_ids="s3_filepath") }}',
        ],
        'name': f'slingshot-{env}',
    }],
    'taskRoleArn': f'arn:aws:iam::672626379771:role/airflow-{env}-workflow-task'
}


load_marc = ECSOperator(task_id='load_marc',
                        cluster=cluster,
                        task_definition=f'slingshot-{env}',
                        overrides=overrides,
                        network_configuration=netconfig,
                        dag=dag)


load_marc_watcher = ECSTaskSensor(task_id='load_marc_sensor',
                                  ecs_task_id='load_marc',
                                  cluster=cluster,
                                  dag=dag)


s3_filepath >> load_marc >> load_marc_watcher
