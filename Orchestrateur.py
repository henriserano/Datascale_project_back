from flask import Flask, request, jsonify
import requests
import threading

app = Flask(__name__)

# Exemple de services simulés (vous pouvez les remplacer par des vrais appels API)
SERVICES = {
    "service_1": "http://localhost:5001/api/service_1",
    "service_2": "http://localhost:5002/api/service_2",
    "service_3": "http://localhost:5003/api/service_3"
}

def call_service(url, payload, responses, service_name):
    """
    Effectue une requête POST à un service donné et enregistre la réponse.
    """
    try:
        response = requests.post(url, json=payload)
        responses[service_name] = response.json()
    except Exception as e:
        responses[service_name] = {"error": str(e)}

@app.route('/orchestrate', methods=['POST'])
def orchestrate():
    """
    Orchestration des appels à différents services.
    """
    data = request.json
    if not data or "payload" not in data:
        return jsonify({"error": "Le champ 'payload' est requis"}), 400

    payload = data["payload"]
    responses = {}
    threads = []

    # Appels parallèles à tous les services
    for service_name, service_url in SERVICES.items():
        thread = threading.Thread(target=call_service, args=(service_url, payload, responses, service_name))
        threads.append(thread)
        thread.start()

    # Attendre la fin de tous les threads
    for thread in threads:
        thread.join()

    return jsonify(responses)

@app.route('/health', methods=['GET'])
def health_check():
    """
    Vérification de l'état de santé de l'orchestrateur.
    """
    return jsonify({"status": "ok", "message": "Orchestrator is running"})

if __name__ == '__main__':
    # Lancer l'application Flask
    app.run(host='0.0.0.0', port=5000, debug=True)
