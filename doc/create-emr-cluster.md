# Create a Spark Cluster on AWS EMR and run Jupyter Notebooks

Apache Spark has become an indispensable tool for data science projects with large data sets. Typically, Spark is operated in larger clusters so that processing can be carried out in a distributed manner. For this purpose, Jupyter notebooks are preferably used for the initial data exploration and for evaluations.

This tutorial describes how an Apache Spark Cluster including JupyterHub can be set up on AWS Elastic Map Reduce (EMR) using AWS Stepfunctions. The tutorial looks at the following aspects:

- Installation of required python packages as bootstrap action
- Configuration of users for JupyterHub and permanent storage of notebooks in their own S3 bucket
- Setting up an IAM role for the execution of the step function
- Connect to JupyterHub via SSH tunnel

As an alternative to the approach described here using AWS Stepfunctions, a cloud formation template can also be defined. Since in data science workflows calculations are often to start automatically at certain events or times (without Jupyter Notebook), AWS step functions are used here, which can be called via AWS Eventbridge. Larger data science workflows with additional steps can also be defined from the modules shown here, e.g. for data cleansing and the automatic training of machine learning models.


## Preparation of bootstrapping scripts

Before we can define and create the AWS Stepfunction, the scripts must be created and uploaded that are to be executed automatically when the cluster is booted

### Step 1: The AWS EMR Bootstrap Script for Python

When the cluster starts up, the required python packages should be installed automatically on all nodes. This process is called bootstrapping. Technically, a shell script is executed on all nodes of the cluster:

```sh
#!/bin/sh

# Install needed python packages
sudo pip3 install seaborn matplotlib numpy pandas pathlib boto3
```

Steps:

- Save the script in the file `bootstrap-modules.sh`

The python packages shown here can of course be adapted according to your own requirements.

### Step 2: The AWS EMR Bootstrap Script for JupyterHub

We will install JupyterHub on the AWS EMR cluster and for security reasons we would like to create our own PAM user accounts including home directories in S3. As a first step we have to create a shell script that the user will create in the JupyterHub Docker container [2]:

```sh
# Bulk add users to container and JupyterHub with temp password of username
set -x
# add all users seperated with spaces here
USERS=(philipp admin)
TOKEN=$(sudo docker exec jupyterhub /opt/conda/bin/jupyterhub token jovyan | tail -1)
for i in "${USERS[@]}"; 
do 
   sudo docker exec jupyterhub useradd -m -s /bin/bash -N $i
   sudo docker exec jupyterhub bash -c "echo $i:$i | chpasswd"
   curl -XPOST --silent -k https://$(hostname):9443/hub/api/users/$i \
 -H "Authorization: token $TOKEN"
done
```

Steps:

- Replace the names in the array `USERS = (philipp admin)` with the required user names.
- Save the script in the file `create-jupyter-users.sh`.

### Step 3: Upload to S3

So that the AWS EMR cluster can execute the bootstrap script, it must be stored in an S3 bucket. Steps:

- Create an S3 bucket in the region of your choice. You can stay with the standard configuration, i.e. no public access and no own bucket policy. The background is that the default IAM role used by AWS EMR has full access to S3. Of course, this can still be customized to improve the security footprint.
- Upload the script `bootstrap-modules.sh` to the bucket.
- Upload the script `create-jupyter-notebook.sh` to the bucket.

## The AWS Stepfunction Script

AWS Stepfunction are developed in the specially developed language AWS Stepfunction Language (ASL) [?] and are defined in json format. In this tutorial, a simple workflow consisting of two tasks is defined:

- Define an IAM role to execute the step function
- Setup EMR cluster
- Configure JupyterHub Users

### Step 1: Create a EC2 Key Pair

So that we are later able to establish SSH connections and an SSH tunnel with the EC2 instances of the EMR cluster, we must first create a key pair. Steps:

- Go to `EC2` in the AWS Console
- In the menu on the left, find the `Key Pairs` area and click on it
- Create a new key pair, save the `.pem` file locally and note the name

### Step 2: Create IAM role for Stepfunction execution

Steps:

