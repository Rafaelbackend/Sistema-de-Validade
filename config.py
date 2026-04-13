db_config = {
    "dbname": "Estoque_Mercado",
    "user": "postgres",
    "Password": "postgres",
    "host": "localhost",
    "port": 5432
}
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}
