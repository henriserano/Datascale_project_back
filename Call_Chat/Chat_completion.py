from flask import Flask, jsonify, request
from mistralai import Mistral
from mistralai.models import UserMessage, AssistantMessage
from dotenv import load_dotenv
import os
import asyncio

# Charger les variables d'environnement
load_dotenv()

# Initialisation de l'application Flask
app = Flask(__name__)

# Charger la clé API
api_key = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=api_key)

# Historique des conversations (à gérer pour chaque session utilisateur)
conversation_histories = {}

@app.route('/', methods=['GET'])
def home():
    """
    Route d'accueil pour vérifier que le serveur fonctionne.
    """
    return jsonify({"message": "Bienvenue sur le serveur Flask pour le chatbot Mistral !"})

@app.route('/api/init_conversation', methods=['POST'])
def init_conversation():
    """
    Initialise une nouvelle conversation pour un utilisateur spécifique.
    """
    data = request.json
    user_id = data.get("user_id")
    titre_secteur = data.get("titre_secteur")
    description_secteur = data.get("description_secteur")

    if not user_id or not titre_secteur or not description_secteur:
        return jsonify({"error": "Tous les champs (user_id, titre_secteur, description_secteur) sont requis."}), 400

    # Message d'introduction
    message_1 = f"""En tant qu'assistant conversationnel du secteur {titre_secteur}, tu représentes et manages le service décrit ci-dessous : 
        {description_secteur}.
        
        Ton objectif principal est d'aider le collaborateur à décrire son problème avec précision... (Instructions détaillées)."""

    # Initialiser l'historique de conversation pour cet utilisateur
    conversation_histories[user_id] = [UserMessage(content=message_1)]

    # Appeler le modèle pour la réponse initiale
    response = asyncio.run(call_llm(conversation_histories[user_id]))

    # Ajouter la réponse de l'assistant à l'historique
    conversation_histories[user_id].append(AssistantMessage(content=response))

    return jsonify({"assistant_response": response})

@app.route('/api/send_message', methods=['POST'])
def send_message():
    """
    Envoie un message utilisateur et obtient une réponse de l'assistant.
    """
    data = request.json
    user_id = data.get("user_id")
    user_message = data.get("message")

    if not user_id or not user_message:
        return jsonify({"error": "Les champs user_id et message sont requis."}), 400

    # Vérifier si l'historique de conversation existe
    if user_id not in conversation_histories:
        return jsonify({"error": "Aucune conversation trouvée pour cet utilisateur. Veuillez initialiser une conversation."}), 404

    # Ajouter le message utilisateur à l'historique
    conversation_histories[user_id].append(UserMessage(content=user_message))

    # Appeler le modèle pour la réponse
    response = asyncio.run(call_llm(conversation_histories[user_id]))

    # Ajouter la réponse de l'assistant à l'historique
    conversation_histories[user_id].append(AssistantMessage(content=response))

    return jsonify({"assistant_response": response})

@app.route('/api/generate_json', methods=['POST'])
def generate_json():
    """
    Génère un fichier JSON à partir de l'historique de conversation.
    """
    data = request.json
    user_id = data.get("user_id")
    agent_id = data.get("agent_id")

    if not user_id or not agent_id:
        return jsonify({"error": "Les champs user_id et agent_id sont requis."}), 400

    # Vérifier si l'historique de conversation existe
    if user_id not in conversation_histories:
        return jsonify({"error": "Aucune conversation trouvée pour cet utilisateur."}), 404

    # Générer le JSON
    discussion = conversation_histories[user_id]
    formatted_json = from_discussion_to_json(agent_id, discussion)

    return jsonify({"generated_json": formatted_json})

async def call_llm(messages):
    """
    Appelle le modèle LLM avec un historique de messages.
    """
    model = "mistral-tiny"
    chat_response = await client.chat.complete_async(
        model=model,
        messages=messages,
    )
    return chat_response.choices[0].message.content

def from_discussion_to_json(agent_id, discussion):
    """
    Génère un JSON structuré à partir de l'historique de conversation.
    """
    prompt_text = f"""En tant qu'assistant conversationnel, ta tâche est d'analyser une discussion donnée afin de générer un fichier JSON... (voir les détails du prompt)."""

    messages = [{
        "role": "user",
        "content": prompt_text + str(discussion),
    }]
    chat_response = client.agents.complete(
        agent_id=agent_id,
        messages=messages,
        response_format={
            "type": "json_object",
        }
    )
    return chat_response.choices[0].message.content

if __name__ == '__main__':
    # Configurer l'hôte et le port selon vos besoins
    app.run(host='0.0.0.0', port=5003, debug=True)