- Go to IAM > Policies in the AWS Console and create a new policy with the following content:


		{
		    "Version": "2012-10-17",
		    "Statement": [
		        {
		            "Effect": "Allow",
		            "Action": [
		                "elasticmapreduce:RunJobFlow",
		                "elasticmapreduce:DescribeCluster",
		                "elasticmapreduce:TerminateJobFlows"
		            ],
		            "Resource": "*"
		        },
		        {
		            "Effect": "Allow",
		            "Action": "iam:PassRole",
		            "Resource": [
		                "arn:aws:iam::<YOUR ACCOUNT ID HERE>:role/EMR_DefaultRole",
		                "arn:aws:iam::<YOUR ACCOUNT ID HERE>:role/EMR_EC2_DefaultRole"
		            ]
		        },
		        {
		            "Effect": "Allow",
		            "Action": [
		                "events:PutTargets",
		                "events:PutRule",
		                "events:DescribeRule"
		            ],
		            "Resource": [
		                "arn:aws:events:<YOUR REGION HERE>:<YOUR ACCOUNT ID HERE>:rule/StepFunctionsGetEventForEMRRunJobFlowRule"
		            ]
		        }
		    ]
		}

- Create a new IAM role to execute the step function. The Trust Poliy is:


        {
            "Version": "2012-10-17",
            "Statement": [
                {
                "Effect": "Allow",
                "Principal": {
                    "Service": "states.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
                }
            ]
        }

- The policy shown above should be added under Permissions
- Press save


If you also want to use the workflow to stop the EMR, special IAM permissions are required [3].


### Step 3: Create the State machine

In the first step the EMR cluster is initiated, all packages are bootstrapped and JupyterHub is configured for permanent storage of notebooks. The basis for the step function to be created is `RunFlowJob` API [1]. The following script does the job. The positions with `<REPLACE WITH YOUR S3 BUCKET>` must be replaced by the name of the previously created S3 bucket:


    {
	    "Comment": "An example of the Amazon States Language for running jobs on Amazon EMR and returns then ClusterId as result.",
	    "StartAt": "Create EMR cluster",
	    "States": {
	        "Create EMR cluster": {
	        "Type": "Task",
	        "Resource": "arn:aws:states:::elasticmapreduce:createCluster.sync",
	        "Parameters": {
	            "Name": "SparkifyCluster",
	            "VisibleToAllUsers": true,
	            "ReleaseLabel": "emr-6.2.0",
	            "Applications": [
	            { "Name": "Spark" },
	            { "Name": "Hadoop" },
	            { "Name": "Livy" },
	            { "Name": "Hive" },
	            { "Name": "JupyterHub" }
	            ],
	            "BootstrapActions": [
	            { 
	                "Name": "PythonLibraries",
	                "ScriptBootstrapAction": { 
	                    "Path": "s3://<REPLACE WITH YOUR S3 BUCKET>/bootstrap-modules.sh"
	                }
	            }
	            ],
	            "Configurations": [
	            {
	                "Classification": "jupyter-s3-conf",
	                "Properties": {
	                    "s3.persistence.enabled": "true",
	                    "s3.persistence.bucket": "<REPLACE WITH YOUR S3 BUCKET>"
	                }
	            }
	        ],
	            "ServiceRole": "EMR_DefaultRole",
	            "JobFlowRole": "EMR_EC2_DefaultRole",
	            "LogUri": "s3://<REPLACE WITH YOUR S3 BUCKET>/logs/",
	            "Instances": {
	            "Ec2KeyName" : "<YOUR KEYPAIR HERE>",
	            "KeepJobFlowAliveWhenNoSteps": true,
	            "InstanceFleets": [
	                {
	                "Name": "MyMasterFleet",
	                "InstanceFleetType": "MASTER",
	                "TargetOnDemandCapacity": 1,
	                "InstanceTypeConfigs": [
	                    {
	                    "InstanceType": "m5.xlarge"
	                    }
	                ]
	                },
	                {
	                "Name": "MyCoreFleet",
	                "InstanceFleetType": "CORE",
	                "TargetOnDemandCapacity": 2,
	                "InstanceTypeConfigs": [
	                    {
	                    "InstanceType": "m5.xlarge"
	                    }
	                ]
	                }
	            ]
	            }
	        },
	        "ResultSelector": {
	            "ClusterId.$": "$.ClusterId"
	        },
	        
	        "Next": "Create JupyterHub Users"
	        },
	        "Create JupyterHub Users": {
	        "Type": "Task",
	        "Resource": "arn:aws:states:::elasticmapreduce:addStep.sync",
	        "Parameters": {
	            "ClusterId.$": "$.ClusterId",
	            "Step": {
	                "Name": "Custom JAR",
	                "ActionOnFailure": "CONTINUE",
	                "HadoopJarStep": {
	                    "Jar": "s3://<REPLACE WITH YOUR S3 BUCKET>.elasticmapreduce/libs/script-runner/script-runner.jar",
	                    "Args": [
	                        "s3://<REPLACE WITH YOUR S3 BUCKET>/createjupyterusers.sh"
	                    ]
	                }
	            }
	        },
	        "ResultPath": "$.ClusterId",
	        "End": true
	    	}
    	}
    }


Steps:

- Open `Stepfunctions` in the AWS console and go to the submenu` State machines`
- Click on `Create state machine` and use the options` Author with code snippets` and Type `Standard`
- Copy the above JSON code into the text field and replace the name of the S3 bucket accordingly
- Click `Next`. Define the name e.g. as `create-emr-cluster`.
- The permissions can be left on `Create new role`
- Click on `Create state machine`

### Step 4: Execute the State machine

The state machine can now be started, which ultimately starts up the EMR cluster, configures it and provides JupyterHub.

### Step 5: Open Security Group for SSH connections

For security reasons, the JupyterHub web interface is only provided on the `localhost` of the master instance of the cluster. Therefore we will connect to the master via an SSH tunnel and access JupyterHub via that tunnel. In order for this to work we must first extend the security group of the master by a TCP inbound rule on port 22. The source IP should be set to your own IP or your own CIDR range in order to restrict access accordingly. Steps:

- Open `EMR` in the AWS Console
- Open the previously created cluster
- Click on the tab `Summary` and find the security group of the master instance, click on the link
- Add the Inbound Rule to TCP Port 22 in the Security Group with Source IP set to 'My own IP' and save


## Connect to JupyterHub

### Step 1: Trust self-signed certificates for localhost

The HTTPS connection to the web interface of JupyterHub, to which we will connect, is protected by a self-signed certificate from the EC2 instance. This is rejected by the Chrome browser for security reasons by default. To solve this problem the Chrome browser has to be opened under the following link: `chrome: // flags / # allow-insecure-localhost` and configured accordingly.

### Step 2: Establishing the SSH connection

In the last step, the SSH connection can be established:

```bash
ssh -i <YOUR KEY PAIR>.pem -N -L 10501:<PUBLIC DNS OF YOUR EMR MASTER INSTANCE>:9443 hadoop@<PUBLIC DNS OF YOUR EMR MASTER INSTANCE>
```

You can now access the JupyterHub web interface on the client computer under `https: // localhost: 10501`. The username corresponds to the password and the usernames configured above in the shell script are available.

## Writing your notebooks

The notebook should be run with the PySpark kernel. If graphics from Seaborn or Matplotlib are to be displayed in the notebook, these must be output with `% matplot plt` instead of the usual inline`% matplotlib inline` or the command `plt.show ()` [4].

# References:

- [1] [https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html#EMR-RunJobFlow-request-Configurations](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html#EMR-RunJobFlow-request-Configurations)
- [2] [https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-jupyterhub-pam-users.html](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-jupyterhub-pam-users.html)
- [3] [https://docs.aws.amazon.com/emr/latest/ManagementGuide/using-service-linked-roles.html](https://docs.aws.amazon.com/emr/latest/ManagementGuide/using-service-linked-roles.html)
- [4] [https://aws.amazon.com/de/blogs/big-data/install-python-libraries-on-a-running-cluster-with-emr-notebooks/](https://aws.amazon.com/de/blogs/big-data/install-python-libraries-on-a-running-cluster-with-emr-notebooks/

)c