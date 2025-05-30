from spyne import Application, rpc, ServiceBase, Integer, Unicode, Float, Iterable
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne import ComplexModel
from pymongo import MongoClient
import pika
import os
import threading
from jose import jwt
from jose.exceptions import JWTError
from jose.utils import base64url_decode
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import requests

# === Conexão MongoDB ===
MONGO_URL = os.getenv("MONGO_URL", "mongodb://192.168.2.110:27017")  #ip
client = MongoClient(MONGO_URL)
db = client["catalogo"]
colecao = db["produtos"]

# === Configuração RabbitMQ ===
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

def publicar_mensagem(mensagem):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue='produtos_queue', durable=True)
    channel.basic_publish(exchange='', routing_key='produtos_queue', body=mensagem)
    connection.close()

def consumidor():
    def callback(ch, method, properties, body):
        print(f"[x] Mensagem recebida no consumidor: {body.decode()}")

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue='produtos_queue', durable=True)
    channel.basic_consume(queue='produtos_queue', on_message_callback=callback, auto_ack=True)
    print("[*] Consumidor pronto e à escuta...")
    channel.start_consuming()

# Iniciar o consumidor numa thread separada
t = threading.Thread(target=consumidor, daemon=True)
t.start()

# === JWT/Keycloak Config ===
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

# === SOAP ===
class ProdutoSOAP(ComplexModel):
    id = Integer
    nome = Unicode
    marca = Unicode
    preco = Float
    stock = Integer
    tela = Unicode
    bateria = Unicode
    armazenamento = Unicode

class ProdutoService(ServiceBase):

    @rpc(_returns=Iterable(ProdutoSOAP))
    def getProdutos(ctx):
        auth_header = ctx.transport.req_env.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith("Bearer "):
            return []
        token = auth_header.replace("Bearer ", "")
        if not validar_token(token):
            return []

        produtos = []
        for p in colecao.find({}, {"_id": 0}):
            produtos.append(ProdutoSOAP(**p))
        return produtos

    @rpc(Integer, Unicode, Unicode, Float, Integer, Unicode, Unicode, Unicode, _returns=Unicode)
    def addProduto(ctx, id, nome, marca, preco, stock, tela, bateria, armazenamento):
        auth_header = ctx.transport.req_env.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith("Bearer "):
            return "Token ausente ou mal formatado"
        token = auth_header.replace("Bearer", "").strip()
        payload = validar_token(token)
        if not payload:
            return "Token inválido ou expirado"
        utilizador = payload.get("preferred_username", "desconhecido")

        if colecao.find_one({"id": id}):
            return "Produto já existe."

        produto = {
            "id": id,
            "nome": nome,
            "marca": marca,
            "preco": preco,
            "stock": stock,
            "tela": tela,
            "bateria": bateria,
            "armazenamento": armazenamento
        }
        colecao.insert_one(produto)

        publicar_mensagem(f"O utilizador {utilizador} adicionou produto: {nome} ({marca})")

        return "Produto adicionado com sucesso"

    @rpc(Integer, Unicode, Unicode, Float, Integer, Unicode, Unicode, Unicode, _returns=Unicode)
    def editarProduto(ctx, id, nome, marca, preco, stock, tela, bateria, armazenamento):
        auth_header = ctx.transport.req_env.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith("Bearer "):
            return "Token ausente ou mal formatado"
        token = auth_header.replace("Bearer", "").strip()
        payload = validar_token(token)
        if not payload:
            return "Token inválido ou expirado"
        utilizador = payload.get("preferred_username", "desconhecido")

        resultado = colecao.update_one(
            {"id": id},
            {"$set": {
                "nome": nome,
                "marca": marca,
                "preco": preco,
                "stock": stock,
                "tela": tela,
                "bateria": bateria,
                "armazenamento": armazenamento
            }}
        )
        if resultado.matched_count == 0:
            return "Produto não encontrado"

        publicar_mensagem(f"O utilizador {utilizador} atualizou produto: {nome} ({marca})")

        return "Produto atualizado com sucesso"

    @rpc(Integer, _returns=Unicode)
    def deleteProduto(ctx, id):
        auth_header = ctx.transport.req_env.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith("Bearer "):
            return "Token ausente ou mal formatado"
        token = auth_header.replace("Bearer", "").strip()
        payload = validar_token(token)
        if not payload:
            return "Token inválido ou expirado"
        utilizador = payload.get("preferred_username", "desconhecido")

        resultado = colecao.delete_one({"id": id})
        if resultado.deleted_count == 0:
            return "Produto não encontrado"

        publicar_mensagem(f"O utilizador {utilizador} removeu o produto com ID: {id}")

        return "Produto removido"

# === Spyne App ===
app = Application(
    [ProdutoService],
    tns="catalogo.eletronica.soap",
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    print("SOAP server a correr em http://localhost:8000")
    wsgi_app = WsgiApplication(app)
    server = make_server("0.0.0.0", 8000, wsgi_app)
    server.serve_forever()
