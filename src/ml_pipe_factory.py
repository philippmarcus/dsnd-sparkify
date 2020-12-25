"""
author: Philipp Marcus
email: marcus@cip.ifi.lmu.de

Machine Learning pipelines based on PySpark for the Sparkify project
that expects the feature extraction to already be applied before.
"""

from pyspark.ml.feature import VectorAssembler, MaxAbsScaler, StringIndexer
from pyspark.ml.classification import NaiveBayes, LinearSVC, RandomForestClassifier, LogisticRegression
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
import optparse, sys

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
                                   outputCol="features",
                                   handleInvalid='skip')


    # Normalizer / Scaler
    """
    TODO Apply Standardization instead of scaling to account for outliers
    """
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
                    weightCol='weightCol',
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
                    weightCol='weightCol',
                    predictionCol='prediction')

    # Param grid for model optimization
    grid = ParamGridBuilder().addGrid(nb.modelType, ["multinomial"]).build()

    # Build the pipeline
    pipe = ml_pipeline_factory(inputCols, nb, grid)
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
                            weightCol='weightCol',
                            predictionCol='prediction')

    # Param grid for model optimization
    grid = ParamGridBuilder().build()
    # .addGrid(lr.threshold, [.3, 0.5, 0.7])
    # .addGrid(lr.elasticNetParam, [.0, 1.])\

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
                                weightCol='weightCol', 
                                predictionCol='prediction')

    # Param grid for model optimization
    grid = ParamGridBuilder().addGrid(rf.impurity, ["gini"]).build()

    # Build the pipeline
    pipe = ml_pipeline_factory(inputCols, rf, grid)
    return pipe


def ml_training(algo, input_data, input_model, output_model):

    # Initiation
    spark = SparkSession \
                    .builder \
                    .config('spark.jars.packages', 'org.apache.hadoop:hadoop-aws:2.7.1,com.github.fommil.netlib:all:1.1.2') \
                    .appName("Sparkify") \
                    .getOrCreate()

    # Read in the data 
    train_test_data = spark.read.parquet(input_data)

    # Define the features to be used in training
    feature_cols = ['avg_sess_p_day',
                    'avg_length',
                    'avg_items_p_sess',
                    'acc_age',
                    'avg_sess_len',
                    'bin_gender',
                    'pref_user_system_ohe',
                    'About',
                    'Add_Friend',
                    'Add_to_Playlist',
                    'Downgrade',
                    'Error',
                    'Help',
                    'Home',
                    'Logout',
                    'NextSong',
                    'Roll_Advert',
                    'Save_Settings',
                    'Settings',
                    'Submit_Downgrade',
                    'Submit_Upgrade',
                    'Thumbs_Down',
                    'Thumbs_Up',
                    'Upgrade']

    # Train the model
    if algo == 'svm': # Support Vector Machine
        pipeline = build_svm_pipeline(inputCols = feature_cols)
    elif algo == 'nb': # Naive Bayes
        pipeline = build_naivebayes_pipeline(inputCols = feature_cols)
    elif algo == 'rf': # Random Forest
        pipeline = build_randomforest_pipeline(inputCols = feature_cols)
    elif algo == 'lr': # Logistic Regression
        pipeline = build_logreg_pipeline(inputCols = feature_cols)
    else:
        raise Exception("Unknown ML algorithm {} requested.".format(algo))

    # Execute the training
    model = pipeline.fit(train_test_data)

    # Save the model
    model.bestModel.write().overwrite().save(output_model)

    return


if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option('--algo', '-a', default="all")
    p.add_option('--input_data', '-i', default="data/sparkify_train_test.parquet")
    p.add_option('--input_model', '-m', default=None)
    p.add_option('--output_model', '-o', default="data/models/svm")
    options, arguments = p.parse_args()

    print("Starting spark machine learning training job...")

    # Train the model  
    sys.exit(ml_training(algo=options.algo,
                        input_data=options.input_data,
                        input_model=options.input_model,
                        output_model=options.output_model))