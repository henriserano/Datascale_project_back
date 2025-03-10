from mistralai import Mistral
from dotenv import load_dotenv
import os

# Charger les variables d'environnement
load_dotenv()

# Charger la clé API
api_key = os.getenv("MISTRAL_AI_KEY")
client = Mistral(api_key=api_key)


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