from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError
import pandas as pd
from io import StringIO, BytesIO

# Charger les variables d'environnement
load_dotenv()

AWS_KEY = os.getenv("AWS_ID")  
AWS_SECRET = os.getenv("AWS_Secret")
REGION_NAME = os.getenv("Region")

session = boto3.Session(
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    region_name=REGION_NAME
)
dynamodb = session.resource('dynamodb')

s3 = boto3.client('s3', aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
dynamodb = session.resource('dynamodb')
s3_client = boto3.client('s3', aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)

def extract_text_from_bucket_discussion(bucket_name, id_user, id_discussion):
    """
    Retrieves and decodes the text content of files from an S3 bucket.
    """
    contenu_texte_fichier = {}
    path_bucket = f"{id_user}/{id_discussion}/"

    try:
        list_files_in_bucket = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=path_bucket)
        if 'Contents' not in list_files_in_bucket:
            print(f"No files found in the user folder {path_bucket}.")
            return

        files_in_bucket = [file for file in list_files_in_bucket['Contents'] if file['Size'] > 0]
        if not files_in_bucket:
            print(f"No valid files found in the user folder {path_bucket}.")
            return

        for file in files_in_bucket:
            file_key = file['Key']
            file_obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)['Body'].read()

            try:
                # Attempt to decode as UTF-8
                decoded_content = file_obj.decode('utf-8')
            except UnicodeDecodeError:
                print(f"Failed to decode {file_key} as UTF-8. Attempting ISO-8859-1...")
                try:
                    # Fallback to ISO-8859-1
                    decoded_content = file_obj.decode('ISO-8859-1')
                except UnicodeDecodeError:
                    print(f"Failed to decode {file_key} as ISO-8859-1. Skipping file.")
                    continue

            contenu_texte_fichier[file_key] = decoded_content

        return contenu_texte_fichier
    except ClientError as e:
        print(f"Error retrieving files from bucket {bucket_name}: {e}")
        return
