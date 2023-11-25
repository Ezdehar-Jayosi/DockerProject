import boto3
import telebot
from boto3 import s3
from loguru import logger
import os
import time
from telebot.types import InputFile
import argparse
import subprocess
import requests


class Bot:

    def __init__(self, token, telegram_chat_url):
        # create a new instance of the TeleBot class.
        # all communication with Telegram servers are done using self.telegram_bot_client
        self.telegram_bot_client = telebot.TeleBot(token)

        # remove any existing webhooks configured in Telegram servers
        self.telegram_bot_client.remove_webhook()
        time.sleep(0.5)

        # set the webhook URL
        self.telegram_bot_client.set_webhook(url=f'{telegram_chat_url}/{token}/', timeout=60)

        logger.info(f'Telegram Bot information\n\n{self.telegram_bot_client.get_me()}')

    def send_text(self, chat_id, text):
        self.telegram_bot_client.send_message(chat_id, text)

    def send_text_with_quote(self, chat_id, text, quoted_msg_id):
        self.telegram_bot_client.send_message(chat_id, text, reply_to_message_id=quoted_msg_id)

    def is_current_msg_photo(self, msg):
        return 'photo' in msg

    def download_user_photo(self, msg):
        """
        Downloads the photos that sent to the Bot to `photos` directory (should be existed)
        :return:
        """
        if not self.is_current_msg_photo(msg):
            raise RuntimeError(f'Message content of type \'photo\' expected')

        file_info = self.telegram_bot_client.get_file(msg['photo'][-1]['file_id'])
        data = self.telegram_bot_client.download_file(file_info.file_path)
        folder_name = file_info.file_path.split('/')[0]

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        with open(file_info.file_path, 'wb') as photo:
            photo.write(data)

        return file_info.file_path

    def send_photo(self, chat_id, img_path):
        if not os.path.exists(img_path):
            raise RuntimeError("Image path doesn't exist")

        self.telegram_bot_client.send_photo(
            chat_id,
            InputFile(img_path)
        )

    def handle_message(self, msg):
        """Bot Main message handler"""
        logger.info(f'Incoming message: {msg}')
        self.send_text(msg['chat']['id'], f'Your original message: {msg["text"]}')


class QuoteBot(Bot):
    def handle_message(self, msg):
        logger.info(f'Incoming message: {msg}')

        if msg["text"] != 'Please don\'t quote me':
            self.send_text_with_quote(msg['chat']['id'], msg["text"], quoted_msg_id=msg["message_id"])


class ObjectDetectionBot(Bot):
    def __init__(self, token, telegram_chat_url):
        Bot.__init__(self, token, telegram_chat_url)

        self.Bucket_Name = os.environ['BUCKET_NAME']
        self.REGION = os.environ['REGION']
        # self.s3_client = boto3.client('s3', aws_access_key_id=self.s3_access_key, aws_secret_access_key=self.s3_secret_key)
        """"" self.s3_resource = boto3.resource(
            's3',
            region_name=self.aws_region,
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
        )"""""
        # Set up AWS S3 client
        self.s3 = boto3.client('s3', os.environ.get('AWS_ACCESS_KEY_ID'), os.environ.get('AWS_SECRET_ACCESS_KEY'))

    def format_prediction_results(self, prediction_result):
        # Extract relevant information from the prediction result
        prediction_id = prediction_result["prediction_id"]
        labels = prediction_result["labels"]

        # Create a dictionary to store the count of each detected object
        object_counts = {}

        # Iterate over each label in the prediction result
        for label in labels:
            class_name = label["class"]
            object_counts[class_name] = object_counts.get(class_name, 0) + 1

        # Convert the object counts dictionary to a formatted string
        formatted_results = ", ".join(f"{obj}: {count}" for obj, count in object_counts.items())

        return f"Detected objects: {formatted_results}"

    def download_user_photo(self, msg):
        if not self.is_current_msg_photo(msg):
            raise RuntimeError(f'Message content of type \'photo\' expected')

        file_info = self.telegram_bot_client.get_file(msg['photo'][-1]['file_id'])
        data = self.telegram_bot_client.download_file(file_info.file_path)
        file_unique_id = msg['photo'][-1]['file_unique_id']
        local_file_path = f'photos/{file_unique_id}.jpg'

        try:
            # Create the "photos" directory if it doesn't exist
            os.makedirs('photos', exist_ok=True)

            with open(local_file_path, 'wb') as photo:
                photo.write(data)
        except Exception as e:
            # Log the exception and handle it appropriately
            logger.error(f'Error saving file locally: {e}')
            raise

        return local_file_path

    def handle_message(self, msg):
        try:
            logger.info(f'Incoming message: {msg}')

            if self.is_current_msg_photo(msg):
                logger.info('Message is a photo.')
                img_path = self.download_user_photo(msg)

                # Upload the photo to S3
                s3_url = self.upload_to_s3(img_path)
                logger.info(f'Successfully uploaded to S3: {s3_url}')

                # Send a request to the `yolo5` service for prediction
                prediction_result = self.send_yolo5_request(s3_url)
                logger.info(f'YOLOm prediction result: {prediction_result}')

                # Format the prediction results for the PolyBot
                formatted_results = self.format_prediction_results(prediction_result)

                # Send the formatted results to the Telegram end-user
                self.send_text(msg['chat']['id'], formatted_results)
            else:
                logger.info('Message is not a photo.')
        except Exception as e:
            # Log the exception
            logger.error(f'Error handling message: {e}')

            # Send an error message to the user
            self.send_text(msg['chat']['id'],
                           'An error occurred while processing your request. Please try again later.')
        finally:
            logger.info('Exiting handle_message.')

    def upload_to_s3(self, img_path):
        """
        Uploads the image file to S3.
        :param img_path: Local path of the image file
        :return: S3 URL of the uploaded file
        """
        try:
            # Use the full path of the local file
            self.s3.upload_file(img_path, self.Bucket_Name, os.path.basename(img_path))
        except Exception as e:
            logger.error(f'Error uploading to S3: {e}')
            raise

        # Return the S3 URL
        s3_url = f'https://{self.Bucket_Name}.s3.{self.REGION}.amazonaws.com/{os.path.basename(img_path)}'
        return os.path.basename(img_path)


    def send_yolo5_request(self, s3_url):
        # TODO: Implement the logic to send a request to the yolo5 service
        yolo5_url = 'http://yolom_container:8081/predict'
        response = requests.post(yolo5_url, params={'imgName': s3_url})

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()
