import requests

BASE_URL = "http://127.0.0.1:5003"

def init_conversation():
    """
    Initialise une nouvelle conversation en appelant l'API /api/init_conversation.
    """
    print("=== Initialisation de la Conversation ===")
    user_id = input("Entrez votre ID utilisateur : ")
    titre_secteur = input("Entrez le titre du secteur : ")
    description_secteur = input("Entrez la description du secteur : ")

    payload = {
        "user_id": user_id,
        "titre_secteur": titre_secteur,
        "description_secteur": description_secteur
    }
    response = requests.post(f"{BASE_URL}/api/init_conversation", json=payload)
    if response.status_code == 200:
        data = response.json()
        print("\nAssistant :", data["assistant_response"])
        return data["conversation_id"]
    else:
        print("\nErreur :", response.json().get("error"))
        return None

def send_message(conversation_id):
    """
    Envoie un message utilisateur et récupère la réponse de l'assistant.
    """
    while True:
        user_message = input("\nVous : ")
        
        if user_message.lower() == "quit":
            print("Fin de la conversation.")
            break

        payload = {
            "conversation_id": conversation_id,
            "message": user_message
        }
        response = requests.post(f"{BASE_URL}/api/send_message", json=payload)
        if response.status_code == 200:
            data = response.json()
            print("Assistant :", data["assistant_response"])
        else:
            print("\nErreur :", response.json().get("error"))

def generate_json(conversation_id):
    """
    Génère un JSON formaté à partir de l'historique de la conversation.
    """
    payload = {
        "conversation_id": conversation_id,
    }
    response = requests.post(f"{BASE_URL}/api/generate_json", json=payload)
    if response.status_code == 200:
        data = response.json()
        print("\n=== JSON Généré ===")
        print(data["generated_json"])
    else:
        print("\nErreur :", response.json().get("error"))

def main():
    """
    Interface principale pour interagir avec l'API depuis la console.
    """
    print("=== Bienvenue sur le Client Console pour le Chatbot Mistral ===")
    print("Options :")
    print("1. Initialiser une conversation")
    print("2. Envoyer un message")
    print("3. Générer un JSON")
    print("4. Quitter")

    conversation_id = None

    while True:
        choice = input("\nEntrez votre choix (1-4) : ")
        if choice == "1":
            conversation_id = init_conversation()
            print(conversation_id)
        elif choice == "2":
            if conversation_id:
                send_message(conversation_id)
            else:
                print("Veuillez d'abord initialiser une conversation (option 1).")
        elif choice == "3":
            if conversation_id:
                generate_json(conversation_id)
            else:
                print("Veuillez d'abord initialiser une conversation (option 1).")
        elif choice == "4":
            print("Au revoir !")
            break
        else:
            print("Choix invalide. Veuillez entrer une option entre 1 et 4.")

if __name__ == "__main__":
    main()
