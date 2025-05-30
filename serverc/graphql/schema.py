import graphene
from pymongo import MongoClient
from jsonschema import validate, ValidationError
import json
import os
from jose import jwt
from jose.exceptions import JWTError
from jose.utils import base64url_decode
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import requests

# === MongoDB Connection ===
MONGO_URL = os.getenv("MONGO_URL", "mongodb://192.168.2.110:27017")
client = MongoClient(MONGO_URL)
db = client["catalogo"]
colecao = db["produtos"]

# === JSON Schema ===
with open("schema.json") as f:
    schema_json = json.load(f)

# === Keycloak Config ===
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
        print(f"[JWT inválido] {e}")
        return None

def extrair_token(info):
    auth = info.context.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth.replace("Bearer ", "")
    return validar_token(token)

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
        payload = extrair_token(info)
        if not payload:
            raise Exception("Token inválido ou ausente")
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
        payload = extrair_token(info)
        if not payload:
            return AdicionarProduto(ok=False, mensagem="Token inválido ou ausente")

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
        payload = extrair_token(info)
        if not payload:
            return EditarProduto(ok=False, mensagem="Token inválido ou ausente")

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
        payload = extrair_token(info)
        if not payload:
            return RemoverProduto(ok=False, mensagem="Token inválido ou ausente")

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
