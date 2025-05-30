import grpc
from concurrent import futures
import time
from pymongo import MongoClient
from google.protobuf import empty_pb2
import os
import produtos_pb2
import produtos_pb2_grpc
from jose import jwt
from jose.exceptions import JWTError
from jose.utils import base64url_decode
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import requests

# === MongoDB ===
MONGO_URL = os.getenv("MONGO_URL", "mongodb://192.168.2.110:27017")
client = MongoClient(MONGO_URL)
db = client["catalogo"]
colecao = db["produtos"]

# === Keycloak JWT Config ===
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

def obter_payload_jwt(context):
    metadata = dict(context.invocation_metadata())
    auth = metadata.get("authorization")
    if not auth or not auth.startswith("Bearer "):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token ausente ou mal formatado")
    token = auth.replace("Bearer ", "").strip()
    payload = validar_token(token)
    if not payload:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token inválido ou expirado")
    return payload

class ProdutoService(produtos_pb2_grpc.ProdutoServiceServicer):

    def ListarProdutos(self, request, context):
        obter_payload_jwt(context)  # Verifica token
        resposta = produtos_pb2.ListaProdutos()
        for p in colecao.find({}, {"_id": 0}):
            produto = produtos_pb2.Produto(
                id=p["id"],
                nome=p["nome"],
                marca=p["marca"],
                preco=p["preco"],
                stock=p["stock"],
                tela=p.get("caracteristicas", {}).get("tela", "n/a"),
                bateria=p.get("caracteristicas", {}).get("bateria", "n/a"),
                armazenamento=p.get("caracteristicas", {}).get("armazenamento", "n/a")
            )
            resposta.produtos.append(produto)
        return resposta

    def ListarProdutosStream(self, request, context):
        obter_payload_jwt(context)
        for p in colecao.find({}, {"_id": 0}):
            yield produtos_pb2.Produto(
                id=p["id"],
                nome=p["nome"],
                marca=p["marca"],
                preco=p["preco"],
                stock=p["stock"],
                tela=p.get("caracteristicas", {}).get("tela", "n/a"),
                bateria=p.get("caracteristicas", {}).get("bateria", "n/a"),
                armazenamento=p.get("caracteristicas", {}).get("armazenamento", "n/a")
            )

    def AdicionarProduto(self, request, context):
        payload = obter_payload_jwt(context)
        utilizador = payload.get("preferred_username", "desconhecido")

        if colecao.find_one({"id": request.id}):
            return produtos_pb2.ProdutoResponse(sucesso=False, mensagem="Produto com este ID já existe.")

        produto = {
            "id": request.id,
            "nome": request.nome,
            "marca": request.marca,
            "preco": request.preco,
            "stock": request.stock,
            "caracteristicas": {
                "tela": request.tela,
                "bateria": request.bateria,
                "armazenamento": request.armazenamento
            }
        }
        colecao.insert_one(produto)
        print(f"{utilizador} adicionou o produto {request.nome} via gRPC")
        return produtos_pb2.ProdutoResponse(sucesso=True, mensagem="Produto adicionado com sucesso.")

    def EditarProduto(self, request, context):
        payload = obter_payload_jwt(context)
        utilizador = payload.get("preferred_username", "desconhecido")

        resultado = colecao.update_one(
            {"id": request.id},
            {"$set": {
                "nome": request.nome,
                "marca": request.marca,
                "preco": request.preco,
                "stock": request.stock,
                "caracteristicas": {
                    "tela": request.tela,
                    "bateria": request.bateria,
                    "armazenamento": request.armazenamento
                }
            }}
        )
        if resultado.matched_count == 0:
            return produtos_pb2.ProdutoResponse(sucesso=False, mensagem="Produto não encontrado.")
        print(f"{utilizador} editou o produto {request.id} via gRPC")
        return produtos_pb2.ProdutoResponse(sucesso=True, mensagem="Produto editado com sucesso.")

    def RemoverProduto(self, request, context):
        payload = obter_payload_jwt(context)
        utilizador = payload.get("preferred_username", "desconhecido")

        resultado = colecao.delete_one({"id": request.id})
        if resultado.deleted_count == 0:
            return produtos_pb2.ProdutoResponse(sucesso=False, mensagem="Produto não encontrado.")
        print(f"{utilizador} removeu o produto {request.id} via gRPC")
        return produtos_pb2.ProdutoResponse(sucesso=True, mensagem="Produto removido com sucesso.")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    produtos_pb2_grpc.add_ProdutoServiceServicer_to_server(ProdutoService(), server)
    server.add_insecure_port('[::]:50051')
    print("gRPC server a correr em http://localhost:50051")
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
