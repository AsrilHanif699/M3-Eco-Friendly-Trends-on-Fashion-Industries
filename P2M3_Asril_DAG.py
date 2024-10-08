'''
-----------------------------------------------------------
INTRODUCTION
-----------------------------------------------------------
Nama    : Muhammad Asril Hanif
Batch   : RMT-034

Program ini untuk menjalankan batch perintah mengambil data, Cleaning data, Copy data, dan Push data ke elasticsearch menggunakan Apache Airflow
-----------------------------------------------------------
'''


import datetime as dt
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
import psycopg2 as db  # koneksi python dengan postgresql
from elasticsearch import Elasticsearch, helpers # koneksi python elastic

import pandas as pd
import numpy as np

def cleanData():
    # Koneksi dengan postgreSQL
    # host 'postgres' dan port 5432 karena data ditarik tidak melalui manusia, melainkan melalui airflow
    conn_string="dbname='postgres' host='postgres' user='airflow' password='airflow' port='5432'"
    conn=db.connect(conn_string)

    # Read keseluruhan data kedalam dataframe
    df=pd.read_sql("select * from table_m3", conn)
 
    # Cleaning nama Kolom menjadi lowercase
    df.columns = df.columns.str.lower()

    # Drop Duplikat Data
    df.drop_duplicates()

    # Ubah tipe data kolom sesuai dengan yang seharusnya
    # Tipe data menjadi integer
    df['year'] = df['year'].astype(int)
    df['product_lines'] = df['product_lines'].astype(int)

    # Mengubah value 'Yes' dan 'No' menjadi Boolean
    df['eco_friendly_manufacturing'] = np.where(df['eco_friendly_manufacturing'] == "Yes", True, False)
    df['recycling_programs'] = np.where(df['recycling_programs'] == "Yes", True, False)

    # Handling Missing Value
    # Pada dataset awal terdapat missing value pada kolom 'Certifications' namun value 'None' tersebut merupakan status sertifikasi brand sebuah perusahaan.
    # oleh karena itu, missing value pada kolom ini akan diisi dengan value 'None' bertipe string
    df.loc[df['certifications'].isna(), 'certifications'] = "None"

    # Save clean data to CSV
    df.to_csv('/opt/airflow/dags/p2m3_asril_data_clean.csv', index=False)

    # Tutup koneksi
    conn.close()

def elasticUpload():
    # Koneksi dengan elastic search
    es = Elasticsearch([{"host":"elasticsearch",
                         "port": "9200"}])

    # Read CSV data clean
    df = pd.read_csv('/opt/airflow/dags/p2m3_asril_data_clean.csv')
    
    # Convert data menjadi dictionary
    def convert_data(df):
        for i, r in df.iterrows():
            yield{
                "_index": "table_m3",
                "_id": i,
                "_source": r.to_dict()
            }
    
    # Upload ke Elasticsearch
    helpers.bulk(es, convert_data(df))

default_args = {
    'owner': 'Asril',
    'start_date': dt.datetime(2024, 9, 12) - dt.timedelta(hours=7),
    'retries': 1,
    'retry_delay': dt.timedelta(minutes=1)
}

with DAG('M3CleanData',
         default_args = default_args,
         schedule_interval= '30 6 * * *',
         catchup=False
         ) as dag:
    
    # Mendefinisikan operator
    cleanData = PythonOperator(task_id = 'Fetch_Clean',
                               python_callable = cleanData)
    elasticUpload = PythonOperator(task_id = 'Elastic_Upload',
                                   python_callable = elasticUpload)
    copyFile = BashOperator(task_id='Copy_Clean_Data',
                            bash_command='cp /opt/airflow/dags/p2m3_asril_data_clean.csv /opt/airflow/logs')

# Flow Task yang akan dilakukan
cleanData >> copyFile >> elasticUpload