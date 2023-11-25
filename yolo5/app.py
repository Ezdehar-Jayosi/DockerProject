import time
from pathlib import Path

import botocore
from detect import run
from flask import Flask, request
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
    # Generates a UUID for this current prediction HTTP request. This id can be used as a reference in logs to identify and track individual prediction requests.
    prediction_id = str(uuid.uuid4())

    logger.info(f'prediction: {prediction_id}. start processing')

    # Receives a URL parameter representing the image to download from S3
    img_name = request.args.get('imgName')

    # TODO download img_name from S3, store the local image path in original_img_path
    #  The bucket name should be provided as an env var BUCKET_NAME.
    original_img_path = f'{img_name}'
    try:
        # Download the image from S3
        if img_name is not None:
            s3.download_file(images_bucket, img_name, original_img_path)
        else:
            # Log an error or handle the situation where img_name is None
            logger.error("Image name is None. Cannot download file.")
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            logger.error("The image does not found")
        else:
            logger.error(e)
            raise
    logger.info(f'prediction: {prediction_id}/{original_img_path}. Download img completed')

    # Predicts the objects in the image
    run(
        weights='yolov5s.pt',
        data='data/coco128.yaml',
        source=original_img_path,
        project='static/data',
        name=prediction_id,
        save_txt=True
    )

    logger.info(f'prediction: {prediction_id}/{original_img_path}. done')

    # This is the path for the predicted image with labels
    # The predicted image typically includes bounding boxes drawn around the detected objects, along with class labels and possibly confidence scores.
    predicted_img_path = Path(f'static/data/{prediction_id}/{original_img_path}')

    # TODO Uploads the predicted image (predicted_img_path) to S3 (be careful not to override the original image).
    # s3_prediction_img_path = f'{img_name.split(".")[0]}_prediction.jpg'
    if predicted_img_path.exists():
        try:
            s3.upload_file(str(predicted_img_path), images_bucket, f'{img_name.split(".")[0]}_prediction.jpg')
        except Exception as e:
            logger.error(e)
            raise
            return
    else:
        logger.error(f'Prediction image does not exist at: {predicted_img_path}')
        # handle the error or return an appropriate response
        return

    # Parse prediction labels and create a summary
    pred_summary_path = Path(f'static/data/{prediction_id}/labels/{original_img_path.split(".")[0]}.txt')


    if pred_summary_path.exists():
        with open(pred_summary_path) as f:
            labels = f.read().splitlines()
            labels = [line.split(' ') for line in labels]
            labels = [{
                'class': names[int(l[0])],
                'cx': float(l[1]),
                'cy': float(l[2]),
                'width': float(l[3]),
                'height': float(l[4]),
            } for l in labels]

        logger.info(f'prediction: {prediction_id}/{original_img_path}. prediction summary:\n\n{labels}')

        prediction_summary = {
            'prediction_id': prediction_id,
            'original_img_path': original_img_path,
            'predicted_img_path': str(predicted_img_path),
            'labels': labels,
            'time': time.time()
        }

        # TODO store the prediction_summary in MongoDB
        # Modify this line in your Flask app code
        collection.insert_one({"img_name": str(predicted_img_path), "predictions": prediction_summary})

        return prediction_summary
    else:
        #return f'prediction: {prediction_id}/{original_img_path}. prediction result not found', 404
        return [{
            'class': "", 'cx': 0, 'cy': 0, 'width': 0, 'height': 0
        }]


if __name__ == "__main__":
    for rule in app.url_map.iter_rules():
        print(rule)
    app.run(host='0.0.0.0', port=8081)
