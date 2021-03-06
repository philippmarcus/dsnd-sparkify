"""
author: Philipp Marcus
email: marcus@cip.ifi.lmu.de

Feature Extraction pipeline based on PySpark for the Sparkify project.
"""
import sys
from pyspark.sql.functions import udf, when
from pyspark.sql.types import FloatType, IntegerType
from pyspark.sql import SparkSession
from pyspark.ml.feature import OneHotEncoder, StringIndexer
import datetime
import optparse

def initiate_df(spark, input_file, new_temp_view='features_df'):
    """
    Produces a Spark RDD that contains one row per userId incl.
    its churn status. Further columns for features are added by
    the other steps of the feature extraction process.

    Prerequisite: a temp view named features_df is available.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    # Read in from parquet - temp view is also needed in later pipeline steps
    df = spark.read.parquet(input_file)
    df.createOrReplaceTempView('df_table')

    # DataFrame for extracted features - to be filled up below
    features_df = spark.sql('''
                            SELECT userId, MAX(churn) as churn
                            FROM df_table
                            GROUP BY userId
                            ''')
    features_df.createOrReplaceTempView(new_temp_view)
    return features_df

def define_udfs(spark):
    """
    Definition of all udfs used on the pipeline.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    # Extract days from timedelta
    to_days = udf(lambda x: datetime.timedelta(milliseconds=x).days, IntegerType())
    spark.udf.register("to_days", to_days)

    # Extract minutes from timedelta
    to_minutes = udf(lambda x: int(datetime.timedelta(milliseconds=x).seconds/60.), IntegerType())
    spark.udf.register("to_minutes", to_minutes)

    # Extract hour of the day from timestamp in ms
    to_hour = udf(lambda x: float(datetime.datetime.fromtimestamp(x / 1000.0).hour), FloatType())
    spark.udf.register("to_hour", to_hour)

    # Extract month of the year from timestamp in ms
    to_month = udf(lambda x: float(datetime.datetime.fromtimestamp(x / 1000.0).month), FloatType())
    spark.udf.register("to_month", to_month)


def add_features(spark, sub_query, feature_names, new_temp_view='features_df'):
    """
    Used to add new features columns to table 'features_df'. This
    is achieved by injecting the passed sql-subquery and joining
    the results on userId with the existing featues_df table.
    
    INPUT:
        - sub_query (string): SQL query that should contain one row of additional features for each userId.
        - new_temp_view (string): Name of the new createOrReplaceTempView resulting from the joining 
    OUTPUT:
        result (DataFrame): Spark DataFrame with the resulting table.
    """
    
    feature_names_sql = "new." + ', new.'.join(feature_names)
    tmp = spark.sql("""
                    SELECT f.*, {feature_names_sql}
                    FROM features_df as f
                    JOIN ({sub_query}) as new
                    on new.userId = f.userId
                    """.format(sub_query = sub_query,
                            feature_names_sql=feature_names_sql))   
    tmp.createOrReplaceTempView(new_temp_view)
    return tmp


def add_avg_sess_p_day(spark):
    """
    Add the feature for average sessions per day.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    # Extract the feature
    avg_sess_per_day = """
                    SELECT userId, COUNT(DISTINCT sessionId) / (to_days(MAX(ts) - MIN(ts))+1) as avg_sess_p_day
                    FROM df_table
                    GROUP BY userId
                    """
    features_df = add_features(spark, avg_sess_per_day, ['avg_sess_p_day'])
    return features_df


def add_avg_song_length(spark):
    """
    Adds a column for the average length of a played song.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    avg_length = """
                SELECT userId, avg(length) as avg_length
                FROM df_table
                GROUP BY userId
                """
    features_df = add_features(spark, avg_length, ['avg_length'])
    return features_df


def add_avg_items_p_sess(spark):
    """
    Add a column for the average items per session.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    # Average items per session
    avg_items_p_sess = """
                        SELECT userId, AVG(itemInSession) as avg_items_p_sess
                        FROM df_table
                        GROUP BY userId
                        """
    features_df = add_features(spark, avg_items_p_sess, ['avg_items_p_sess'])
    return features_df


def add_acc_age_days(spark):
    """
    Add a column for the account age in days.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    acc_age = """
            SELECT userId, to_days(MAX(ts) - MIN(ts)) as acc_age
            FROM df_table
            GROUP BY userId
            """
    features_df = add_features(spark, acc_age, ['acc_age'])
    return features_df


