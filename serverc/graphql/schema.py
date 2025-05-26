import graphene
from pymongo import MongoClient
from jsonschema import validate, ValidationError
import json
import os

# === MongoDB Connection ===
MONGO_URL = os.getenv("MONGO_URL", "mongodb://192.168.2.110:27017")
client = MongoClient(MONGO_URL)
db = client["catalogo"]
colecao = db["produtos"]

# === JSON Schema ===
with open("schema.json") as f:
    schema_json = json.load(f)

# === GraphQL Tipos ===
class CaracteristicasType(graphene.ObjectType):
    tela = graphene.String()
    bateria = graphene.String()
    armazenamento = graphene.String()

class ProdutoType(graphene.ObjectType):
    id = graphene.Int()
    nome = graphene.String()
    marca = graphene.String()
    preco = graphene.Float()
    stock = graphene.Int()
    caracteristicas = graphene.Field(CaracteristicasType)

class Query(graphene.ObjectType):
    produtos = graphene.List(ProdutoType)

    def resolve_produtos(root, info):
        return list(colecao.find({}, {"_id": 0}))

# === Mutations ===

class AdicionarProduto(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        nome = graphene.String(required=True)
        marca = graphene.String(required=True)
        preco = graphene.Float(required=True)
        stock = graphene.Int(required=True)
        tela = graphene.String(required=True)
        bateria = graphene.String(required=True)
        armazenamento = graphene.String(required=True)

    ok = graphene.Boolean()
    mensagem = graphene.String()

    def mutate(self, info, id, nome, marca, preco, stock, tela, bateria, armazenamento):
        produto = {
            "id": id,
            "nome": nome,
            "marca": marca,
            "preco": preco,
            "stock": stock,
            "caracteristicas": {
                "tela": tela,
                "bateria": bateria,
                "armazenamento": armazenamento
            }
        }

        try:
            validate(produto, schema_json)
        except ValidationError as e:
            return AdicionarProduto(ok=False, mensagem=f"Erro: {e.message}")

        if colecao.find_one({"id": id}):
            return AdicionarProduto(ok=False, mensagem="ID já existe.")

        colecao.insert_one(produto)
        return AdicionarProduto(ok=True, mensagem="Produto adicionado com sucesso")

class EditarProduto(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        nome = graphene.String(required=True)
        marca = graphene.String(required=True)
        preco = graphene.Float(required=True)
        stock = graphene.Int(required=True)
        tela = graphene.String(required=True)
        bateria = graphene.String(required=True)
        armazenamento = graphene.String(required=True)

    ok = graphene.Boolean()
    mensagem = graphene.String()

    def mutate(self, info, id, nome, marca, preco, stock, tela, bateria, armazenamento):
        produto = {
            "id": id,
            "nome": nome,
            "marca": marca,
            "preco": preco,
            "stock": stock,
            "caracteristicas": {
                "tela": tela,
                "bateria": bateria,
                "armazenamento": armazenamento
            }
        }

        try:
            validate(produto, schema_json)
        except ValidationError as e:
            return EditarProduto(ok=False, mensagem=f"Erro: {e.message}")

        resultado = colecao.update_one({"id": id}, {"$set": produto})
        if resultado.matched_count == 0:
            return EditarProduto(ok=False, mensagem="Produto não encontrado.")

        return EditarProduto(ok=True, mensagem="Produto atualizado com sucesso")

class RemoverProduto(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    ok = graphene.Boolean()
    mensagem = graphene.String()

    def mutate(self, info, id):
        resultado = colecao.delete_one({"id": id})
        if resultado.deleted_count == 0:
            return RemoverProduto(ok=False, mensagem="Produto não encontrado.")
        return RemoverProduto(ok=True, mensagem="Produto removido com sucesso")

# === Schema ===
class Mutation(graphene.ObjectType):
    adicionar_produto = AdicionarProduto.Field()
    editar_produto = EditarProduto.Field()
    remover_produto = RemoverProduto.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)
