import re

import boto3
import pytest

from mit.operators import ECSOperator


arn_search = re.compile(r'arn:aws:ecs:us-east-1:012345678910:task/[0-9a-z-]+')


@pytest.fixture
def task(cluster):
    task_name = 'workflow-task'
    ecs = boto3.client('ecs')
    ecs.register_task_definition(family=task_name, containerDefinitions=[])
    return task_name


def test_ecs_operator_runs_task(cluster, task):
    op = ECSOperator(cluster=cluster.name,
                     task_definition=task,
                     overrides={},
                     network_configuration={},
                     task_id='test')
    arn = op.execute(context={})
    assert arn_search.search(arn)
