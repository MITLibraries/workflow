from contextlib import contextmanager
import sys

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
    cluster = Cluster(cluster, scheduler, worker, web)
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
@click.option('--wait/--no-wait', default=True,
              help='Wait until the cluster has fully restarted before '
                   'exiting. This is the default behavior.')
@click.pass_context
def redeploy(ctx, wait):
    """Redeploy Airflow cluster.

    This will perform a full redeploy of the Airflow cluster. First, all
    containers in all services are stopped. Then, all containers in all
    services are restarted with a --force-new-deployment. A redeploy
    should be done when new workflows are added. This is the only way to
    sync the workflows across all containers.

    *IMPORTANT* You shouldn't try to force redeploy a single service as race
    conditions could arise. Always use this command to redeploy as it will
    ensure the system remains in a consistent state.

    By default, the command will wait until the cluster has been fully
    stopped and fully restarted until exiting. The --no-wait flag can be
    used to exit as soon as the ECS request to scale back up has been made.

    It may take several minutes for the cluster to fully restart. Be patient.

    \b
    Example usage:

        $ workflow --cluster airflow-prod redeploy
    """
    cluster = ctx.obj['cluster']
    stop_waiter = boto_waiter.create_waiter_with_client('ServiceDrained',
                                                        ecs_model, cluster.ecs)
    start_waiter = cluster.ecs.get_waiter('services_stable')
    with check_task():
        cluster.stop()
        click.echo('Stopping cluster...', nl=False)
        stop_waiter.wait(cluster=cluster.name, services=cluster.services)
        click.echo("\033[1A")
        ok = click.style('OK', fg='green')
        click.echo(f'Stopping cluster...{ok}')

    with check_task():
        cluster.start()
        if not wait:
            click.echo('Starting cluster...')
            return
        click.echo('Starting cluster...', nl=False)
        start_waiter.wait(cluster=cluster.name, services=cluster.services)
        click.echo("\033[1A")
        ok = click.style('OK', fg='green')
        click.echo(f'Starting cluster...{ok}')


@contextmanager
def check_task():
    try:
        yield
    except Exception as e:
        click.echo(click.style(str(e), fg='red'))
        sys.exit(1)
