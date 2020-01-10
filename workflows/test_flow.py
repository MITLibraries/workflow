from datetime import datetime

from airflow import DAG
from airflow.operators.python_operator import PythonOperator


dag = DAG('test_dag', description='Print the date',
          start_date=datetime(2020, 1, 1))


op = PythonOperator(task_id='print_date', dag=dag,
        python_callable=lambda: print(f'Current time: {datetime.utcnow()}'))
