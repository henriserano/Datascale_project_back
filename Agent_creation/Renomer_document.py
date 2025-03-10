from flask import Flask, jsonify, request
from dotenv import load_dotenv
from transformers import pipeline, AutoTokenizer, AutoModel
import os
import boto3
from botocore.exceptions import ClientError
import pandas as pd
from io import StringIO, BytesIO
import json
import torch
from services.process_files import process_files

# Charger les variables d'environnement
load_dotenv()
bucket_name = "process-boost"
AWS_KEY = os.getenv("AWS_ID")
AWS_SECRET = os.getenv("AWS_Secret")
REGION_NAME = os.getenv("Region")

# Initialiser les services AWS
session = boto3.Session(
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    region_name=REGION_NAME
)
dynamodb = session.resource('dynamodb')
s3_client = boto3.client('s3', aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)

# Initialiser Hugging Face
model_name = "sentence-transformers/all-MiniLM-L6-v2"
embedding_model = AutoModel.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

# Initialiser Flask
app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process_endpoint():
    data = request.json
    if not all(k in data for k in ("id_process", "id_discussion", "id_user")):
        return {"error": "Les champs 'id_process', 'id_discussion', et 'id_user' sont requis."}, 400

    id_process = data['id_process']
    id_discussion = data['id_discussion']
    id_user = data['id_user']

    result, status = process_files(id_process, id_discussion, id_user)
    return jsonify(result), status

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004)