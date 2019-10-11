from contextlib import contextmanager
import sys

import boto3
from botocore import waiter as boto_waiter
import click

from manager.cluster import Cluster, ecs_model


@click.group()
@click.option('--cluster', default='airflow-stage',
              help='Fargate cluster name. Defaults to airflow-stage.')
@click.option('--scheduler', default='airflow-stage-scheduler',
              help='Name of scheduler service. Defaults to '
                   'airflow-stage-scheduler.')
@click.option('--worker', default='airflow-stage-worker',
              help='Name of worker service. Defaults to airflow-stage-worker.')
@click.option('--web', default='airflow-stage-web',
              help='Name of web service. Defaults to airflow-stage-web.')
@click.pass_context
def main(ctx, cluster, scheduler, worker, web):
    """Run one-off tasks on a Fargate Airflow cluster.

    This tool can be used to run certain Airflow tasks on a Fargate cluster
    that would otherwise be difficult to run. It spins up a transient
    container using the same image used by the other Airflow containers.

    In order to get an appropriate network configuration it examines one
    of the existing services. All three services should have the same
    network configuration.

    The tool only schedules a task to be run. Check the AWS console to see
    if the container ran successfully.
    """
    ecs = boto3.client('ecs')
    cluster = Cluster(cluster, scheduler, worker, web, ecs)
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
    """Add an Airflow user.

    Note that all parameters are required.

    \b
    Example usage:

        $ workflow --cluster airflow-stage add-user -u foobar \
            -e foobar@example.com -f Foo -l Bar -r Admin
    """
    cluster = ctx.obj['cluster']
    command = ['create_user', '-u', username, '-e', email, '-f', firstname,
               '-l', lastname, '-p', password, '-r', role]
    with check_task():
        resp = cluster.run_task({'command': command})
    click.echo(f'Task scheduled: {resp}')


@main.command()
@click.option('-u', '--username', prompt=True)
@click.pass_context
def delete_user(ctx, username):
    """Delete an Airflow user."""
    cluster = ctx.obj['cluster']
    with check_task():
        resp = cluster.run_task({'command': ['delete_user', '-u', username]})
    click.echo(f'Task scheduled: {resp}')


@main.command()
@click.pass_context
def upgradedb(ctx):
    """Run Airflow's upgradedb command on the cluster."""
    cluster = ctx.obj['cluster']
    with check_task():
        resp = cluster.run_task({'command': ['upgradedb']})
    click.echo(f'Task scheduled: {resp}')


@main.command()
@click.pass_context
def rotate_fernet_key(ctx):
    """Rotate the fernet key.

    Read the documentation at
    https://airflow.apache.org/howto/secure-connections.html for the proper
    order in which to do this.
    """
    cluster = ctx.obj['cluster']
    with check_task():
        resp = cluster.run_task({'command': ['rotate_fernet_key']})
    click.echo(f'Task scheduled: {resp}')


@main.command()
@click.confirmation_option(prompt='Are you sure you want to initialize '
                                  'Airflow in the selected environment?')
@click.pass_context
def initialize(ctx):
    """Initialize a Fargate Airflow cluster.

    This should only be run once on an Airflow cluster. It will run Airflow's
    initdb command.

    \b
    Example usage:

        $ workflow --cluster airflow-stage initialize
    """
    cluster = ctx.obj['cluster']
    with check_task():
        resp = cluster.run_task({'command': ['initdb']})
    click.echo(f'Task scheduled: {resp}')


@main.command()
@click.confirmation_option(prompt='Are you sure you want to redeploy the '
                                  'selected cluster?')
