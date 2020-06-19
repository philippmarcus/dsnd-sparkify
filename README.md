# Sparkify

Sparkify is a fictional music streaming service, comparable to Spotify. In this project, a user log of approx. 12 GB is given. The entries contain all events created by single users, e.g. by logging in, selecting the next song, or liking a song. 

Some users within this event log cancelled their subscription. The goal of this project is to predict for a given trace of user evens whether this user is likely to cancel his subscription and consequently stop to use Sparkify.

The technical solution is based on PySpark and Jupyter Notebook. It is executable on Amazon EMR.

## Usage instructions

1. Start a local `jupyter-pyspark` container by executing `./start_pyspark.sh`
2. Access the Jupyter Notebook at `localhost:8888`
3. Execue the Jupyter Notebook 

## Files

The project contains the following files:
```
.
├── README.md
├── Sparkify.ipynb (Main Notebook)
├── mini_sparkify_event_data.json (Partial data set)
├── spark-warehouse
└── start-pyspark.sh (shell script to start jupyter-pyspark)
```
