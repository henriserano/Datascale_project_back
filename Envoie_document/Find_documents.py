from flask import Flask, request, jsonify
import boto3
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from dotenv import load_dotenv
import os
from threading import Lock
import json
from flask_cors import CORS
from services.similarity import preload_embeddings, find


app = Flask(__name__)
CORS(app)
load_dotenv()

# Configurations AWS
aws_access_key_id = os.getenv("AWS_ID")
aws_secret_access_key = os.getenv("AWS_SECRET")
region_name = os.getenv("REGION")
bucket_name = os.getenv("BUCKET_NAME", "base-tweet-rag")
DYNAMO_TABLE_NAME = os.getenv("DYNAMO_TABLE_NAME", "vector_rag")
MODEL_NAME = "bert-base-uncased"
MIN_SIMILARITY = 0.5

# Initialisation AWS
session = boto3.Session(
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name,
)
dynamodb = session.resource("dynamodb")
table = dynamodb.Table(DYNAMO_TABLE_NAME)
s3_client = session.client("s3")

# Chargement du modèle BERT
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)

# Cache des embeddings
cache_lock = Lock()
cached_embeddings = []



def fetch_s3_content(key):
    """Récupère le contenu d'un fichier depuis le bucket S3."""
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response["Body"].read().decode("utf-8")
        return content
    except Exception as e:
        print(f"Erreur lors de la récupération du fichier S3 : {e}")
        return None

@app.route('/receive', methods=['POST'])
def receive_text():
    try:
        data = request.get_json()
        if not data or "text" not in data:
            return jsonify({"error": "Bad Request", "message": 'Expected a JSON object with a "text" key.'}), 400

        text = data["text"]
        best_document, score = find(text)

        if best_document is None:
            return jsonify({"error": "No match found"}), 404

        # Charger le contenu associé depuis S3
        s3_key = best_document["metadata"]["source"]
        s3_content = fetch_s3_content(s3_key)

        return jsonify({
            "status": "success",
            "document": {
                "id_vector": best_document["id_vector"],
                "metadata": best_document["metadata"],
                "text": best_document["text"],
                "similarity_score": score,
                "s3_content": s3_content,
            }
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/test', methods=['GET'])
def test_endpoint():
    """Test simple pour valider le bon fonctionnement de l'API."""
    return jsonify({"status": "success", "message": "Test successful!"}), 200

if __name__ == "__main__":
    # Précharger les embeddings au démarrage
    preload_embeddings()
    app.run(host="0.0.0.0", port=5002)
