from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
import boto3


class ECSOperator(BaseOperator):
    @apply_defaults
    def __init__(self,
                 cluster,
                 task_definition,
                 overrides,
                 network_configuration,
                 launch_type='FARGATE',
                 **kwargs):
        super().__init__(**kwargs)
        self.cluster = cluster
        self.task_definition = task_definition
        self.overrides = overrides
        self.launch_type = launch_type
        self.network_configuration = network_configuration

    def execute(self, context):
        ecs = boto3.client('ecs')
        res = ecs.run_task(
                cluster=self.cluster,
                taskDefinition=self.task_definition,
                overrides=self.overrides,
                count=1,
                launchType=self.launch_type,
                startedBy='Airflow',
                networkConfiguration=self.network_configuration)
        if len(res['failures']) > 0:
            raise Exception(res)
        return res['tasks'][0]['taskArn']
