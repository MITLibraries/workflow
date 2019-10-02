# workflow

MIT Libraries Airflow implementation.

## Running Locally

First, initialize the database. You only need to do this once:

```
$ docker-compose -f init.yml run initialize
```

Now you can just run `docker-compose up` as usual.

The Airflow web UI can be accessed at http://localhost:8080/admin/.

## Adding Workflows

Put your workflows (DAGs in Airflow parlance) in the `workflows` directory. This directory gets copied to the container when it's built and is what will be used as the source of production workflows. When developing locally using docker-compose, this directory is mounted so any changes you make will get picked up in your running instance of Airflow. The scheduler is configured to scan this directory every 30 seconds in development.

If your workflow needs specific Python dependencies, you will need to install them using Pipenv and then rebuild the container:

```
$ pipenv install <dependencies>
$ make dist
$ docker-compose down && docker-compose up
```

## Cluster Maintenace

This repo provides a `workflow` command for doing various maintenance tasks on the Fargate cluster. These mostly include user functions and database migrations. You will need to have AWS authentication configured on your machine to use this. To use the command:

```
$ pipenv install
$ pipenv run workflow
```