@click.pass_context
def redeploy(ctx):
    """Redeploy Airflow cluster.

    This will perform a full redeploy of the Airflow cluster. The cluster
    has to be brought down and back up in a specific order or otherwise
    race conditions could arise. First, the scheduler is stopped. Then,
    the web and worker services are redeployed. Finally, the scheduler is
    started back up with the new deployment.

    *IMPORTANT* Always use this command to redeploy as it will ensure the
    system remains in a consistent state. It should be safe to run again
    even if it has previously failed partway through due to, for example,
    a network failure.

    It will take several minutes for the cluster to fully restart. Be patient.

    \b
    Example usage:

        $ workflow --cluster airflow-prod redeploy
    """
    cluster = ctx.obj['cluster']
    stop_waiter = boto_waiter.create_waiter_with_client('ServiceDrained',
                                                        ecs_model, cluster.ecs)
    start_waiter = cluster.ecs.get_waiter('services_stable')
    with check_task():
        cluster.stop(services=[cluster.scheduler])
        click.echo('Stopping scheduler.......', nl=False)
        stop_waiter.wait(cluster=cluster.name, services=[cluster.scheduler])
        click.echo("\033[1A")
        ok = click.style('OK', fg='green')
        click.echo(f'Stopping scheduler.......{ok}')

    with check_task():
        cluster.start(services=[cluster.worker, cluster.web])
        click.echo('Redeploying web/worker...', nl=False)
        start_waiter.wait(cluster=cluster.name,
                          services=[cluster.web, cluster.worker])
        click.echo("\033[1A")
        ok = click.style('OK', fg='green')
        click.echo(f'Redeploying web/worker...{ok}')

    with check_task():
        cluster.start(services=[cluster.scheduler])
        click.echo('Starting scheduler.......', nl=False)
        start_waiter.wait(cluster=cluster.name, services=[cluster.scheduler])
        click.echo("\033[1A")
        ok = click.style('OK', fg='green')
        click.echo(f'Starting scheduler.......{ok}')


@main.command()
@click.confirmation_option(prompt='Are you sure you want to stop the '
                                  'scheduler?')
@click.option('--wait/--no-wait', default=True,
              help='Wait for the scheduler to stop. This is the default '
                   'behavior.')
@click.pass_context
def stop_scheduler(ctx, wait):
    """Stop the scheduler service.

    Only one Airflow scheduler can be running at a time. During a new
    service redeploy through Terraform this would result in a brief period
    where two schedulers are running simultaneously. The process for
    deploying a new service should be to use this command to stop the
    scheduler, then deploy the new service through Terraform, then run the
    start-scheduler command.
    """
    cluster = ctx.obj['cluster']
    stop_waiter = boto_waiter.create_waiter_with_client('ServiceDrained',
                                                        ecs_model, cluster.ecs)
    with check_task():
        cluster.stop(services=[cluster.scheduler])
        click.echo('Stopping scheduler...', nl=False)
        if not wait:
            return
        stop_waiter.wait(cluster=cluster.name, services=[cluster.scheduler])
        click.echo("\033[1A")
        ok = click.style('OK', fg='green')
        click.echo(f'Stopping scheduler...{ok}')


@main.command()
@click.option('--wait/--no-wait', default=True,
              help='Wait for scheduler to start. This is the default '
                   'behavior.')
@click.pass_context
def start_scheduler(ctx, wait):
    """Start the scheduler service.

    This should only be necessary after running the stop-scheduler
    command, though it should be safe to run even if the scheduler is
    already running. This simply sets the desiredCount of the scheduler
    service to 1.
    """
    cluster = ctx.obj['cluster']
    start_waiter = cluster.ecs.get_waiter('services_stable')
    with check_task():
        cluster.start(services=[cluster.scheduler])
        click.echo('Starting scheduler...', nl=False)
        if not wait:
            return
        start_waiter.wait(cluster=cluster.name, services=[cluster.scheduler])
        click.echo("\033[1A")
        ok = click.style('OK', fg='green')
        click.echo(f'Starting scheduler...{ok}')


@contextmanager
def check_task():
    try:
        yield
    except Exception as e:
        click.echo(click.style(str(e), fg='red'))
        sys.exit(1)
