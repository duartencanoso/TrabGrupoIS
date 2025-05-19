from spyne import Application, rpc, ServiceBase, Integer, Unicode, Float, Iterable
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne import ComplexModel
from pymongo import MongoClient
import os

# === Conexão MongoDB ===
MONGO_URL = os.getenv("MONGO_URL", "mongodb://192.168.2.110:27017")  #ip
client = MongoClient(MONGO_URL)
db = client["catalogo"]
colecao = db["produtos"]

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
        produtos = []
        for p in colecao.find({}, {"_id": 0}):
            produtos.append(ProdutoSOAP(**p))
        return produtos

    @rpc(Integer, Unicode, Unicode, Float, Integer, Unicode, Unicode, Unicode, _returns=Unicode)
    def addProduto(ctx, id, nome, marca, preco, stock, tela, bateria, armazenamento):
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
        return "Produto adicionado com sucesso"

    @rpc(Integer, Unicode, Unicode, Float, Integer, Unicode, Unicode, Unicode, _returns=Unicode)
    def editarProduto(ctx, id, nome, marca, preco, stock, tela, bateria, armazenamento):
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
        return "Produto atualizado com sucesso"

    @rpc(Integer, _returns=Unicode)
    def deleteProduto(ctx, id):
        resultado = colecao.delete_one({"id": id})
        if resultado.deleted_count == 0:
            return "Produto não encontrado"
        return "Produto removido"

# Spyne App
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
