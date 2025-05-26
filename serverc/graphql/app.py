from flask import Flask, request, jsonify
from flask_graphql import GraphQLView
from schema import schema

app = Flask(__name__)

app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view(
        "graphql",
        schema=schema,
        graphiql=True
    )
)

if __name__ == "__main__":
    print("GraphQL server a correr em http://localhost:5001/graphql")
    
    # Porta 5001
    app.run(host="0.0.0.0", port=5001, debug=True)
