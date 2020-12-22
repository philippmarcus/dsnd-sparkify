"""
author: Philipp Marcus
email: marcus@cip.ifi.lmu.de

Machine Learning pipelines based on PySpark for the Sparkify project
that expects the feature extraction to already be applied before.

Command line version.
"""

# Import various candidate models
from ml_pipe_factory import build_svm_pipeline, build_naivebayes_pipeline, build_randomforest_pipeline, build_logreg_pipeline
from pyspark.sql import SparkSession
import pathlib, sys
import optparse

