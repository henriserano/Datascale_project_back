from services.extract_text import extract_text_from_bucket_discussion
from services.dynamodb import get_item_dynanodb
from dotenv import load_dotenv
import os
import boto3
import json
import datetime
from mistralai import Mistral

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
api_key = os.getenv("MISTRAL_AI_KEY")
client = Mistral(api_key=api_key)

# Historique des conversations (cache en mémoire)
conversation_histories = {}


def from_discussion_to_json(conversation_id, discussion,id_user,id_sector):
    """
    Génère un JSON structuré à partir de l'historique de conversation.
    """
    sector_data = get_item_dynanodb('Sector', {'ID_Sector': id_sector})["Process_Model"] 
    criteria_selection = json.loads(str(sector_data))["criteria"]    
    text_from_bucket = extract_text_from_bucket_discussion("process-boost",id_user,conversation_id)
    date_today =  datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(date_today)
    summarized_discussion = (
        discussion[:5000] + "..." if len(discussion) > 5000 else discussion
    )
    print(f"Summarized discussion length: {len(summarized_discussion)}")

    # Truncate text from bucket
    truncated_bucket_text = {}
    for key, text in text_from_bucket.items():
        truncated_bucket_text[key] = text[:1000] + "..." if len(text) > 1000 else text
    prompt_text = f"""Votre tâche est d'analyser une discussion donnée ainsi que les documents fournis pour générer un fichier JSON.
Le JSON doit contenir les éléments suivants :

Le nom du service auquel appartient le processus.
Un titre court et explicite qui décrit une analyse du candidat.
Une description détaillée d'une analyse globale de la discussion et des documents, permettant de prendre pleinement conscience de la discussion.
Une analyse des différents critères définis lors de la création du processus métier. Chaque critère doit inclure le nom et le type de source de données (discussion ou document).
Veuillez respecter le format suivant :
{{
"Sector": "",
"Title": "",
"Description": "",
"SubmittedOn": "{date_today}",
"UserID": "{id_user}",
"ID_Conversation": "{conversation_id}",
"name of criteria 1": "",
…,
"name of criteria n": "",
"Statut": "pending"
}}

Voici la discussion que vous devez analyser :
{summarized_discussion}

Détail du contenu des documents fournis par l'utilisateur :
{truncated_bucket_text}

Les critères définis pour l'analyse sont :
{criteria_selection}

Générez le fichier JSON en respectant le format et en remplissant les champs avec les informations pertinentes extraites de la discussion et des documents fournis."""

    messages = [{
        "role": "user",
        "content": prompt_text,
    }]
    chat_response = client.agents.complete(
        agent_id="ag:e559a37b:20241205:generation-json-from-metier:be347c70",
        messages=messages,
        response_format={"type": "json_object"}
    )
    json_data = json.loads(chat_response.choices[0].message.content)
    print("JSON DATA : ",json_data)
    return json_data
