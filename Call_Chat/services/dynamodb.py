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

def get_user_info(user_id):
    """
    Récupère les informations de l'utilisateur à partir de son ID.
    Args:
        user_id (_type_): _description_
    """
    table_user = dynamodb.Table('Datascale_users')
    print("USER ID : ",user_id)  
    response = table_user.get_item(Key={'ID_Users': str(user_id)})
    return response['Item']

def push_request_dynamodb(json_generated):
    """
    Push the generated JSON to DynamoDB dynamically, adapting to the provided keys.
    """
    try:
        # Log the generated JSON
        print("JSON GENERATED:", json_generated)
        print("JSON GENERATED TYPE:", type(json_generated))

        # Retrieve user info from DynamoDB if 'Nom utilisateur' key exists
        user_info = {}
        if "Nom utilisateur" in json_generated:
            user_info = get_user_info(json_generated["Nom utilisateur"])
            print("USER INFO:", user_info)

        # Prepare the item for DynamoDB
        item = {
            "RequestID": str(uuid.uuid4()),  # Always include a unique RequestID
        }

        # Add all keys from json_generated dynamically
        for key, value in json_generated.items():
            item[key] = value

        # Add additional user information if available
        if user_info:
            item.update({
                "UserEmail": user_info.get("Email", ""),
                "UserFirstName": user_info.get("FirstName", ""),
                "UserLastName": user_info.get("LastName", ""),
            })

        # Push the item to the Requests table
        table_request = dynamodb.Table('Requests')
        table_request.put_item(Item=item)

        print("Request successfully pushed to DynamoDB.")

    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        raise
    except KeyError as e:
        print("Missing expected key in JSON:", e)
        raise
    except Exception as e:
        print("Error pushing to DynamoDB:", e)
        raise

def get_item_dynanodb(table_name, key):
    """
    Get an item from a DynamoDB table based on the key.
    """
    table = dynamodb.Table(table_name)
    response = table.get_item(Key=key)
    return response['Item'] if 'Item' in response else None 