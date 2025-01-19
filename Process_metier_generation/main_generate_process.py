import pandas as pd
import json
import requests
import os
import flask


app = flask.Flask(__name__)

@app.route('/api/v1/health', methods=['GET'])
def health():
    return 'Healthy'

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/generate_bpmn', methods=['POST'])
def generate_bpmn():
    # Récupération des données envoyées via la requête POST
    data = request.json

    process_name = data.get('name')
    process_description = data.get('description')
    kpis = data.get('kpis', [])
    documents = data.get('documents', [])
    steps = data.get('steps', [])

    # Ajout de champs supplémentaires pour chaque étape
    for i, step in enumerate(steps):
        step["nextStep"] = steps[i + 1]["name"] if i + 1 < len(steps) else None
        step["roles"] = step.get("roles", [])

    # Construction du JSON BPMN
    bpmn_json = {
        "process": {
            "name": process_name,
            "description": process_description,
            "KPI": kpis,
            "Documents": documents,
            "Etape_Workflow": steps
        }
    }

    # Retour du JSON généré
    return jsonify(bpmn_json)

if __name__ == '__main__':
    # Exemple de données de test
    test_data = {
        "name": "Processus de gestion des commandes",
        "description": "Ce processus permet de gérer les commandes clients",
        "kpis": ["KPI1", "KPI2"],
        "documents": ["Doc1", "Doc2"],
        "steps": [
            {
                "name": "Recupération des documents",
                "description": "Description de l'étape 1",
                "Type": "INPUT",
                "roles": ["Admin"]
            },
            {
                "name": "Vérification des documents",
                "description": "Description de l'étape 2",
                "Type": "XOR",
                "roles": ["Manager"]
            },
            {
                "name": "Validation finale",
                "description": "Description de l'étape 3",
                "Type": "END",
                "roles": ["Supervisor"]
            }
        ]
    }

    # Test local de l'API
    with app.test_client() as c:
        rv = c.post('/generate_bpmn', json=test_data)
        print("Test JSON généré :", rv.get_json())  # Affiche le JSON BPMN généré pour vérification

    # Lancement du serveur Flask
    app.run(debug=True)