import json
import pandas as pd

# Charger les données du fichier Excel
base_train = pd.read_excel("BPMN_TRAIN.xlsx")

# Vérifier le contenu du DataFrame
if base_train.empty:
    print("Le fichier Excel est vide ou n'a pas été chargé correctement.")
    exit()

# Vérifier si les colonnes nécessaires sont présentes
required_columns = ["input", "output"]
if not all(col in base_train.columns for col in required_columns):
    print(f"Le fichier Excel doit contenir les colonnes suivantes : {', '.join(required_columns)}")
    exit()

# Liste pour stocker les conversations
conversations = []

# Parcourir chaque ligne du DataFrame pour construire les prompts
for _, row in base_train.iterrows():
    user_input = row.get("input", "").strip()
    assistant_output = row.get("output", "").strip()

    if user_input and assistant_output:
        # Créer une conversation avec un échange utilisateur-assistant
        conversation = {
            "messages": [
                {
                    "role": "user",
                    "content": user_input
                },
                {
                    "role": "assistant",
                    "content": assistant_output
                }
            ]
        }
        # Ajouter la conversation à la liste
        conversations.append(conversation)

# Vérifier s'il y a des données valides avant d'écrire le fichier
if not conversations:
    print("Aucune donnée valide trouvée dans le fichier Excel.")
    exit()

# Nom du fichier de sortie
output_file = 'BPMN.jsonl'

# Écrire les conversations dans un fichier JSONL
try:
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for convo in conversations:
            json.dump(convo, outfile, ensure_ascii=False)
            outfile.write('\n')
    print(f"Le fichier JSONL a été créé avec succès : {output_file}")
except Exception as e:
    print(f"Une erreur s'est produite lors de la création du fichier JSONL : {e}")