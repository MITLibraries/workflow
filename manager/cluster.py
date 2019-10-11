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
    def __init__(self, cluster, scheduler, worker, web, client):
        self.name = cluster
        self.scheduler = scheduler
        self.worker = worker
        self.web = web
        self.ecs = client

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

    def stop(self, services=None):
        if services is None:
            services = self.services
        for service in services:
            self.ecs.update_service(cluster=self.name,
                                    service=service,
                                    desiredCount=0)

    def start(self, services=None):
        if services is None:
            services = self.services
        for service in services:
            self.ecs.update_service(cluster=self.name,
                                    service=service,
                                    desiredCount=1,
                                    forceNewDeployment=True)

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
