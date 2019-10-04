========
Workflow
========

This is the MIT Libraries' `Airflow <https://airflow.apache.org/>`_ implementation. **Please read these instructions carefully, because this is very much a shared codebase.**

.. contents:: Table of Contents
.. section-numbering::

Intro
-----

This repo contains a few different things. The main attraction is the ``workflows`` directory which contains all our `Airflow DAGs <http://airflow.apache.org/concepts.html#dags>`_. There is also the Docker infrastructure used for deploying, both locally for development and in production. Finally, there's a custom Python command line tool for performing various maintenace tasks on the Fargate cluster.

Workflows
---------

The main thing to remember is that all our workflows go in the ``workflows`` directory and are deployed together. If you follow our usual GitHub practices, this shouldn't be a problem. A general overview of the process for publishing a new workflow will look like this:

1. Create your new workflow and test it locally.
2. Commit your changes and create a PR.
3. Wait for the changes to be deployed in the staging cluster to verify they are working as expected.
4. Get your PR approved and merged.

Dependencies
^^^^^^^^^^^^

One thing that may be confusing at first is how dependencies are handled for a workflow. The answer is pretty simple, if somewhat unsastisfying: all workflows share the same dependencies. Everything goes in the same bucket. This is a function of how Airflow is built.

When you need a new dependency for your workflow use ``pipenv`` the way you normally would::

  $ pipenv install <dependency>

It will be incumbent upon all of us to keep an eye on which dependency versions have changed in a PR and also ensure *that we have a good test suite for our workflows*.

Workflow Tips and Things to Remember
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Make your workflow idempotent. This is a distributed system and all sorts of things may cause your task to fail and then be run again. It should be able to tolerate this uncertainty.
- It's better to have several small tasks than a single large task for your workflow. The Airflow worker nodes will need to be restarted from time to time for different reasons. When a node is restarted, it's given about 2 minutes for any tasks currently running to finish at which point it is forceably killed.
- Airflow schedules tasks to be run, but there are no hard guarantees about when a scheduled task will actually be run as it depends on there being workers available to run it.

Developing Locally
------------------

You can use docker-compose to develop locally. First, you'll need to initialize the database. You only need to do this once::

  $ docker-compose -f init.yml run initialize

Now you can just run ``docker-compose up`` as usual. The Airflow web UI can be accessed at http://localhost:8080/admin/.

Put your workflows in the ``workflows`` directory. This directory gets copied to the container when it's built and is what will be used as the source of production workflows. When developing locally using docker-compose, this directory is mounted so any changes you make will get picked up in your running instance of Airflow. The scheduler is configured to scan this directory every 30 seconds in development.

If your workflow needs specific Python dependencies, you will need to install them using Pipenv and then rebuild the container::

  $ pipenv install <dependencies>
  $ make dist
  $ docker-compose down && docker-compose up

Cluster Maintenance
-------------------

This repo provides a ``workflow`` command for doing various maintenance tasks on the Fargate cluster. These mostly include user functions and database migrations. You will need to have AWS authentication configured on your machine to use this. To use the command::

  $ pipenv install
  $ pipenv run workflow

Deployment Notes
----------------

There are a number of unanswered questions about our deployment. I suspect some of these will have to be answered through experience.

- There's a note in the Airflow docs about setting the visibility timeout:

   Make sure to set a visibility timeout in [celery_broker_transport_options] that exceeds the ETA of your longest running task.

  The language used here is pretty confusing. To make matters worse, the Celery documentation on visibility timeout isn't much better. As best I can tell, the ETA doesn't have anything to do with how long a task takes to complete, it *only* affects the scheduling of a task. In Celery it's possible to asynchronously schedule a task to run at some point in the future. The time between scheduling this task and when it is supposed to be run is the ETA. The Celery docs also say that this is different from periodic tasks. I've searched the Airflow codebase and can't see that they are using ETA with Celery at all. My takeaway is that the visibility timeout is probably not something we need to worry about. If tasks mysteriously seem to keep getting rescheduled instead of being run, this might be something to look at.
