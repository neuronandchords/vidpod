from fastapi import FastAPI, HTTPException
import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel

# Initialize FastAPI
app = FastAPI()

# AWS credentials
AWS_ACCESS_KEY_ID = 'AKIA2RNQ6W7SDNKB6Y4L'
AWS_SECRET_ACCESS_KEY = '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'
AWS_BUCKET_NAME = 'vidpod'
S3_ENDPOINT_URL = f"https://{AWS_BUCKET_NAME}.s3.amazonaws.com/"
AWS_REGION ="ap-south-1"

# Initialize Amazon Polly and S3 clients
polly_client = boto3.client('polly', region_name=AWS_REGION,
                            aws_access_key_id=AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
s3_client = boto3.client('s3', region_name=AWS_REGION,
                         aws_access_key_id=AWS_ACCESS_KEY_ID,
                         aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

def text_to_speech(i, description):

    # Convert text to speech using Amazon Polly
    try:
        response = polly_client.synthesize_speech(
            OutputFormat='mp3',
            Text=description,
            VoiceId='Joanna'  # You can choose different voices
        )
    except ClientError as e:
        raise HTTPException(status_code=500, detail="Failed to synthesize speech: {}".format(e))

    if "AudioStream" in response:
        # Upload the speech as an MP3 file to S3
        try:
            s3_client.put_object(
                Body=response['AudioStream'].read(),
                Bucket=AWS_BUCKET_NAME,
                Key=f'fake {i}.mp3'
            )
        except ClientError as e:
            raise HTTPException(status_code=500, detail="Failed to upload speech to S3: {}".format(e))
        
        # Return the S3 URL of the uploaded speech
        s3_url = "https://{}.s3.amazonaws.com/fake {}.mp3".format(AWS_BUCKET_NAME, i)
        return s3_url
    else:
        raise HTTPException(status_code=500, detail="Failed to synthesize speech: AudioStream not found in response")