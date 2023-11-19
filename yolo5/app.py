import time
from pathlib import Path

import botocore
from flask import Flask, request
from detect import run
import uuid
import yaml
from loguru import logger
import os
from pymongo import MongoClient
import boto3

try:
    images_bucket = os.environ['BUCKET_NAME']
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
except KeyError as e:
    logger.error(f"Missing environment variable: {e}")
    exit(1)

# Set up AWS S3 client
s3 = boto3.client('s3', aws_access_key_id, aws_secret_access_key)

# Set up MongoDB client
try:
    mongo_uri = 'mongodb://mongo1:27017,mongo2:27018,mongo3:27019/?replicaSet=myReplicaSet'
    mongo_client = MongoClient(mongo_uri)
    print("after mongo client")
    db = mongo_client['EDS']
    collection = db['ECollection']
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    exit(1)

with open("data/coco128.yaml", "r") as stream:
    names = yaml.safe_load(stream)['names']

app = Flask(__name__)

# Flag to track whether initialization has occurred
initialized = False

@app.before_request
def before_request():
    global initialized
    if not initialized:
        # This block will only run before the first request
        logger.info("Connecting to MongoDB")
        initialized = True

@app.teardown_appcontext
def teardown_appcontext(exception=None):
    # This function is called when the application context is popped.
    # It ensures that the MongoDB connection is closed.
    mongo_client.close()
    logger.info("MongoDB connection closed")

@app.route('/predict', methods=['POST'])
def predict():
    # Rest of the code remains unchanged

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8081)
