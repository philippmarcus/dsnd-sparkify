import math

import luigi
import luigi.contrib.spark
from pyspark.sql import SparkSession
from pyspark import  SQLContext

import logging
from pyspark import SparkContext
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.feature import Bucketizer, Imputer, StringIndexer, VectorAssembler

"""
1. Clean Data

2. Add Churn

3. Extract Features

4. Train Model

5. Evaluate Model


The target checks whether the output file is there.
If not it is executed again.

"""
import luigi
from luigi.contrib.s3 import S3Target
from pyspark import SparkConf, SparkContext

s3_target = 's3://udacity-dsnd/sparkify/mini_sparkify_event_data.json'
local_folder = './data/'

# Check if the file exists in the S3 bucket
class FileExists(luigi.Task):
    def output(self):
        return S3Target(str(s3_target))
    def run(self):
        self.output().open('w').close()

# Download the file from the S3 bucket to local
class JsonDownloader(luigi.Task):

    def requires(self):
        yield FileExists()

    def output(self):
        return luigi.LocalTarget(local_folder + 'mini_sparkify_event_data.json')

    def run(self):
        luigi.contrib.s3.S3Client().get(self.input()[0].path, self.output().path)

class DataCleaner(luigi.contrib.spark.SparkSubmitTask):

    app = 'ml_clean_data.py'
    master = 'local[*]'

    def output(self):
        return luigi.LocalTarget(local_folder + 'sparkify_cleaned.parquet')

    def requires(self):
        return JsonDownloader()

    def app_options(self):
        return [self.input().path, self.output().path]

class FeatureExtractor(luigi.contrib.spark.SparkSubmitTask):
    app = 'ml_features.py'
    master = 'local[*]'

    def output(self):
        return {'train_test':luigi.LocalTarget(local_folder + 'df_features_train_test.parquet'),
                'validation':luigi.LocalTarget(local_folder + 'df_features_validation.parquet')}

    def requires(self):
        return DataCleaner()

    def app_options(self):
        return [self.input().path, self.output()['train_test'].path, self.output()['validation'].path]

if __name__ == "__main__":
    """
    luigi.build(
        [

            FileExists(input_file='s3://udacity-dsnd/sparkify/mini_sparkify_event_data.json'),
            CleanData(input_file='s3n://udacity-dsnd/sparkify/mini_sparkify_event_data.json', 
                      output_file='./data/sparkify_cleaned.parquet')
        ],
        local_scheduler=True,
        detailed_summary=False,
    )
    """
    
    luigi.build(
        [
            FileExists(),
            JsonDownloader(),
            DataCleaner(),
            FeatureExtractor()
            
        ],
        local_scheduler=True,
        detailed_summary=False,
    )
    
    # Use local scheduler for development purposes.
    # ALTERNATIVE:
    #luigi.run()

  