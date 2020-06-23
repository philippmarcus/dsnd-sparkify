"""
author: Philipp Marcus
email: marcus@cip.ifi.lmu.de

A Naive Bayes-based pipeline for the Sparkify project
that expects the feature extraction to already be applied before.
"""

from pyspark.ml.feature import VectorAssembler, MaxAbsScaler
from pyspark.ml.classification import NaiveBayes, LinearSVC, RandomForestClassifier, LogisticRegression
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import MulticlassClassificationEvaluator

# Helper function to build pipelines
def ml_pipeline_factory(inputCols, classifier, param_gird=None):
    """
    Helper function to build a Spark ML pipeline based on a given classifier for
    the given feature names in the given DataFrame. Result is a `CrossValidator`
    that needs to be fitted with `.fit(df)` to the training/validation set.

    INPUT:
        - inputCols (list [string]): list of string names of the feature columns of `df` that shall be considered.
        - classifier: a classifier instance from pyspark.ml.classification
        - param_grid: a ParamGrid that was built for the passed classifier based on pyspark.ml.ParamGridBuilder
    OUTPUT:
        - result (CrossValidator): A Spark ML `CrossValidator`. 
    """

    # VectorAssembler
    vecAssembler = VectorAssembler(inputCols=inputCols,
                                   outputCol="features")


    # Normalizer / Scaler
    maScaler = MaxAbsScaler(inputCol="features",
                            outputCol="features_scaled")


    # Define a pipeline
    pipe = Pipeline(stages=[vecAssembler,
                            maScaler,
                            classifier])

    # Use cross-validation
    cv = CrossValidator(estimator=pipe,
                        evaluator=MulticlassClassificationEvaluator(labelCol='churn',
                                                                    metricName='f1'),
                        estimatorParamMaps=param_gird,
                        numFolds=3,
                        parallelism=4)

    return cv


# Build a Support Vector Machine Pipeline
def build_svm_pipeline(inputCols):
    """
    Builds a Support Vector Machine-based Spark ML pipeline for the given
    feature names in the given DataFrame. Result is a `CrossValidator` that
    needs to be fitted with `.fit(df)` to the training/validation set.

    INPUT:
        - inputCols (list [string]): list of string names of the feature columns of `df` that shall be considered.
    OUTPUT:
        - result (CrossValidator): A Spark ML `CrossValidator`. 
    """

    # Create the model
    svm = LinearSVC(featuresCol='features_scaled',
                    labelCol='churn', 
                    predictionCol='prediction')

    # Define a parameter grid for optimization
    grid = ParamGridBuilder().addGrid(svm.regParam, [0]).build()

    # Build the pipeline
    pipe = ml_pipeline_factory(inputCols, svm, grid)
    return pipe


# Build a Naive Bayes Pipeline
def build_naivebayes_pipeline(inputCols):
    """
    Builds a Naive Bayes-based Spark ML pipeline for the given
    feature names in the given DataFrame. Result is a `CrossValidator` that
    needs to be fitted with `.fit(df)` to the training/validation set.

    INPUT:
        - inputCols (list [string]): list of string names of the feature columns of `df` that shall be considered.
    OUTPUT:
        - result (CrossValidator): A Spark ML `CrossValidator`. 
    """

    # Create the model
    nb = NaiveBayes(featuresCol='features_scaled',
                    labelCol='churn', 
                    predictionCol='prediction')

    # Param grid for model optimization
    grid = ParamGridBuilder().addGrid(nb.modelType, ["gaussian",
                                                     "multinomial"]).build()

    # Build the pipeline
    pipe = ml_pipeline_factory(inputCols, svm, grid)
    return pipe


# Build a Logistic Regression Pipeline
def build_logreg_pipeline(inputCols):
    """
    Builds a Logistic Regression-based Spark ML pipeline for the given
    feature names in the given DataFrame. Result is a `CrossValidator` that
    needs to be fitted with `.fit(df)` to the training/validation set.

    INPUT:
        - inputCols (list [string]): list of string names of the feature columns of `df` that shall be considered.
    OUTPUT:
        - result (CrossValidator): A Spark ML `CrossValidator`. 
    """

    # Create the model
    lr = LogisticRegression(featuresCol='features_scaled',
                            labelCol='churn', 
                            predictionCol='prediction')

    # Param grid for model optimization
    grid = ParamGridBuilder().addGrid(lr.elasticNetParam, [.0, 1.]) \
                             .addGrid(lr.threshold, [.3, 0.5, 0.7]).build()

    # Build the pipeline
    pipe = ml_pipeline_factory(inputCols, lr, grid)
    return pipe


# Build a Random Forest Pipeline
def build_randomforest_pipeline(inputCols):
    """
    Builds a Random Forest-based Spark ML pipeline for the given
    feature names in the given DataFrame. Result is a `CrossValidator` that
    needs to be fitted with `.fit(df)` to the training/validation set.

    INPUT:
        - inputCols (list [string]): list of string names of the feature columns of `df` that shall be considered.
    OUTPUT:
        - result (CrossValidator): A Spark ML `CrossValidator`. 
    """

    # Create the model
    rf = RandomForestClassifier(featuresCol='features_scaled',
                            labelCol='churn', 
                            predictionCol='prediction')

    # Param grid for model optimization
    grid = ParamGridBuilder().addGrid(rf.impurity, ["entropy", "gini"]).build()

    # Build the pipeline
    pipe = ml_pipeline_factory(inputCols, rf, grid)
    return pipe