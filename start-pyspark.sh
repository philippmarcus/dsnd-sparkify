#!/bin/sh
docker run -p 8888:8888 -e PASSWORD=password -v $PWD:/home/jovyan/work --name spark jupyter/pyspark-notebook
