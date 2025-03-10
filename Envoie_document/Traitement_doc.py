import boto3
import os
import json
import uuid
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer, AutoModel
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
import torch
from decimal import Decimal

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Charger les configurations depuis .env
aws_access_key_id = os.getenv("AWS_ID")
aws_secret_access_key = os.getenv("AWS_Secret")
region_name = os.getenv("Region")
bucket_name = "json-process-metier"
# Initialisation de la session Boto3 avec des clés explicites
session = boto3.Session(
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name,
)

# Initialiser les clients S3 et DynamoDB
s3_client = session.client("s3")
dynamodb = session.resource("dynamodb")
table = dynamodb.Table("vector_rag")
# Charger le modèle BERT depuis Hugging Face
MODEL_NAME = "bert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)

# Définir un séparateur de texte
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


def list_files_in_bucket(bucket_name):
    """Liste les fichiers dans le bucket S3."""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        return []
    except Exception as e:
        print(f"Erreur lors de l'accès au bucket {bucket_name} :", e)
        return []

def convert_to_decimal(arr):
    """
    Convertit une liste de nombres à virgule flottante en une liste de Decimals.
    """
    return [Decimal(str(x)) for x in arr]

def vectorize_and_store_documents(files):
    """Vectorise les documents et stocke les vecteurs avec leur texte brut dans DynamoDB."""
    for file_key in files:
        print(f"Traitement du fichier : {file_key}")
        
        # Télécharger le fichier depuis S3
        file_content = download_file(bucket_name, file_key)
        if not file_content:
            continue

        # Découper le contenu en morceaux
        chunks = text_splitter.split_text(file_content)

        # Vectoriser chaque morceau
        documents = [Document(page_content=chunk, metadata={"source": file_key}) for chunk in chunks]
        embeddings = embed_text([doc.page_content for doc in documents])

        for i, embedding in enumerate(embeddings):
            try:
                vector_id = str(uuid.uuid4())
                item = {
                    "id_vector": vector_id,  # Identifiant unique
                    "embedding": convert_to_decimal(embedding.tolist()),  # Embedding vectorisé
                    "text": documents[i].page_content,  # Texte brut vectorisé
                    "metadata": json.dumps(documents[i].metadata),  # Métadonnées (source du document)
                }
                table.put_item(Item=item)  # Insérer dans DynamoDB
                print(f"Vecteur {vector_id} ajouté dans DynamoDB avec texte.")
            except Exception as e:
                print(f"Erreur lors de l'ajout du vecteur {i} dans DynamoDB :", e)


def download_file(bucket_name, key):
    """Télécharge un fichier depuis S3."""
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"Erreur lors du téléchargement du fichier {key} :", e)
        return None

def embed_text(texts):
    """
    Génère les embeddings pour une liste de textes en utilisant BERT.
    """
    try:
        inputs = tokenizer(
            texts, padding=True, truncation=True, return_tensors="pt", max_length=512
        )
        with torch.no_grad():
            outputs = model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1)
        return embeddings.numpy()
    except Exception as e:
        print("Erreur lors de la génération des embeddings :", e)
        return []

if __name__ == "__main__":
    # Liste des fichiers dans le bucket S3
    files_in_bucket = list_files_in_bucket(bucket_name)
    if not files_in_bucket:
        print("Aucun fichier trouvé dans le bucket S3.")
    else:
        vectorize_and_store_documents(files_in_bucket)
