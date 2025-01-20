from openai import OpenAI
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)

# Charger les variables d'environnement
load_dotenv()
AWS_KEY = os.getenv("AWS_ID")
AWS_SECRET = os.getenv("AWS_Secret")
REGION_NAME = os.getenv("Region")
api_key = os.getenv("CHATGPT_KEY")
assistant_id = os.getenv("ASSISTANT_ID")

session = boto3.Session(
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    region_name=REGION_NAME,
)
dynamodb = session.resource("dynamodb")
table = dynamodb.Table("Sector")

client = OpenAI(api_key=api_key)

def get_sector_info(id_sector):
    """
    Récupère les informations d'un secteur dans DynamoDB.
    """
    table_sector = dynamodb.Table('Sector')
    response = table_sector.get_item(Key={'ID_Sector': str(id_sector)})
    return response.get('Item', {})

def update_or_create_dynamodb(bpmn_generate, id_sector):
    """
    Met à jour ou ajoute la variable dans un objet DynamoDB.
    """
    try:
        # Met à jour ou ajoute le champ BPMN dans l'objet correspondant à l'ID_Sector
        table.update_item(
            Key={"ID_Sector": id_sector},
            UpdateExpression="SET BPMN = :bpmn_generate",
            ExpressionAttributeValues={":bpmn_generate": bpmn_generate},
            ReturnValues="UPDATED_NEW"
        )
        print("Process BPMN mis à jour avec succès dans DynamoDB.")
    except ClientError as e:
        print("Erreur lors de la mise à jour sur DynamoDB:", e)
        raise
    except Exception as e:
        print("Erreur inattendue:", e)
        raise

@app.route('/bpmn', methods=['POST'])
def open_ai_bpmn():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Bad Request", "message": 'Expected a JSON object with a "text" key.'}), 400

        
        sector_id = data["sector_id"]
        data_secteur = get_sector_info(sector_id) 

        
        
        titre_process = data_secteur.get("Secteur", "Titre non défini")
        description_process = data_secteur.get("Description", "Description non définie")
        
        
        if "description" in data and "titre" in data:
            description_process = data["description"]
            titre_process = data["titre"]
        prompt = f"""Titre : {titre_process}
        Description : {description_process}"""
        
        
        thread = client.beta.threads.create()
        message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt
        )
        response = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant_id,
        instructions=prompt
        )
        messages = client.beta.threads.messages.list(
                thread_id=thread.id
        )

        res_ai =  messages.data[0].content[0].text.value
        
        # ------------------- PUSH DU PROCESSUS METIER DANS DYNAMODB -------------------

        update_or_create_dynamodb(res_ai, sector_id)

        return jsonify({"status": "success", "message": res_ai}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    


@app.route('/', methods=['GET'])
def test_endpoint():
    """Test simple pour valider le bon fonctionnement de l'API."""
    return jsonify({"status": "success", "message": "Test successful!"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)