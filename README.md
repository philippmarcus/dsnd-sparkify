# Sparkify on AWS Elastic Map Reduce (EMR)

This project is the cap-stone project of the Udacity Data Science Nano-degree. It shows a full big data machine learning project written in Apache Spark and executed on an AWS Elastic Map Reduce (EMR) cluster with AWS Stepfunctions.

Sparkify is a fictional music streaming service, comparable to Spotify. Udacity provides a Sparkify user event log that spans 60 full days and contains all events created by each single user, e.g. by logging in, selecting the next song, or liking a song. In this project, a user log of approx. 12 GB is given. The entries contain all events created by single users, e.g. by logging in, selecting the next song, or liking a song. 

Some users within this event log cancelled their subscription. The goal of this project is to predict for a given trace of user evens whether this user is likely to cancel his subscription and consequently stop to use Sparkify.

## Project results

The results can be found in the write-up [here](https://github.com/philippmarcus/dsnd-sparkify/blob/master/writeup.md).

## Usage instructions

The execution of the Jupyter Notebooks requires and AWS EMR cluster incl. JupyterHub. A detailed description for the setup can be found [here](./doc/create-emr-cluster.md). Overview:

1. Launch an AWS EMR Cluster incl. JupyterHub. 
2. Upload the Notebook files to the S3 bucket that was linked to you JupyterHub setup.
3. Set up an SSH tunnel to your AWS EMR master instance and access your JupyterHub instance.

The data is not contained in this repo and needs to be downloaded from the following locations:

- Full Sparkify Dataset (12Gb): <s3n://udacity-dsnd/sparkify/sparkify_event_data.json>
- Mini Sparkify Dataset (123Mb): <s3n://udacity-dsnd/sparkify/mini_sparkify_event_data.json>

## Execution on AWS EMR

The project includes AWS Stepfunctions to automate the shown workflow on an AWS EMR cluster:

- `create-emr-cluster`: Stepfunction to create an AWS EMR cluster. Execution requires an IAM policy with assigned *service-linked role* policy (see [here](https://docs.aws.amazon.com/emr/latest/ManagementGuide/using-service-linked-roles.html)). ***A detailed description can also be found [here](./doc/create-emr-cluster.md)***
- `data-pre-processing`: Stepfunction that loads the full dataset and applies the data cleaning and feature extraction as shown in this notebook.
- `ml-training-validation`: Stepfunction to execute the ML trainings and ML evaluations of as shown in this notebook.
- `terminate-emr-cluster`: Stepfunction to create an AWS EMR cluster. Execution requires an IAM policy with assigned *service-linked role* policy (see [here](https://docs.aws.amazon.com/emr/latest/ManagementGuide/using-service-linked-roles.html)).

***Step 1: Create an S3 bucket***
Create an S3 bucket to store the python code for later execution on the EMR cluster. The bucket should not be public and you can stay with the default settings, as the standard IAM role used for EMR will be able to access all S3 buckets.

***Step 2: Prepare files***
Prerequisites for all Stepfunctions except `create-emr-cluster`: replace all `<Placeholder>` by your respective `s3://...` bucket paths. The Stepfunctions by default refer to the full dataset.

***Step 3: Upload files***
Upload all files of folder `/src/*` to your newly created S3 bucket. Also include the file `/scripts/bootstrap-modules.sh`, which will be called while bootstrapping your EMR cluster to install all required python modules.

***Step 3: Register the Stepfunctions***
Register the Stepfunctions as in folder `/stepfunctions/` of this folder.

***Step 4: Run the Stepfunctions***
Start the execution of the Stepfunctions in this order:
1. `create-emr-cluster`, note down the `ClusterId` in the output
2. `data-pre-processing`, take care to define the correct input, e.g. `{ "ClusterId": "J-1AZ82NTT1MZRG"}`
3. `ml-training-validation`, take care to define the correct input, e.g. `{ "ClusterId": "J-1AZ82NTT1MZRG"}`
4. `terminate-emr-cluster`, take care to define the correct input, e.g. `{ "ClusterId": "J-1AZ82NTT1MZRG"}`

## Files

The project contains the following files:

```
.
├── README.md
├── doc
│   └── create-emr-cluster.md (Guideline to setup EMR and the Stepfunctions)
├── model (Trained Spark ML models on the full data set)
│   ├── lr (Logistic Regression)
│   ├── nb (Naive Bayes)
│   ├── rf (Random Forest)
│   └── svm (Support Vector Machine)
├── notebooks
│   ├── Sparkify-Evaluation.html
│   ├── Sparkify-Evaluation.ipynb (Notebook 2/2 for ML results evaluation)
│   ├── Sparkify-Exploration.html 
│   └── Sparkify-Exploration.ipynb (Notebook 1/2 for data exploration)
├── scripts (Scripts used by the AWS Stepfunction templates)
│   ├── bootstrap-modules.sh (Required python packages on the EMR cluster - executed by )
│   ├── createjupyterusers.sh (Create custom users for JupyterHub)
├── src (ML pipeline launched by AWS Stepfunctions)
│   ├── ml_clean_data.py
│   ├── ml_evaluator.py
│   ├── ml_features.py
│   └── ml_pipe_factory.py
├── start-pyspark.sh (Script to start a local PySpark cluser with Docker)
└── templates (Templates for AWS Stepfunctions)
    ├── create-emr-cluster.json (Create the AWS EMR cluster and configure JupyterHub)
    ├── data-pre-processing.json (Carry out data cleaning and feature extraction)
    ├── ml-training-validation.json (Carry out ML training and evaluation)
```

## Requirements

The requirements have to be installed based on `scripts/bootstrap-modules.py`.

## Acknowledgements

Thanks to Udacity for providing the data set and project idea.