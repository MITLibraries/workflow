from airflow.sensors.base_sensor_operator import BaseSensorOperator
from airflow.utils.decorators import apply_defaults
import boto3


class ECSTaskSensor(BaseSensorOperator):
    @apply_defaults
    def __init__(self,
                 cluster,
                 ecs_task_id,
                 mode='reschedule',
                 *args,
                 **kwargs):
        super().__init__(*args, mode=mode, **kwargs)
        self.cluster = cluster
        self.ecs_task_id = ecs_task_id

    def poke(self, context):
        ecs = boto3.client('ecs')
        arn = context['task_instance'].xcom_pull(task_ids=self.ecs_task_id)
        res = ecs.describe_tasks(cluster=self.cluster, tasks=[arn])
        if len(res['failures']) > 0:
            raise Exception(res)

        task = res['tasks'][0]
        if task['lastStatus'] != 'STOPPED':
            return False
        cntr = task['containers'][0]
        if cntr['exitCode'] > 0:
            raise Exception(
                    f'Container exited with exit code {cntr["exitCode"]}')
        return True
