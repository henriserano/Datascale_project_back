import os
import asyncio
from mistralai import Mistral
from mistralai.models import UserMessage, AssistantMessage
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("MISTRAL_AI_KEY")
# Initialiser le client Mistral
client = Mistral(api_key=api_key)
# Initialiser l'historique de conversation
conversation_history = []

async def call_LLM(messages):
    """
    Appelle le modèle LLM avec un historique de messages.
    """
    # Nom du modèle utilisé
    model = "mistral-tiny"


    # Appel au modèle avec l'historique de messages
    chat_response = await client.chat.complete_async(
        model=model,
        messages=messages,
    )

    # Récupérer et afficher la réponse
    response = chat_response.choices[0].message.content
    print("\nAgent Mistral:\n", response)
    return response

def add_to_history(user_message, assistant_response):
    """
    Ajoute un message utilisateur et une réponse de l'assistant à l'historique.
    """
    conversation_history.append(AssistantMessage(content=assistant_response))

def from_discussion_to_json(agent_id,discussion):
    """Fonction qui permet de générer un json à partir d'une discussion

    Args:
        agent_id (_type_): _description_
        prompt_text (_type_): _description_
    """
    prompt_text = """En tant qu'assistant conversationnel, ta tâche est d'analyser une discussion donnée afin de générer un fichier JSON qui communique clairement une problématique client.

    Le JSON doit inclure les éléments suivants :
    1. Le nom du service auquel appartient la problématique.
    2. Un titre court et explicite de la problématique du collaborateur.
    3. Une description détaillée du problème.
    4. Un niveau d'urgence entre 1 et 5, 1 étant peu urgent et 5 étant très urgent.

    Voici le format du JSON à respecter :
    "
    {
        ‘Nom Service’ : ‘’,
        ‘Titre’:’’,
        ‘Description’:’’,
        ‘Niveau d’urgence’: ‘’,
        ‘Date’ : ‘’,
        ‘Nom utilisateur’ : ‘’,
        ‘Statut’ : ‘pending’
    }
    "

    Exemple de discussion :
    """    +str(discussion)
    messages = [{
                "role": "user",
                "content": prompt_text,
            }]
    chat_response = client.agents.complete(
        agent_id=agent_id,
        messages=messages,
        response_format = {
          "type": "json_object",
      }
    )
    return chat_response.choices[0].message.content
    
    
async def main(titre_secteur,description_secteur):
    """
    Boucle principale pour interagir avec l'utilisateur et appeler le LLM.
    """
    print("Welcome to the Mistral Sector Insights Agent! Type 'exit' to quit.\n")
    global conversation_history
    message_1 = f"""En tant qu'assistant conversationnel du secteur {titre_secteur}, tu représentes et manages le service décrit ci-dessous : 
        {description_secteur}.

        Ton objectif principal est d'aider le collaborateur à décrire son problème avec précision en suivant les instructions ci-dessous :
        1. Saluer le collaborateur en répondant "Bienvenue sur le services {titre_secteur}, que puis-je faire pour vous aider ?".
        2. Poser des questions pour identifier et clarifier le problème du collaborateur.
        3. Après 2-3 messages ou lorsque tu penses avoir compris le problème, définir et formuler le titre et la description du problème.
        4. Informer le collaborateur qu'il peut envoyer sa demande en indiquant "si vous vous sentez prêt pour envoyer votre demande envoyé 'send' dans le chat de la conversation".

        Exemple :
        Collaborateur : "J'ai un souci avec la connexion internet dans mon bureau."
        Assistant : "Pouvez-vous me dire depuis quand vous rencontrez ce problème ?"
        Collaborateur : "Cela fait environ trois jours."
        Assistant : "Merci pour l'information. Pouvez-vous préciser si d'autres services sont également impactés ?"
        Collaborateur : "Non, uniquement la connexion internet."
        Assistant : "D'accord. Voici ce que j'ai compris :
        Titre : Problème de connexion internet au bureau
        Description : La connexion internet dans le bureau est instable depuis trois jours. Aucun autre service n'est impacté.
        Si vous vous sentez prêt pour envoyer votre demande envoyé 'send' dans le chat de la conversation."

        Utilise ce format pour guider chaque conversation et assure-toi d'informer le collaborateur de l'option d'envoyer leur demande lorsqu'ils sont prêts."""
    conversation_history.append(UserMessage(content=message_1))

    # Appeler le modèle avec l'historique
    assistant_response = await call_LLM(conversation_history)
    while True:
        # Demander à l'utilisateur une entrée
        user_message = input("You: ")
        if user_message.lower() == 'send':
            print(from_discussion_to_json("ag:e559a37b:20241205:generation-json-from-metier:be347c70",conversation_history))
            
            break

        # Ajouter le message utilisateur à l'historique
        conversation_history.append(UserMessage(content=user_message))

        # Appeler le modèle avec l'historique
        assistant_response = await call_LLM(conversation_history)

        # Ajouter la réponse de l'assistant à l'historique
        add_to_history(user_message, assistant_response)

if __name__ == "__main__":
    titre_secteur = "Quality Control"  
    description = "Quality assurance and product testing"
    asyncio.run(main(titre_secteur,description))
