from flask import Flask, jsonify, request
from mistralai import Mistral
from mistralai.models import UserMessage, AssistantMessage
from dotenv import load_dotenv
import os
import asyncio
import uuid
from flask_cors import CORS
import datetime
import json
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

def upload_to_s3(file_obj, user_id, conversation_id):
    """
    Upload a file to S3 inside a folder structure based on user ID and conversation ID.

    Args:
        file_obj: The file-like object to upload.
        user_id: The ID of the user.
        conversation_id: The ID of the conversation.
    """
    bucket_name = "process-boost"

    # Sanitize file name
    file_name = file_obj.filename
    if any(char in file_name for char in ["/", "\\", "//"]):
        file_name = file_name.replace("/", "_").replace("\\", "_").replace("//", "_")

    # Define the folder structure
    user_folder = f"{user_id}/"
    conversation_folder = f"{user_folder}{conversation_id}/"
    file_key = f"{conversation_folder}{file_name}"

    try:
        # Check if user folder exists
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=user_folder)
        if 'Contents' not in response:
            print(f"User folder {user_folder} does not exist. Creating it...")
            s3_client.put_object(Bucket=bucket_name, Key=user_folder)

        # Check if conversation folder exists
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=conversation_folder)
        if 'Contents' not in response:
            print(f"Conversation folder {conversation_folder} does not exist. Creating it...")
            s3_client.put_object(Bucket=bucket_name, Key=conversation_folder)

        # Upload the file to the defined key
        s3_client.upload_fileobj(file_obj, bucket_name, file_key)

        print(f"File successfully uploaded to {bucket_name}/{file_key}")
    except ClientError as e:
        print(f"Error occurred while uploading file to S3: {e}")
        raise

def from_bucket_to_dataframe(file_key, nom_bucket):
    try:
        response = s3.get_object(Bucket=nom_bucket, Key=file_key)

        file_extension = file_key.split('.')[-1].lower()

        file_content = response['Body'].read()
        if file_extension == 'csv' or file_extension == 'txt' or file_key == 'base_secteur_taux_growth':
            # Si c'est un fichier CSV, lire avec pd.read_csv
            data_matched = pd.read_csv(StringIO(file_content.decode('utf-8')), encoding='utf-8', sep=',', on_bad_lines='skip')
        elif file_extension in ['xls', 'xlsx']:
            data_matched = pd.read_excel(BytesIO(file_content), engine='openpyxl')
        elif file_extension == 'json':
            data_matched = pd.read_json(StringIO(file_content.decode('utf-8')))
        else:
            print(f"Le format de fichier .{file_extension} n'est pas pris en charge.")
            return None
        return data_matched

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"L'objet n'existe pas dans le bucket {nom_bucket} à l'emplacement {file_key}")
        else:
            raise
        return None

def from_dataframe_to_bucket(dataframe, file_key, nom_bucket):
    # Créer un client S3
    try:
        # Convertir le DataFrame en CSV dans une chaîne de caractères
        csv_buffer = StringIO()
        dataframe.to_csv(csv_buffer, index=False, encoding='utf-8')

        # Pousser le fichier CSV dans le bucket S3 au chemin d'accès indiqué
        s3.put_object(Bucket=nom_bucket, Key=file_key, Body=csv_buffer.getvalue())

        print(f"Le fichier CSV a été chargé avec succès dans {nom_bucket}/{file_key}")

    except ClientError as e:
        print(f"Erreur lors du chargement du fichier CSV dans le bucket S3 : {e}")
        return None