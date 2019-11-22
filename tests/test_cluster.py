import boto3
import jmespath

from manager.cluster import Cluster


def test_run_task_returns_taskarn(cluster):
    ecs = boto3.client('ecs')
    c = Cluster('airflow-test', 'airflow-test-scheduler',
                'airflow-test-worker', 'airflow-test-web', ecs)
    assert c.run_task({'command': ['run_things']})\
        .startswith('arn:aws:ecs:us-east-1:012345678910:task/')


def test_stop_sets_desired_count_to_zero(cluster):
    ecs = boto3.client('ecs')
    Cluster(*cluster, ecs).stop()
    res = ecs.describe_services(cluster=cluster.name, services=cluster[1:])
    assert jmespath.search('services[].desiredCount', res) == [0, 0, 0]


def test_stop_stops_specified_service(cluster):
    ecs = boto3.client('ecs')
    c = Cluster(*cluster, ecs)
    c.stop(services=[c.scheduler])
    res = ecs.describe_services(cluster=cluster.name, services=cluster[1:])
    assert jmespath.search(
        f"services[?serviceName=='{cluster.scheduler}'].desiredCount|[0]",
        res) == 0
    assert jmespath.search(
        f"services[?serviceName=='{cluster.web}'].desiredCount|[0]",
        res) == 1


def test_start_sets_desired_count(cluster):
    ecs = boto3.client('ecs')
    c = Cluster(*cluster, ecs)
    c.stop()
    c.start()
    res = ecs.describe_services(cluster=cluster.name, services=cluster[1:])
    assert jmespath.search('services[].desiredCount', res) == [1, 1, 1]


def test_start_starts_specified_service(cluster):
    ecs = boto3.client('ecs')
    c = Cluster(*cluster, ecs)
    c.stop()
    c.start(services=[c.scheduler])
    res = ecs.describe_services(cluster=cluster.name, services=cluster[1:])
    assert jmespath.search(
        f"services[?serviceName=='{cluster.scheduler}'].desiredCount|[0]",
        res) == 1
    assert jmespath.search(
        f"services[?serviceName=='{cluster.web}'].desiredCount|[0]",
        res) == 0
