"""
author: Philipp Marcus
email: marcus@cip.ifi.lmu.de

Calculates various metrics for a trained CrossValidatorModel and returns
them as dict.
"""
from pyspark.ml import PipelineModel
from pyspark.sql import SparkSession
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
import optparse, sys
import json
import boto3
from urllib.parse import urlparse

def evaluate_model(data_set, model_path = None, label_col='churn'):
    """
    Evaluates the f1, accuracy, precision and recall score on a given
    data set, assuming the columns 'churn' as label and 'prediction' for
    the value generated by the classificator.
    
    INPUT:
        `data_set` (DataFrame): Spark DataFrame that was processed by then `.transform(...)` method of the cv already.
        `model_name` (string): Name of the ML algorithm that was used to generate the results. Used in the ouput data.
        `label_col` (string): Name of the column in `data_set` that contains the labels.
    OUTPUT:
        - result (dict): keys are accuracy, recall, precision, f1. Values are provided as float.
    """

    # Extract the evaluator
    evaluator = MulticlassClassificationEvaluator(labelCol=label_col,predictionCol='prediction',weightCol='weightCol')

    # Calculate the metrics
    recall = evaluator.evaluate(data_set, {evaluator.metricName: "weightedRecall"})
    precision = evaluator.evaluate(data_set, {evaluator.metricName: "weightedPrecision"})
    accuracy = evaluator.evaluate(data_set, {evaluator.metricName: "accuracy"})
    f1 = evaluator.evaluate(data_set, {evaluator.metricName: "f1"})
    
    # Create a dict and return
    return {'model_path': model_path,
            'recall': recall,
            'precision': precision,
            'accuracy': accuracy,
            'f1': f1 }

def evaluation_pipeline(input_data, model_path):

    # Initiation
    spark = SparkSession \
                    .builder \
                    .config('spark.jars.packages', 'org.apache.hadoop:hadoop-aws:2.7.1,com.github.fommil.netlib:all:1.1.2') \
                    .appName("Sparkify") \
                    .getOrCreate()

    # Load the validation data set
    validation_data = spark.read.parquet(input_data)

    # Load ML model
    ml_model = PipelineModel.load(model_path)

    # Transform the validation data set
    model_results = ml_model.transform(validation_data)

    # Evaluate the transformation results
    results = evaluate_model(model_results, model_path = model_path)

    # Write out results
    s3 = boto3.resource('s3')
    bucket_url = urlparse(model_path, allow_fragments=False)
    s3object = s3.Object(bucket_url.netloc, bucket_url.path[1:] + 'evaluation_results.json')

    s3object.put(
        Body=(bytes(json.dumps(results).encode('UTF-8')))
    )
    return

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option('--input_path', '-i', default="data/sparkify_train_test.parquet")
    p.add_option('--model_path', '-m', default=None)
    options, arguments = p.parse_args()

    print("Starting spark machine learning training job...")

    # Train the model
    sys.exit(evaluation_pipeline(input_data=options.input_path,
                                    model_path=options.model_path))