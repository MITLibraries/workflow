from collections import namedtuple
import json
from unittest import mock

import boto3
from moto import mock_ecs, mock_ec2
from moto.ec2.utils import generate_instance_identity_document
import pytest

from manager.cluster import Cluster


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'foo')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'correct horse battery staple')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'baz')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')


@pytest.fixture
def cluster():
    """Create the mock Airflow cluster.

    moto doesn't support the Fargate launch type, so we have to pretend
    like we're going to launch our containers in EC2. There's a little
    hand waving to make this work. moto comes with some predefined images
    that seem to work fine.

    Also see the ``patch_cluster_config`` fixture below.
    """
    C = namedtuple('C', ['name', 'scheduler', 'worker', 'web'])
    cluster = C('airflow-test', 'airflow-test-scheduler',
                'airflow-test-worker', 'airflow-test-web')
    with mock_ecs(), mock_ec2():
        ec2_client = boto3.client('ec2')
        ec2 = boto3.resource('ec2')
        ecs = boto3.client('ecs')

        image = ec2_client.describe_images()['Images'][0]
        instance = ec2.create_instances(ImageId=image['ImageId'], MinCount=1,
                                        MaxCount=1)[0]
        doc = json.dumps(generate_instance_identity_document(instance))
        ecs.create_cluster(clusterName=cluster.name)
        ecs.register_container_instance(cluster=cluster.name,
                                        instanceIdentityDocument=doc)
        for service in cluster[1:]:
            ecs.register_task_definition(family=service,
                                         containerDefinitions=[])
            ecs.create_service(cluster=cluster.name,
                               serviceName=service,
                               desiredCount=1,
                               taskDefinition=f'{service}:1')
        ecs.update_service(cluster=cluster.name,
                           service=cluster.worker,
                           desiredCount=3)
        yield cluster


@pytest.fixture(autouse=True)
def patch_cluster_config():
    """Patch the private config method on Cluster.

    moto does not add the networkConfiguration to the service description.
    Rather than just patching the whole thing, this effectively provides a
    runtime decorator on the ``Cluster.__get_config`` method to augment the
    reponse.
    """
    def wraps(f):
        def wrapped(*args, **kwargs):
            network_config = {
                'awsvpcConfiguration': {
                    'subnets': ['awesome-subnet', 'dumb-subnet']
                }
            }
            res = f(*args, **kwargs)
            [r.update(networkConfiguration=network_config) for r in res]
            return res
        return wrapped
    func = wraps(Cluster._Cluster__get_config)
    with mock.patch.object(Cluster, '_Cluster__get_config', func):
        yield
