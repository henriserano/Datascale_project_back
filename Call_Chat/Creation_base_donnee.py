import json
import pandas as pd
base_train = pd.read_excel("back//Call_Chat//Base_creation_json.xlsx")
base_train
conversations = []

# Parcourir chaque ligne du DataFrame
for _, row in base_train.iterrows():
    # Créer une conversation avec un échange utilisateur-assistant
    conversation = {
        "messages": [
            {
                "role": "user",
                "content": row["input"]
            },
            {
                "role": "assistant",
                "content": row["output"]
            }
        ]
    }
    # Ajouter la conversation à la liste
    conversations.append(conversation)

# Écrire les conversations dans un fichier JSONL
output_file = 'back//Call_Chat//Creation_json.jsonl'
with open(output_file, 'w', encoding='utf-8') as outfile:
    for convo in conversations:
        json.dump(convo, outfile, ensure_ascii=False)
        outfile.write('\n')

print(f"Le fichier JSONL a été créé : {output_file}")