def add_avg_sess_length_min(spark):
    """
    Average session length in minutes
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    # Create a helper table that holds all session lengths for each user in minutes
    tmp_sess_lens = """
            SELECT userId, to_minutes(MAX(ts)-MIN(ts)) as len
            FROM df_table
            GROUP BY userId, sessionId
        """
    tmp_sess_lens = spark.sql(tmp_sess_lens)
    tmp_sess_lens.createOrReplaceTempView("tmp_sess_lens")

    # Compute the average over the session lengths of each user
    avg_sess_len = """
                SELECT userId, AVG(len) as avg_sess_len
                FROM tmp_sess_lens
                GROUP BY userId
                """
    features_df = add_features(spark, avg_sess_len, ['avg_sess_len'])

    # Clean temp views
    spark.catalog.dropTempView("tmp_sess_lens")

    return features_df


def add_gender_dummy_vars(spark):
    """
    Gender of the user - convert to dummy variable with one-hot-encoding.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    # Add the indexed gender to each entry of the df_table
    usr_gender = spark.sql("""SELECT userId, 
                                    CASE WHEN gender = 'F' THEN 1 ELSE 0 END as gender
                                FROM df_table
                            """)
    usr_gender.createOrReplaceTempView("usr_gender")

    # Create user gender pairs
    usr_gender2 = """SELECT userId, MAX(gender) as bin_gender
                    FROM usr_gender
                    GROUP BY userId
                  """
    features_df = add_features(spark, usr_gender2, ['bin_gender'])

    # Clean temp views
    spark.catalog.dropTempView("usr_gender")

    return features_df

def add_pref_user_system(spark):
    """
    For each user, add the mode of its prefered system (iPad, Macos, Windows...)
    as a dummy variable with one-hot-encoding.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    """
    pref_user_system = """
                    SELECT userId, MAX(userSystem) as pref_user_system
                    FROM df_table
                    GROUP BY userId
                    """
    features_df = add_features(spark, pref_user_system, ['pref_user_system'])

    # Fill null values of the operating system, i.e. "unknown"
    features_df = features_df.fillna("unknown", subset=['pref_user_system'])

    # Index the prefered user system (macos, iphone etc...)
    stringIndexer = StringIndexer(inputCol="pref_user_system", 
                                outputCol="pref_user_system_ind",
                                stringOrderType="frequencyDesc")

    features_df = stringIndexer.fit(features_df).transform(features_df)

    # Apply one-hot-encoding for the user system
    ohe = OneHotEncoder(inputCol="pref_user_system_ind",
                        outputCol="pref_user_system_ohe", 
                        dropLast=True)

    ohe_model = ohe.fit(features_df)
    features_df = ohe_model.transform(features_df)
    features_df.createOrReplaceTempView("features_df")

    return features_df


def add_avg_page_clicks_p_sess(spark):
    # Aggregate the count for each page in each session
    pages_per_session = spark.sql("""
                                SELECT userId, sessionId, page, COUNT(page) as cnt, to_month(AVG(ts)) as month
                                FROM df_table
                                GROUP BY userId, sessionId, page
                                """)
    pages_per_session.createOrReplaceTempView("pages_per_session")

    # Average page counts per user per sessions per month
    tmp = spark.sql("""
            SELECT userId, page, month, AVG(cnt) as avg_cnt
            FROM pages_per_session
            GROUP BY userId, month, page
            """)
    tmp.createOrReplaceTempView("tmp")

    # Average page counts per user over all months
    tmp2 = spark.sql("""
            SELECT userId, page, AVG(avg_cnt) as avg_mhly_cnt
            FROM tmp
            GROUP BY userId, page
            """)
    tmp2.createOrReplaceTempView("tmp2")

    # Create a pivot, fill empty values with 0 and drop the column 'Cancellation Confirmation' as this directly correlates with our label
    pages_pivot_df = tmp2.groupBy("userId").pivot("page").sum("avg_mhly_cnt").fillna(0).drop("Cancellation Confirmation")

    # Remove spaces from column names
    for col in pages_pivot_df.columns:
        pages_pivot_df = pages_pivot_df.withColumnRenamed(col, col.replace(" ", "_"))
    pages_pivot_df.createOrReplaceTempView("pages_pivot_df")

    # Get column names for page pivot but leave out the userId
    columns = pages_pivot_df.columns[1:]

    # Finally add the features
    page_pivot = "SELECT * FROM pages_pivot_df"
    features_df = add_features(spark, page_pivot, columns)

    # Clean up
    spark.catalog.dropTempView("tmp")
    spark.catalog.dropTempView("tmp2")
    spark.catalog.dropTempView("pages_pivot_df")

    return features_df

