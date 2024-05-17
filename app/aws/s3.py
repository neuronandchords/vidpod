from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse, RedirectResponse
import requests
import boto3
import os
import random
import string
from io import BytesIO

app = FastAPI()


# AWS S3 credentials
AWS_ACCESS_KEY_ID = 'AKIA2RNQ6W7SDUQG6KCK'
AWS_SECRET_ACCESS_KEY = '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'
AWS_BUCKET_NAME = 'vidpod'
S3_ENDPOINT_URL = f"https://{AWS_BUCKET_NAME}.s3.amazonaws.com/"
AWS_REGION ="ap-south-1"

S3_BASE_URL = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/"


s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)


def upload_audio_to_s3(audio_url: str, id:int, podcast_id:int, type):
    try:
        # Open a streaming connection to the audio URL
        with requests.get(audio_url, stream=True) as response:
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to stream audio from the provided URL")

            # Upload the audio file to S3 in chunks
            if(type=="audio"):
                s3_key = f"audio/podcast/{podcast_id}/episode/{id+1}.mp3"
                s3.upload_fileobj(response.raw, AWS_BUCKET_NAME, s3_key)
                s3_url = f"{S3_ENDPOINT_URL}{s3_key}"
            else:
                s3_key = f"image/podcast/{podcast_id}.jpg"
                s3.upload_fileobj(response.raw, AWS_BUCKET_NAME, s3_key)
                s3_url = f"{S3_ENDPOINT_URL}{s3_key}"

        return s3_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def generate_random_string(length=10):
    """Generate a random string of fixed length."""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for _ in range(length))

def upload_xml_to_s3():
    try:
        # Path to the local XML file stored in the codebase
        local_file_path = "podcast_final.xml"
        
        # Generate a random string as the file name
        file_name = "rss/" + generate_random_string() + "final.xml"
        
        # Upload the file to S3 bucket
        s3.upload_file(local_file_path, AWS_BUCKET_NAME, file_name, ExtraArgs={'ACL':'public-read'})
        
        # Construct the S3 URL
        s3_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{file_name}"
        
        return s3_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def upload_and_view_xml():
    try:
        # Path to the local XML file stored in the codebase
        local_file_path = "podcast_final.xml"
        
        # Generate a random string as the file name
        file_name = generate_random_string() + "final.xml"
        
        # Upload the file to S3 bucket
        s3.upload_file(local_file_path, AWS_BUCKET_NAME, file_name)
        
        # Generate a pre-signed URL for the uploaded file
        presigned_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": AWS_BUCKET_NAME, "Key": file_name},
            ExpiresIn=960000  # URL expires in 1 hour (adjust as needed)
        )
        
        # Redirect to the pre-signed URL
        return presigned_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def upload_file(local_file_path: str = None):
    try:
        with open(local_file_path, "rb") as f:
            uploaded_file = BytesIO(f.read())
        file_name = local_file_path.split("/")[-1]  # Extract file name from local file path
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not file_name.endswith('.xml'):
        raise HTTPException(status_code=400, detail="Only XML files are allowed")

    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    try:
        s3_client.upload_fileobj(
            uploaded_file,
            AWS_BUCKET_NAME,
            file_name,
            ExtraArgs={'ContentType' : 'text/xml', 'ContentDisposition' : 'inline'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    file_url = f"{S3_BASE_URL}{file_name}"
    return file_url