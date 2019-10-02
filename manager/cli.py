import sys

import boto3
import click


@click.group()
@click.option('--environment', default='stage')
@click.option('--cluster', default='airflow')
@click.option('--service', default='scheduler')
@click.pass_context
def main(ctx, environment, cluster, service):
    """Run one-off tasks on a Fargate Airflow cluster.

    This tool can be used to run certain Airflow tasks on a Fargate cluster
    that would otherwise be difficult to run. It spins up a transient
    container using the same image used by the other Airflow containers.

    In order to get an appropriate network configuration it examines one
    of the existing services. The cluster and service names it uses are
    CLUSTER-ENVIRONMENT and CLUSTER-ENVIRONMENT-SERVICE, respectively.

    The tool only schedules a task to be run. Check the AWS console to see
    if the container ran successfully.
    """
    ecs = boto3.client('ecs')
    cluster = Cluster(f'{cluster}-{environment}',
                      f'{cluster}-{environment}-{service}',
                      ecs)
    ctx.ensure_object(dict)
    ctx.obj['cluster'] = cluster


@main.command()
@click.option('-u', '--username', prompt=True)
@click.option('-e', '--email', prompt=True)
@click.option('-f', '--firstname', prompt=True)
@click.option('-l', '--lastname', prompt=True)
@click.option('-r', '--role', prompt=True)
@click.password_option()
@click.pass_context
def add_user(ctx, username, email, firstname, lastname, role, password):
    """Add an Airflow user."""
    cluster = ctx.obj['cluster']
    command = ['create_user', '-u', username, '-e', email, '-f', firstname,
               '-l', lastname, '-p', password, '-r', role]
    try:
        resp = cluster.run_task({'command': command})
    except Exception as e:
        click.echo(click.style(str(e), fg='red'))
        sys.exit(1)
    click.echo(f'Task scheduled: {resp}')


@main.command()
@click.confirmation_option(prompt='Are you sure you want to initialize '
                                  'Airflow in the selected environment?')
@click.pass_context
def initialize(ctx):
    """Initialize a Fargate Airflow cluster.

    This should only be run once on an Airflow cluster. It will run Airflow's
    initdb command.
    """
    cluster = ctx.obj['cluster']
    try:
        resp = cluster.run_task({'command': ['initdb']})
    except Exception as e:
        click.echo(click.style(str(e), fg='red'))
        sys.exit(1)
    click.echo(f'Task scheduled: {resp}')


class Cluster:
    def __init__(self, cluster, service, client):
        self.ecs = client
        self.cluster = cluster
        self.service = service

    def run_task(self, overrides):
        default_overrides = {'name': self.service}
        default_overrides.update(overrides)
        resp = self.ecs.run_task(
                cluster=self.cluster,
                taskDefinition=self.service,
                overrides={'containerOverrides': [default_overrides]},
                count=1,
                launchType='FARGATE',
                networkConfiguration=self.__config['networkConfiguration'])
        return resp['tasks'][0]['taskArn']

    @property
    def __config(self):
        if not hasattr(self, '__service'):
            services = self.ecs.describe_services(cluster=self.cluster,
                                                  services=[self.service])
            if len(services['services']) == 0:
                raise Exception(f'No service called {self.service}')
            self.__service = services['services'][0]
        return self.__service
