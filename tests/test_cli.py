import re

import boto3
from click.testing import CliRunner
import jmespath
import pytest

from manager.cli import main


arn_search = re.compile(r'arn:aws:ecs:us-east-1:012345678910:task/[0-9a-z-]+')
command_search = jmespath.compile(
        'tasks[0].overrides.containerOverrides[0].command')


@pytest.fixture
def cluster_opts(cluster):
    return ['--cluster', cluster.name, '--scheduler', cluster.scheduler,
            '--worker', cluster.worker, '--web', cluster.web]


def test_adds_user(cluster, cluster_opts):
    ecs = boto3.client('ecs')
    res = CliRunner().invoke(main, [
            *cluster_opts,
            'add-user',
            '-u', 'lucy',
            '-e', 'lucy@example.com',
            '-f', 'Lucy',
            '-l', 'Cat',
            '-r', 'Admin',
            '--password', 'meow'])
    assert res.exit_code == 0
    assert res.output.startswith('Task scheduled:')
    arn = arn_search.search(res.output)
    tasks = ecs.describe_tasks(cluster=cluster.name, tasks=[arn.group()])
    command = command_search.search(tasks)
    assert command == ['create_user', '-u', 'lucy', '-e', 'lucy@example.com',
                       '-f', 'Lucy', '-l', 'Cat', '-p', 'meow', '-r', 'Admin']


def test_deletes_user(cluster, cluster_opts):
    ecs = boto3.client('ecs')
    res = CliRunner().invoke(main, [
            *cluster_opts,
            'delete-user',
            '-u', 'lucy'])
    assert res.exit_code == 0
    assert res.output.startswith('Task scheduled:')
    arn = arn_search.search(res.output)
    tasks = ecs.describe_tasks(cluster=cluster.name, tasks=[arn.group()])
    command = command_search.search(tasks)
    assert command == ['delete_user', '-u', 'lucy']


def test_upgrades_db(cluster, cluster_opts):
    ecs = boto3.client('ecs')
    res = CliRunner().invoke(main, [
            *cluster_opts,
            'upgradedb'])
    assert res.exit_code == 0
    assert res.output.startswith('Task scheduled:')
    arn = arn_search.search(res.output)
    tasks = ecs.describe_tasks(cluster=cluster.name, tasks=[arn.group()])
    command = command_search.search(tasks)
    assert command == ['upgradedb']


def test_rotates_fernet_key(cluster, cluster_opts):
    ecs = boto3.client('ecs')
    res = CliRunner().invoke(main, [
            *cluster_opts,
            'rotate-fernet-key'])
    assert res.exit_code == 0
    assert res.output.startswith('Task scheduled:')
    arn = arn_search.search(res.output)
    tasks = ecs.describe_tasks(cluster=cluster.name, tasks=[arn.group()])
    command = command_search.search(tasks)
    assert command == ['rotate_fernet_key']


def test_initializes_cluster(cluster, cluster_opts):
    ecs = boto3.client('ecs')
    res = CliRunner().invoke(main, [
            *cluster_opts,
            'initialize', '--yes'])
    assert res.exit_code == 0
    assert res.output.startswith('Task scheduled:')
    arn = arn_search.search(res.output)
    tasks = ecs.describe_tasks(cluster=cluster.name, tasks=[arn.group()])
    command = command_search.search(tasks)
    assert command == ['initdb']


def test_redeploys_cluster(cluster, cluster_opts):
    res = CliRunner().invoke(main, [
            *cluster_opts,
            'redeploy',
            '--yes',
            '--no-wait'])
    assert 'Stopping cluster...OK' in res.output
    assert 'Starting cluster...' in res.output
