from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson.json_util import dumps
from jsonschema import validate, ValidationError
from jsonpath_ng.ext import parse
from collections import OrderedDict
import os
import json

app = Flask(__name__)

# === Conexão MongoDB ===
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client["catalogo"]
colecao = db["produtos"]

# === JSON Schema ===
with open("schema.json") as f:
    schema = json.load(f)

# === CRUD ===

@app.route("/produtos", methods=["GET"])
def listar_produtos():
    produtos = list(colecao.find({}, {"_id": 0}))
    return jsonify(produtos)

@app.route("/produtos/<int:produto_id>", methods=["GET"])
def obter_produto(produto_id):
    produto = colecao.find_one({"id": produto_id}, {"_id": 0})
    if produto:
        return jsonify(produto)
    return jsonify({"erro": "Produto não encontrado"}), 404

@app.route("/produtos", methods=["POST"])
def adicionar_produto():
    produto = request.get_json()
    try:
        validate(produto, schema)
    except ValidationError as e:
        return jsonify({"erro": "Dados inválidos", "detalhes": e.message}), 400

    if colecao.find_one({"id": produto["id"]}):
        return jsonify({"erro": "Produto com este ID já existe"}), 400

    colecao.insert_one(produto)
    return jsonify({"mensagem": "Produto adicionado"}), 201

@app.route("/produtos/<int:produto_id>", methods=["PUT"])
def atualizar_produto(produto_id):
    novos_dados = request.get_json()
    try:
        validate(novos_dados, schema)
    except ValidationError as e:
        return jsonify({"erro": "Dados inválidos", "detalhes": e.message}), 400

    resultado = colecao.update_one({"id": produto_id}, {"$set": novos_dados})
    if resultado.matched_count == 0:
        return jsonify({"erro": "Produto não encontrado"}), 404
    return jsonify({"mensagem": "Produto atualizado"})

@app.route("/produtos/<int:produto_id>", methods=["DELETE"])
def remover_produto(produto_id):
    resultado = colecao.delete_one({"id": produto_id})
    if resultado.deleted_count == 0:
        return jsonify({"erro": "Produto não encontrado"}), 404
    return jsonify({"mensagem": "Produto removido"})

# === Exportar / Importar ===

@app.route("/exportar", methods=["GET"])
def exportar_json():
    produtos = list(colecao.find({}, {"_id": 0}))
    return jsonify(produtos)

@app.route("/importar", methods=["POST"])
def importar_json():
    novos_produtos = request.get_json()
    for produto in novos_produtos:
        try:
            validate(produto, schema)
        except ValidationError as e:
            return jsonify({"erro": f"Erro ao importar produto ID {produto.get('id')}", "detalhes": e.message}), 400
    colecao.insert_many(novos_produtos)
    return jsonify({"mensagem": "Importação concluída"})

# === Consulta JSONPath ===

@app.route("/consulta", methods=["GET"])
def consulta_jsonpath():
    query = request.args.get("q")
    if not query:
        return jsonify({"erro": "Parâmetro 'q' obrigatório"}), 400

    produtos = list(colecao.find({}, {"_id": 0}))
    try:
        jsonpath_expr = parse(query)
        resultados = [match.value for match in jsonpath_expr.find(produtos)]
        return jsonify(resultados)
    except Exception as e:
        return jsonify({"erro": "Erro ao processar JSONPath", "detalhes": str(e)}), 400

# === Iniciar servidor ===

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
