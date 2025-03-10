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
from services.extract_text import extract_text_from_bucket_discussion
from services.bucket_services import upload_to_s3
from services.dynamodb import push_request_dynamodb  ,get_item_dynanodb
from services.from_discussion_json import from_discussion_to_json
from services.call_LLM import call_llm

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

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# Charger la clé API
api_key = os.getenv("MISTRAL_AI_KEY")
client = Mistral(api_key=api_key)

# Historique des conversations (cache en mémoire)
conversation_histories = {}

@app.route('/health', methods=['GET']) 
def health():   
    return jsonify({"message": "Server is running!"})
   

@app.route('/', methods=['GET'])
def home():
    """
    Route d'accueil pour vérifier que le serveur fonctionne.
    """
    return jsonify({"message": "Bienvenue sur le serveur Flask pour le chatbot Mistral !"})

@app.route('/api/init_conversation', methods=['POST'])
def init_conversation():
    """
    Initialise une nouvelle conversation et retourne un ID unique pour celle-ci.
    """
    data = request.json
    user_id = data.get("user_id")
    titre_secteur = data.get("titre_secteur")
    description_secteur = data.get("description_secteur")

    if not user_id or not titre_secteur or not description_secteur:
        return jsonify({"error": "Tous les champs (user_id, titre_secteur, description_secteur) sont requis."}), 400

    # Générer un ID de conversation unique
    conversation_id = str(uuid.uuid4())

    # Message d'introduction
    message_1 = f"""En tant qu'assistant conversationnel du secteur {titre_secteur}, tu représentes et manages le service décrit ci-dessous :
{description_secteur}.

Ton objectif principal est d'accompagner le collaborateur tout au long de sa procédure en suivant les consignes ci-dessous :

1. Saluer le collaborateur en répondant "Bienvenue sur le service {titre_secteur}, que puis-je faire pour vous aider ?".
2. Identifier la procédure que le collaborateur souhaite initier (par exemple, dépôt de candidature pour une offre d'emploi, dépôt de bilan comptable, etc.).
3. Demander les informations nécessaires étape par étape pour compléter la procédure (noms, adresses, références, etc.).
4. Inviter le collaborateur à télécharger tous les documents pertinents ou preuves nécessaires à la procédure.
5. Après avoir rassemblé toutes les informations et documents, récapituler les éléments fournis et confirmer que tout est en ordre.
6. Informer le collaborateur qu'il peut soumettre sa demande en indiquant "Si vous vous sentez prêt pour envoyer votre demande, tapez 'send' dans le chat de la conversation".

Exemple :
Collaborateur : "Je souhaite postuler pour l'offre d'emploi de développeur web."
Assistant : "Pouvez-vous me donner votre nom complet et votre adresse email ?"
Collaborateur : "Jean Dupont, jean.dupont@example.com"
Assistant : "Merci Jean. Pouvez-vous télécharger votre CV et votre lettre de motivation ?"
Collaborateur : "Je vais les télécharger maintenant."
Assistant : "D'accord. Voici ce que j'ai rassemblé jusqu'à présent :
Nom complet : Jean Dupont
Adresse email : jean.dupont@example.com
Document(s) : CV, Lettre de motivation
Si vous vous sentez prêt pour envoyer votre demande, tapez 'send' dans le chat de la conversation."

Utilise ce format pour guider chaque conversation et assure-toi d'informer le collaborateur de l'option de soumettre leur demande lorsqu'ils sont prêts, ainsi que de fournir tous les documents nécessaires."""

    # Initialiser l'historique de conversation pour cet ID
    conversation_histories[conversation_id] = [UserMessage(content=message_1)]

    # Appeler le modèle pour la réponse initiale
    response = call_llm(conversation_histories[conversation_id])

    # Ajouter la réponse de l'assistant à l'historique
    conversation_histories[conversation_id].append(AssistantMessage(content=response))

    return jsonify({
        "conversation_id": conversation_id,
        "assistant_response": f"Bienvenue sur le service {titre_secteur}, que puis-je faire pour vous aider ?"
    })

@app.route('/api/send_message', methods=['POST'])
def send_message():
    """
    Envoie un message utilisateur et obtient une réponse de l'assistant.
    """
    if not request.content_type.startswith('multipart/form-data'):
        return jsonify({"error": "Unsupported Media Type. Expected multipart/form-data"}), 415

    conversation_id = request.form.get("conversation_id")
    user_message = request.form.get("message")
    user_id = request.form.get("user_id")
    documents = request.files.getlist("documents") if "documents" in request.files else []

    if not conversation_id or not user_message:
        return jsonify({"error": "Les champs conversation_id et message sont requis."}), 400

    # Vérifier si l'historique de conversation existe
    if conversation_id not in conversation_histories:
        return jsonify({"error": "Aucune conversation trouvée pour cet ID. Veuillez initialiser une conversation."}), 404

    # Upload documents if provided
    if documents:
        for document in documents:
            try:
                upload_to_s3(document, user_id, conversation_id)

            except Exception as e:
                return jsonify({"error": f"Erreur lors de l'upload du document : {e}"}), 500

    # Ajouter le message utilisateur à l'historique
    conversation_histories[conversation_id].append(UserMessage(content=user_message))

    # Appeler le modèle pour la réponse
    response = call_llm(conversation_histories[conversation_id])

    # Ajouter la réponse de l'assistant à l'historique
    conversation_histories[conversation_id].append(AssistantMessage(content=response))

    return jsonify({
        "conversation_id": conversation_id,
        "assistant_response": response
    })

    
@app.route('/api/generate_json', methods=['POST'])
def generate_json():
    """
    Génère un fichier JSON à partir de l'historique de conversation.
    """
    data = request.json
    conversation_id = data.get("conversation_id")
    id_user = data.get("id_user") 
    id_sector = data.get("id_sector")   
    if not conversation_id :
        return jsonify({"error": "Les champs conversation_id  sont requis."}), 400

    # Vérifier si l'historique de conversation existe
    if conversation_id not in conversation_histories:
        return jsonify({"error": "Aucune conversation trouvée pour cet ID."}), 404

    # Générer le JSON
    discussion = conversation_histories[conversation_id]
    formatted_json = from_discussion_to_json(conversation_id, discussion,id_user,id_sector)

    push_request_dynamodb(formatted_json)

    return jsonify({"generated_json": str(formatted_json)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
