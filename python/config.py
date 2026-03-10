"""Load configuration from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "localpulse")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "localpulse")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "localpulse")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
