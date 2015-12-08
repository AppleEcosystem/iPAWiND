import logging
import time
from datetime import datetime, timedelta
from io import BytesIO
import aioboto3
from pytz import UTC

logger = logging.getLogger(__name__)

class R2Storage:
    """
    Simple Cloudflare r2 storage connection
    :param endpoint_url: Your Cloudflare endpoint url
    :type endpoint_url: string
    :param key_id: Your key id
    :type key_id: string
    :param access_key: Your access key
    :type access_key: string
    :param bucket: R2 bucket name
    :type bucket: string
    :param bucket_url: R2 bucket public url
    :type bucket_url: string
    """

    def __init__(self, endpoint_url, key_id, access_key, bucket, bucket_url):
        self.session = aioboto3.Session(key_id, access_key)
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self.bucket_url = bucket_url

    async def upload_file(self, file, path):
        async with self.session.client('s3', endpoint_url=self.endpoint_url) as client:
            start = time.perf_counter()
            if isinstance(file, str):
                # If the file is a string path, open the file and read it into a BytesIO object
                with open(file, 'rb') as f:
                    file_obj = BytesIO(f.read())
                await client.put_object(Bucket=self.bucket, Key=path, Body=file_obj)
            else:
                # If file is already a file-like object, upload directly
                await client.put_object(Bucket=self.bucket, Key=path, Body=file)
            end = time.perf_counter()
            logger.info(f"Uploaded file in {end - start:.2f} seconds.")
        return self.bucket_url + '/' + path
