# Create a Spark Cluster on AWS EMR and run Jupyter Notebooks

Fuer Data Science Projekte mit grossen Datensaetzen hat sich Apache Spark zu einem unverzichtbarem Tool entwickelt. Typischerweise wird Spark in groesseren Clustern betrieben, so dass die Verarbeitung verteilt durchgefuehrt werden kann. Dazu wird fuer die initiale Daten Exploration und fuer Auswertungen vorzugsweise Jupyter Notebooks verwendet. 

Dieses Tutorial beschreibt wie mittels AWS Stepfunctions ein Apache Spark Cluster incl. JupyterHub auf AWS Elastic Map Reduce (EMR) aufgesetzt werden kann. Das Tutorial betrachtet folgende Aspekte:

- Installation benoetigter python packages als Bootstrap action
- Konfiguration von Usern fuer JupyterHub und permanente Speicherung von Notebooks im eigenen S3-Bucket
- Einrichten einer IAM-Rolle zur Ausfuehrung der Stepfunction
- Verbinden zum JupyterHub via SSH Tunnel

Alternativ zu dem hier beschriebenen Ansatz mittels AWS Stepfunctions kann auch ein Cloudformation Template definiert werden. Da in Data Science Workflows jedoch oft Berechnungen zu automatisch bestimmten Ereignissen oder Zeitpunkten (ohne Jupyter Notebook) starten sollen, werden hier AWS Stepfunctions verwendet, die ueber AWS Eventbridge aufgerufen werden koennen. Ebenfalls lassen sich aus den hier dargestellten Bausteinen groesseren Data Science workflows mit zusaetzlichen Schritten definieren, z.B. zur Datenbereinigung und dem automatischen Trainieren von Machine Learning Modellen.


## Preparation of bootstrapping scripts

Bevor wir die AWS Stepfunction definieren und anlegen koennen, muessen die Scripte erstellt und hochgeladen werden, die beim Bootstrapping Starten des Clusters automatisch ausgefuehrt werden sollen.

### Step 1: The AWS EMR Bootstrap Script for Python

Wenn der cluster hochfaehrt sollen automatisch auf allen Nodes die benoetigten python packages installiert werden. Dieser Prozess heisst Bootstrapping. Technisch wird dabei ein shell script auf allen Nodes des Clusters ausgefuehrt:

```sh
#!/bin/sh

# Install needed python packages
sudo pip3 install seaborn matplotlib numpy pandas pathlib boto3
```

Schritte:

- Speichere das Script in der Datei `bootstrap-modules.sh`

Die hier dargestellten Pakete koennen natuerlich entsprechend der eigenen Anforderungen angepasst werden.

### Step 2: The AWS EMR Bootstrap Script for JupyterHub

Wir werden JupyterHub in auf dem AWS EMR cluster installieren und moechten aus Security Gruenden eigene PAM user accounts incl. home directory in S3 anlegen. Als ersten Schritt muessen wir dazu ein shell script erzeugen, das die user im JupyterHub Docker container erzeugen wird [2]:

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

Schritte:

- Ersetze die Namen im Array `USERS=(philipp admin)` mit den benoetigten user names.
- Speichere das Script in der Datei `create-jupyter-users.sh`.

### Step 3: Upload to S3

Damit der AWS EMR cluster das bootstrap script ausfuehren kann muss es in einem S3 Bucket abgelegt werden. Schritte:
- Erstelle einen S3 bucket in der Region deiner Wahl. Du kannst bei der Standardkonfiguration bleiben, d.h. no public access und keine eigene bucket policy. Hintergrund ist, dass die default IAM Rolle, die von AWS EMR verwendetn wird, vollen Zugriff auf S3 hat. Natuerlich kann dies zur Verbesserung des Security-Footprint individuell noch angepasst werden.

- Lade das script `bootstrap-modules.sh` in den Bucket hoch.
- Lade das script `create-jupyter-notebook.sh` in den Bucket hoch.


## The AWS Stepfunction Script

AWS Stepfunction sind in der eigens dafuer entwickelten Sprache AWS Stepfunction Language (ASL) entwickelt [?] und werden im json format definiert. In diesem Tutorial wird ein einfach Workflow bestehend aus zwei Tasks definiert:

- Definiere eine IAM role zum Ausfuehren der Stepfunction
- Setup EMR Cluster
- Configure JupyterHub Users

### Step 1: Create a EC2 Key Pair

Damit wir spaeter in der Lage sind mit den EC2 Instanzen des EMR clusters SSH Verbindungen und einen SSH Tunnel aufzubauen, muessen wir zuerst ein Key Pair erzeugen. Schritte:

