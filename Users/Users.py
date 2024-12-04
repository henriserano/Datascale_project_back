from flask import Flask, jsonify, request

# Initialisation de l'application Flask
app = Flask(__name__)

# Route d'accueil (GET)
@app.route('/', methods=['GET'])
def home():
    """
    Route d'accueil pour vérifier que le serveur fonctionne.
    """
    return jsonify({"message": "Bienvenue sur le serveur Flask !"})

# Exemple d'API (GET)
@app.route('/api/data', methods=['GET'])
def get_data():
    """
    Exemple de route pour renvoyer des données JSON.
    """
    data = {
        "name": "Flask Server",
        "version": "1.0",
        "status": "running"
    }
    return jsonify(data)

# Exemple d'API (POST)
@app.route('/api/echo', methods=['POST'])
def echo_data():
    """
    Exemple de route pour recevoir et renvoyer des données envoyées par POST.
    """
    content = request.json  # Récupération des données JSON envoyées
    return jsonify({"received_data": content})

# Lancer le serveur
if __name__ == '__main__':
    # Configurer l'hôte et le port selon vos besoins
    app.run(host='0.0.0.0', port=5001, debug=True)
