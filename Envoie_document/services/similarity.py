import torch
import boto3
import os
import numpy as np
import json
from threading import Lock

from transformers import AutoTokenizer, AutoModel
from dotenv import load_dotenv
import json


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

def preload_embeddings():
    """Précharge les données de DynamoDB dans une structure locale."""
    global cached_embeddings
    print("Préchargement des embeddings depuis DynamoDB...")
    response = table.scan()
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    cached_embeddings = [
        {
            "id_vector": item["id_vector"],
            # Convertir directement les Decimal en float
            "embedding": np.array([float(x) for x in item["embedding"]]),
            "metadata": json.loads(item["metadata"]),
            "text": item["text"]
        }
        for item in items
    ]
    print(f"{len(cached_embeddings)} embeddings préchargés.")


def vectorize_text(text):
    """Vectorise une phrase avec BERT."""
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    embedding = outputs.last_hidden_state.mean(dim=1).numpy()
    return embedding.flatten()

def cosine_similarity(vec1, vec2):
    """Calcule la similarité cosinus entre deux vecteurs."""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def find(text):
    """Trouve les documents les plus pertinents pour un texte donné."""
    try:
        input_vector = vectorize_text(text)
        with cache_lock:
            best_score = -1
            best_document = None
            for item in cached_embeddings:
                similarity = cosine_similarity(input_vector, item["embedding"])
                if similarity > MIN_SIMILARITY and similarity > best_score:
                    best_score = similarity
                    best_document = item
        return best_document, best_score
    except Exception as e:
        print(f"Erreur dans la fonction find : {e}")
        return None, None