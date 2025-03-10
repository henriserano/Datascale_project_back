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

# Fonctions utilitaires
def calculate_similarity(embedding1, embedding2):
    """Calcule la similarité cosinus entre deux embeddings."""
    embedding1 = embedding1.unsqueeze(0) if embedding1.dim() == 1 else embedding1
    embedding2 = embedding2.unsqueeze(0) if embedding2.dim() == 1 else embedding2
    return float(torch.nn.functional.cosine_similarity(embedding1, embedding2).item())

def get_embeddings(text):
    """Génère les embeddings pour un texte donné."""
    tokens = tokenizer(text, truncation=True, return_tensors="pt")
    with torch.no_grad():
        embeddings = embedding_model(**tokens).last_hidden_state.mean(dim=1)
    return embeddings.squeeze()

def process_files(id_process, id_discussion, id_user):
    """Processus principal pour analyser et mapper les fichiers avec des titres requis."""
    table_process = dynamodb.Table('Sector')
    response = table_process.get_item(Key={'ID_Sector': str(id_process)})
    process = response['Item']
    documents_process = json.loads(process['Process_Model'])['documents']

    path_bucket = f"{id_user}/{id_discussion}/"
    try:
        list_files_in_bucket = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=path_bucket)
        if 'Contents' not in list_files_in_bucket:
            return {"error": f"Aucun fichier trouvé dans le dossier utilisateur {path_bucket}."}, 404

        files_in_bucket = [file for file in list_files_in_bucket['Contents'] if file['Size'] > 0]

        mapping = []
        used_files = set()

        for doc in documents_process:
            required_title = doc['title']
            required_embedding = get_embeddings(required_title)

            best_match = None
            best_score = 0

            for file in files_in_bucket:
                if file['Key'] in used_files:
                    continue

                file_name = file['Key'].split('/')[-1]
                file_embedding = get_embeddings(file_name)
                score = calculate_similarity(required_embedding, file_embedding)

                if score > best_score:
                    best_score = score
                    best_match = file

            if best_match:
                new_key = f"{path_bucket}{required_title}.pdf"
                s3_client.copy_object(
                    Bucket=bucket_name,
                    CopySource={
                        'Bucket': bucket_name,
                        'Key': best_match['Key']
                    },
                    Key=new_key
                )

                mapping.append({
                    "required_title": required_title,
                    "file_name": best_match['Key'],
                    "confidence": f"{best_score:.2f}"
                })
                used_files.add(best_match['Key'])

        return mapping, 200

    except ClientError as e:
        return {"error": f"Erreur lors du traitement des fichiers dans S3: {e}"}, 500
