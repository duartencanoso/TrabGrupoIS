import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify, Response
from flask_socketio import SocketIO
from pymongo import MongoClient
from bson.json_util import dumps
from jsonschema import validate, ValidationError
from jsonpath_ng.ext import parse
import os
import json
from functools import wraps
from jose import jwt
from jose.exceptions import JWTError
import requests
from jose.utils import base64url_decode
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# === Configuração da aplicação ===
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # Habilitar CORS para WebSocket

# === Conexão com MongoDB ===
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client["catalogo"]
colecao = db["produtos"]

# === Carregamento do schema JSON ===
with open("schema.json") as f:
    schema = json.load(f)

# === Configurações do Keycloak ===
KEYCLOAK_REALM = "catalogo-produtos"
KEYCLOAK_URL = "http://192.168.2.122:8080"
KEYCLOAK_ISSUER = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
JWKS_URL = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs"
jwks = requests.get(JWKS_URL).json()

def jwk_to_rsa_key(jwk):
    e = base64url_decode(jwk["e"].encode("utf-8"))
    n = base64url_decode(jwk["n"].encode("utf-8"))
    public_numbers = rsa.RSAPublicNumbers(
        e=int.from_bytes(e, "big"),
        n=int.from_bytes(n, "big")
    )
    return public_numbers.public_key(backend=default_backend())

def validar_token(token):
    try:
        header = jwt.get_unverified_header(token)
        key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
        if not key:
            raise Exception("Chave pública não encontrada")
        rsa_key = jwk_to_rsa_key(key)
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            issuer=KEYCLOAK_ISSUER,
            options={"verify_aud": False}
        )
        return payload
    except JWTError as e:
        print(f"Erro de validação JWT: {e}")
        return None


def login_obrigatorio(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"erro": "Token ausente ou mal formatado"}), 401
        token = auth_header.replace("Bearer ", "")
        payload = validar_token(token)
        if not payload:
            return jsonify({"erro": "Token inválido ou expirado"}), 401
        request.user = payload
        return f(*args, **kwargs)
    return decorated

# === Rotas REST ===

@app.route("/produtos", methods=["GET"])
@login_obrigatorio
def listar_produtos():
    produtos = list(colecao.find({}, {"_id": 0}))
    return Response(dumps(produtos), mimetype="application/json")


@app.route("/produtos/<int:produto_id>", methods=["GET"])
@login_obrigatorio
def obter_produto(produto_id):
    produto = colecao.find_one({"id": produto_id}, {"_id": 0})
    if produto:
        return Response(dumps(produto), mimetype="application/json")
    return jsonify({"erro": "Produto não encontrado"}), 404


@app.route("/produtos", methods=["POST"])
@login_obrigatorio
def adicionar_produto():
    produto = request.get_json()
    try:
        validate(produto, schema)
    except ValidationError as e:
        return jsonify({"erro": "Dados inválidos", "detalhes": e.message}), 400

    if colecao.find_one({"id": produto["id"]}):
        return jsonify({"erro": "Produto com este ID já existe"}), 400

    colecao.insert_one(produto)
    produto_limpo = {k: v for k, v in produto.items() if k != "_id"}
    socketio.emit("novo_produto", produto_limpo)
    return jsonify({"mensagem": "Produto adicionado"}), 201


@app.route("/produtos/<int:produto_id>", methods=["PUT"])
@login_obrigatorio
def atualizar_produto(produto_id):
    novos_dados = request.get_json()
    try:
        validate(novos_dados, schema)
    except ValidationError as e:
        return jsonify({"erro": "Dados inválidos", "detalhes": e.message}), 400

    resultado = colecao.update_one({"id": produto_id}, {"$set": novos_dados})
    if resultado.matched_count == 0:
        return jsonify({"erro": "Produto não encontrado"}), 404

    socketio.emit("produto_editado", novos_dados)
    return jsonify({"mensagem": "Produto atualizado"})


@app.route("/produtos/<int:produto_id>", methods=["DELETE"])
@login_obrigatorio
def remover_produto(produto_id):
    resultado = colecao.delete_one({"id": produto_id})
    if resultado.deleted_count == 0:
        return jsonify({"erro": "Produto não encontrado"}), 404

    socketio.emit("produto_removido", {"id": produto_id})
    return jsonify({"mensagem": "Produto removido"})


@app.route("/exportar", methods=["GET"])
@login_obrigatorio
def exportar_json():
    produtos = list(colecao.find({}, {"_id": 0}))
    return Response(dumps(produtos), mimetype="application/json")


@app.route("/importar", methods=["POST"])
@login_obrigatorio
def importar_json():
    novos_produtos = request.get_json()
    for produto in novos_produtos:
        try:
            validate(produto, schema)
        except ValidationError as e:
            return jsonify({
                "erro": f"Erro ao importar produto ID {produto.get('id')}",
                "detalhes": e.message
            }), 400
    colecao.insert_many(novos_produtos)
    return jsonify({"mensagem": "Importação concluída"})


@app.route("/consulta", methods=["GET"])
@login_obrigatorio
def consulta_jsonpath():
    query = request.args.get("q")
    if not query:
        return jsonify({"erro": "Parâmetro 'q' obrigatório"}), 400

    produtos = list(colecao.find({}, {"_id": 0}))
    try:
        jsonpath_expr = parse(query)
        resultados = [match.value for match in jsonpath_expr.find(produtos)]
        return Response(dumps(resultados), mimetype="application/json")
    except Exception as e:
        return jsonify({
            "erro": "Erro ao processar JSONPath",
            "detalhes": str(e)
        }), 400

# === Eventos WebSocket ===
@socketio.on("connect")
def handle_connect():
    print("Cliente WebSocket conectado!")


@socketio.on("disconnect")
def handle_disconnect():
    print("Cliente WebSocket desconectado!")


# === Inicialização do servidor ===
if __name__ == "__main__":
    print("Servidor REST + WebSocket a correr em http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
