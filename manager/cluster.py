import boto3
from botocore import waiter
import jmespath


ecs_model = waiter.WaiterModel({
    'version': 2,
    'waiters': {
        'ServiceDrained': {
            'operation': 'DescribeServices',
            'delay': 6,
            'maxAttempts': 150,
            'acceptors': [
                {
                    'expected': 0,
                    'matcher': 'pathAll',
                    'state': 'success',
                    'argument': 'services[].runningCount',
                },
            ]
        }
    }
})


class Cluster:
    def __init__(self, cluster, scheduler, worker, web):
        self.name = cluster
        self.scheduler = scheduler
        self.worker = worker
        self.web = web

    def run_task(self, overrides):
        default_overrides = {'name': self.worker}
        default_overrides.update(overrides)
        resp = self.ecs.run_task(
                cluster=self.name,
                taskDefinition=self.worker,
                overrides={'containerOverrides': [default_overrides]},
                count=1,
                launchType='FARGATE',
                startedBy='AirController',
                networkConfiguration=self.__worker['networkConfiguration'])
        return resp['tasks'][0]['taskArn']

    def stop(self):
        # This needs to be set before stopping everything, because there
        # will be a variable number of workers. We need to know how many
        # to restart. This is a bit of hack because the value really needs
        # to come from the Terraform config.
        # TODO: Find a better way to handle this.
        self.num_workers = self.__worker['desiredCount']
        for service in self.services:
            self.ecs.update_service(cluster=self.name, service=service,
                                    desiredCount=0)

    def start(self):
        self.ecs.update_service(cluster=self.name,
                                service=self.scheduler,
                                desiredCount=1,
                                forceNewDeployment=True)
        self.ecs.update_service(cluster=self.name,
                                service=self.web,
                                desiredCount=1,
                                forceNewDeployment=True)
        self.ecs.update_service(cluster=self.name,
                                service=self.worker,
                                desiredCount=self.num_workers,
                                forceNewDeployment=True)

    @property
    def ecs(self):
        return boto3.client('ecs')

    @property
    def services(self):
        return [self.scheduler, self.worker, self.web]

    @property
    def __worker(self):
        return jmespath.search(f"[?serviceName=='{self.worker}']|[0]",
                               self.__get_config())

    def __get_config(self):
        if not hasattr(self, '__config'):
            services = self.ecs.describe_services(cluster=self.name,
                                                  services=self.services)
            if len(services['services']) != 3:
                raise Exception('Some services are missing')
            self.__config = services['services']
        return self.__config
