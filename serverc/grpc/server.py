import grpc
from concurrent import futures
import time
from pymongo import MongoClient
from google.protobuf import empty_pb2
import os
import produtos_pb2
import produtos_pb2_grpc

# Conexão com MongoDB
MONGO_URL = os.getenv("MONGO_URL", "mongodb://192.168.2.110:27017")
client = MongoClient(MONGO_URL)
db = client["catalogo"]
colecao = db["produtos"]

class ProdutoService(produtos_pb2_grpc.ProdutoServiceServicer):

    def ListarProdutos(self, request, context):
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
        return produtos_pb2.ProdutoResponse(sucesso=True, mensagem="Produto adicionado com sucesso.")

    def EditarProduto(self, request, context):
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
        return produtos_pb2.ProdutoResponse(sucesso=True, mensagem="Produto editado com sucesso.")

    def RemoverProduto(self, request, context):
        resultado = colecao.delete_one({"id": request.id})
        if resultado.deleted_count == 0:
            return produtos_pb2.ProdutoResponse(sucesso=False, mensagem="Produto não encontrado.")
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
