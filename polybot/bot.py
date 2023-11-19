import telebot
from loguru import logger
import os
import time
from telebot.types import InputFile


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
   def handle_message(self, msg):
       logger.info(f'Incoming message: {msg}')

       if self.is_current_msg_photo(msg):
           img_path = self.download_user_photo(msg)

           # TODO: Upload the photo to S3
           s3_url = self.upload_to_s3(img_path)

           # TODO: Send a request to the `yolo5` service for prediction
           prediction_result = self.send_yolo5_request(s3_url)

           # TODO: Send results to the Telegram end-user
           self.send_text(msg['chat']['id'], f'Object Detection Results: {prediction_result}')

   def upload_to_s3(self, img_path):
       # TODO: Implement the logic to upload the image to S3
       # Example: You can use a library like boto3 to upload the image to your S3 bucket
       # Replace the placeholders with your actual S3 credentials and bucket information
       # s3.upload_file(img_path, 'your_bucket_name', 'your_s3_key')

       # Placeholder: Return a dummy S3 URL for demonstration purposes
       return f'https://your-s3-bucket.s3.amazonaws.com/{os.path.basename(img_path)}'

   def send_yolo5_request(self, s3_url):
       # TODO: Implement the logic to send a request to the yolo5 service
       # Example: You can use the requests library to perform an HTTP POST request
       # Replace the URL with the actual endpoint of your yolo5 service
       yolo5_url = 'http://yolo5-service-endpoint/predict'
       response = requests.post(yolo5_url, json={'s3_url': s3_url})

       # Placeholder: Return a dummy prediction result for demonstration purposes
       return response.json()['predictions']