- Gehe in der AWS Console auf `EC2`
- Suche im linken Menue den Bereich `Key Pairs` und klicke darauf
- Erzeuge ein neues Key Pair, speichere lokal das `.pem` file und notiere den Namen

### Step 2: Create IAM role for Stepfunction execution

Schritte:

- Gehe in der AWS Console auf IAM > Policies und erzeuge eine neue Policy mit folgendem Inhalt:


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

- Erzeuge eine neue IAM Role zur Ausfuehrung der Stepfunction. Die Trust Poliy ist:


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

- Unter Permissions soll die oben gezeigte Policy hinzugefuegt werden
- Speichern


Falls man den Workflow auch zum Stoppen des EMR verwenden moechte, so ist sind spezielle IAM permissions noetig [3].


### Step 3: Create the State machine

Im ersten Schritt wird der EMR Cluster inititiert, alle Pakete ueber Bootstrapping ausgefuehrt und JupyterHub zur permanenten Speicherung von Notebooks konfiguriert. Grundlage fuer die zu erstellende Stepfunction ist `RunFlowJob` API [1]. Das folgende Script erfuellt den Zweck. Die Stellen mit `<REPLACE WITH YOUR S3 BUCKET>` muessen durch den Namen des zuvor erstellten S3 Buckets ersetzt werden:


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


Schritte:

- Oeffne `Stepfunctions` in der AWS console und gehe in der Untermenue `State machines`
- Klicke auf `Create state machine` und verwende die Optionen `Author with code snippets` und Type `Standard`
- Kopiere den obigen JSON code in das Textfeld und ersetze den Namen des S3 Bucket entsprechend
- Klicke `Next`. Definiere den Namen z.B. als `create-emr-cluster`. 
- Die Permissions koennen auf `Create new role` belassen werden
- Clicke auf `Create state machine`

### Step 4: Execute the State machine

Die State machine kann nun gestartet werden, was letztlich den EMR Cluster hochfaehrt, konfiguriert und JupyterHub bereitstellt.

### Step 5: Open Security Group for SSH connections

Das Web Interface von JupyterHub wird aus Sicherheitsgruenden nur auf dem `localhost` der Master Instanz des Clusters bereitgestellt. Daher werden wir uns mittels eines SSH Tunnels zum Master verbinden und so auf JupyterHub zugreifen. Damit dies funktioniert muessen wir zuerst die Security Group des Masters um eine TCP Inbound Rule auf Port 22 erstellen. Die Source IP sollte auf die eigene IP oder eine eigene CIDR Range gesetzt werden, um den Zugriff entsprechend einzuschraenken. Schritte:

- Oeffne `EMR` in der AWS Console
- Oeffne den zuvor erstelltetn Cluster
- Klicke auf das Tab `Summary` und finde die Security Group der Master Instanz, klicke auf den Link
- Fuege in der Security Group die Inbound Rule auf TCP Port 22 hinzu mit Source IP auf 'My own IP' gesetzt und speichere

## Zum JupyterHub verbinden

### Step 1: Vertraue selbst-signierten Zertifikaten fuer Localhost

Die HTTPS Verbindung zum Webinterface von JupyterHub, zu dem wir uns verbinden werden, wird durch ein von der EC2 Instanz selbst-signiertes Zertifikat geschuetzt. Dieses wird vom Chrome Browser standardmaessig aus Sicherheitsgruenden abgelehnt. Um dieses Problem zu loesen muss der Chrome Browser unter folgendem Link geoeffnet werden: `chrome://flags/#allow-insecure-localhost` und entsprechend konfiguriert werden.

### Step 2: Aufbau der SSH Verbindung

Im letzten Schritt kann dann die SSH Verbindung aufgebaut werden:

```bash
ssh -i <YOUR KEY PAIR>.pem -N -L 10501:<PUBLIC DNS OF YOUR EMR MASTER INSTANCE>:9443 hadoop@<PUBLIC DNS OF YOUR EMR MASTER INSTANCE>
```

Man kann nun auf dem Client Rechner unter `https://localhost:10501` auf das JupyterHub Webinterface zugreifen. Der Username entspricht dem Password und es stehen die oben im Shell Script konfigurierten Usernames zur Verfuegung.


Referenzen:

- [1] [https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html#EMR-RunJobFlow-request-Configurations](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html#EMR-RunJobFlow-request-Configurations)
- [2] [https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-jupyterhub-pam-users.html](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-jupyterhub-pam-users.html)
- [3] [https://docs.aws.amazon.com/emr/latest/ManagementGuide/using-service-linked-roles.html](https://docs.aws.amazon.com/emr/latest/ManagementGuide/using-service-linked-roles.html)