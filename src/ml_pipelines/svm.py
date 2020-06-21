"""
author: Philipp Marcus
email: marcus@cip.ifi.lmu.de

A Linear Support Vector Machine-based pipeline for the Sparkify project
that expects the feature extraction to already be applied before.
"""

from pyspark.ml.feature import VectorAssembler, MaxAbsScaler
from pyspark.ml.classification import LinearSVC
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import MulticlassClassificationEvaluator

def build_svm_pipeline(inputCols):
    """
    Builds a Spark ML pipeline based on the given feature names in
    the given DataFrame. Result is a `CrossValidator` that needs to
    be fitted with `.fit(df)` to the training/validation set.

    INPUT:
        - inputCols (list [string]): list of string names of the feature columns of `df` that shall be considered.
    OUTPUT:
        - result (CrossValidator): A Spark ML `CrossValidator`. 
    """

    # VectorAssembler
    vecAssembler = VectorAssembler(inputCols=inputCols,
                                   outputCol="features")

    # Normalizer / Scaler
    maScaler = MaxAbsScaler(inputCol="features",
                            outputCol="features_scaled")

    # Create the model
    svm = LinearSVC(featuresCol='features_scaled',
                    labelCol='churn', 
                    predictionCol='prediction')

    # Define a pipeline
    pipe = Pipeline(stages=[vecAssembler,
                            maScaler,
                            svm])

    grid = ParamGridBuilder().addGrid(svm.regParam, [0]).build()

    # Use cross-validation
    cv = CrossValidator(estimator=pipe,
                        evaluator=MulticlassClassificationEvaluator(labelCol='churn',
                                                                    metricName='f1'),
                        estimatorParamMaps=grid,
                        numFolds=3,
                        parallelism=4)

    return cv