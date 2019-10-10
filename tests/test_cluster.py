import boto3
import jmespath

from manager.cluster import Cluster


def test_run_task_returns_taskarn(cluster):
    c = Cluster('airflow-test', 'scheduler', 'worker', 'web')
    assert c.run_task({'command': ['run_things']})\
        .startswith('arn:aws:ecs:us-east-1:012345678910:task/')


def test_stop_sets_desired_count_to_zero(cluster):
    ecs = boto3.client('ecs')
    Cluster(*cluster).stop()
    res = ecs.describe_services(cluster=cluster.name, services=cluster[1:])
    for service in res['services']:
        assert service['desiredCount'] == 0


def test_start_sets_resets_desired_count(cluster):
    ecs = boto3.client('ecs')
    c = Cluster(*cluster)
    c.stop()
    c.start()
    res = ecs.describe_services(cluster=cluster.name, services=cluster[1:])
    assert jmespath.search(
        f"services[?serviceName=='{cluster.worker}'].desiredCount|[0]",
        res) == 3
    assert jmespath.search(
        f"services[?serviceName=='{cluster.scheduler}'].desiredCount|[0]",
        res) == 1
    assert jmespath.search(
        f"services[?serviceName=='{cluster.web}'].desiredCount|[0]",
        res) == 1
