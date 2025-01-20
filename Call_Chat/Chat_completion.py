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

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# Charger la clé API
api_key = os.getenv("MISTRAL_AI_KEY")
client = Mistral(api_key=api_key)

# Historique des conversations (cache en mémoire)
conversation_histories = {}
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
        "assistant_response": response
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

def call_llm(messages):
    """
    Appelle le modèle LLM en mode synchrone.
    """
    model = "mistral-tiny"
    chat_response = client.chat.complete(
        model=model,
        messages=messages,
    )
    return chat_response.choices[0].message.content

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
