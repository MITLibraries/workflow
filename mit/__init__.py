from airflow.plugins_manager import AirflowPlugin

from mit.operators import ECSOperator
from mit.sensors import ECSTaskSensor


class MitPlugin(AirflowPlugin):
    name = 'mit'
    operators = [ECSOperator]
    sensors = [ECSTaskSensor]