def add_instance_weights(spark, features_df):
    # Extract positive and negative samples
    churn_neg_samples = features_df.filter(features_df.churn == 0)
    churn_pos_samples = features_df.filter(features_df.churn == 1)

    # Compute counts of both sets
    churn_neg_cnt = churn_neg_samples.count()
    churn_pos_cnt = churn_pos_samples.count()

    # Weights of both classes have to sum up to 0.5. Thus count/0.5 is the weight.
    churn_pos_instance_weight = 0.5 / churn_pos_cnt
    churn_neg_instance_weight = 0.5 / churn_neg_cnt

    # Add weights to weightCol for each instance
    features_df = features_df.withColumn("weightCol", \
              when(features_df["churn"] == 0, churn_neg_instance_weight).otherwise(churn_pos_instance_weight))
    
    return features_df
    

def train_test_val_split(spark, features_df):
    """
    The data set is split into two parts, a `train_test` set, that is used for 3-fold cross-validation,
    and a `validation` set. This function should be called after the balancing of churned users
    and all other feature extraction steps are completed.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
        - features_df (DataFrame): Pre-processed data with extracted features
    Output:
        - train_test (DataFrame): DataFrame to be used in Training/Test for a CrossValidator
        - train_test (DataFrame): DataFrame to be used in Validation of a trained ML model
    """
    # Split data for training/test and validation
    train_test, validation = features_df.randomSplit([0.9, 0.1], seed=42)

    return train_test, validation

def feature_extraction_pipe(input_file, output_file_train_test, output_file_validation):
    """
    Final feature extraction pipeline.
    Input:
        - spark (SparkSession): A initiated pyspark.sql.SparkSession
    Output:
        - features_df (DataFrame): Result DataFrame with the created features
    """
    # Initiation
    spark = SparkSession \
                    .builder \
                    .appName("Sparkify") \
                    .getOrCreate()
                    
    initiate_df(spark, input_file)

    define_udfs(spark)

    # Feature extraction
    add_avg_sess_p_day(spark)
    add_avg_song_length(spark)
    add_avg_items_p_sess(spark)
    add_acc_age_days(spark)
    add_avg_sess_length_min(spark)
    add_gender_dummy_vars(spark)
    features_df = add_pref_user_system(spark) # fail
    features_df = add_avg_page_clicks_p_sess(spark)

    # Split to training/test and validation data
    train_test, validation = train_test_val_split(spark, features_df)

    # Add a weight column to compensate imbalanced classes
    train_test = add_instance_weights(spark, train_test)
    validation = add_instance_weights(spark, validation)

    # save the dataframe
    train_test.write.parquet(output_file_train_test)
    validation.write.parquet(output_file_validation)

if __name__ == "__main__":

    p = optparse.OptionParser()
    p.add_option('--input', '-i', default="data/sparkify_cleaned.parquet")
    p.add_option('--traintest', '-t', default="data/sparkify_train_test.parquet")
    p.add_option('--validation', '-v', default="data/sparkify_validation.parquet")
    options, arguments = p.parse_args()
    print(options.validation)

    print("Starting spark job...")
    print(sys.argv)
    args = sys.argv[1].split(",")
    sys.exit(feature_extraction_pipe(input_file = options.input, output_file_train_test = options.traintest, output_file_validation = options.validation))
