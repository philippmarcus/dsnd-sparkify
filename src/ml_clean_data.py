"""
author: Philipp Marcus
email: marcus@cip.ifi.lmu.de

Data cleaning pipeline based on PySpark for the Sparkify project.
"""

import sys
from pyspark.sql import SparkSession
import optparse, sys
import logging

def load_data(spark, input_file="mini_sparkify_event_data.json"):
    # load the data in spark
    logging.info("Downloading file {}".format(input_file))
    df_s = spark.read.json(input_file)
    logging.info("Completed download of file {}".format(input_file))
    # create a temp view
    df_s.createOrReplaceTempView("df_table")
    return df_s

def clean_userAgent_col(spark):
    """
    The `userAgent` column contains a lot details that are most
    likely not relevant. However, the device type / OS type could
    be relevant, thus we extract it.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    Output:
        - features_df (DataFrame): Result DataFrame with an adde `userSystem` column and `userAgent` column dropped
    """
    # Extract the user system from column `userAgent`
    df_table = spark.sql('''
                        SELECT *, regexp_extract(userAgent,
                                                \"\\\(([a-zA-Z 0-9.]+)\", 1)
                                                as userSystem
                        FROM df_table
                        ''')
    df_table.createOrReplaceTempView("df_table")

    # drop the userAgent column
    df_table = df_table.drop('userAgent')

    return df_table

def rm_empty_userId(spark):
    """
    The `userId` column contains entries with ''. Those are users that
    are logged out and/or anonymous. As we want to make statements for specific
    users based on their behavior, anonymous users are dropped.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    Output:
        - features_df (DataFrame): Result DataFrame where all rows with userId='' are dropped
    """
    # Only leave such roles where userId is not empty
    df_table = spark.sql("""
                        SELECT *
                        FROM df_table
                        WHERE userId <> ''
                        """)
    # Replace the temp view
    df_table.createOrReplaceTempView("df_table")    
    return df_table


def drop_ignored_columns(spark):
    """
    Remove all columns but the following: userId, page, level, sessionId, ts, gender, itemInSession, userSystem, length, auth
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    Output:
        - features_df (DataFrame): Result DataFrame where all columns except the listed ones are removed
    """
    
    df_s = spark.sql('''
                 SELECT userId, page, level, sessionId, ts, gender, itemInSession, userSystem, length, auth
                 FROM df_table
                 ''')
    df_s.createOrReplaceTempView("df_table")
    return df_s

def add_churn_column(spark):
    """
    Define a column `churn` that is 0 before a `Cancellation Confirmation` and 1 afterwards.
    Calculation logic:
    - binary encoding of the events
    - cumulative sum over the binary encoding
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    Output:
        - features_df (DataFrame): Result DataFrame where all columns except the listed ones are removed
    """  
    # binary encoding of the 'Cancellation Confirmation' events in column churn
    df_s = spark.sql('''
                    SELECT *, CASE WHEN page = 'Cancellation Confirmation' THEN 1 ELSE 0 END as cancel_event
                    FROM df_table
                    ''')
    df_s.createOrReplaceTempView('df_table')

    # cumulative sum over the churn column to detect phases
    df_s = spark.sql('''
                    SELECT *,
                    SUM(cancel_event) OVER (PARTITION BY userId) as churn
                    FROM df_table
                    ''')
    df_s.createOrReplaceTempView("df_table")

    # drop the temp column
    df_s = df_s.drop('cancel_event')
    return df_s

def execute_pipeline(input_file, output_file):
    spark = SparkSession \
                        .builder \
                        .appName("Sparkify") \
                        .getOrCreate()
    
    # Load the data
    load_data(spark, input_file)

    # Clean column 
    clean_userAgent_col(spark)

    # Drop empty userId rows
    rm_empty_userId(spark)

    # Drop all but important columns
    drop_ignored_columns(spark)

    # Add a churn column
    df = add_churn_column(spark)

    # save the dataframe
    df.write.parquet(output_file)

if __name__ == "__main__":
    p = optparse.OptionParser()
    p = optparse.OptionParser()
    p.add_option('--input_file', '-i', default="s3://udacity-dsnd/sparkify/mini_sparkify_event_data.json")
    p.add_option('--output_file', '-o', default="s3://sparkify-pmarcus/sparkify_cleaned.parquet/")
    options, arguments = p.parse_args()

    print("Starting spark job...")
    sys.exit(execute_pipeline(input_file = options.input_file, output_file = options.output_file))