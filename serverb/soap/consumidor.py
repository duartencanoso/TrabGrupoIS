import pika

# --- Configuração do RabbitMQ ---
RABBITMQ_HOST = "192.168.2.111"  # IP Server RabbitMQ

def callback(ch, method, properties, body):
    print(f"[x] Mensagem recebida: {body.decode()}")

def main():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()

    # Garantir que a queue existe
    channel.queue_declare(queue="produtos_queue", durable=True)
    print("[*] Consumidor pronto. À escuta...")

    channel.basic_consume(queue="produtos_queue", on_message_callback=callback, auto_ack=True)
    channel.start_consuming()

if __name__ == "__main__":
    main()
