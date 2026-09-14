from pathlib import Path

from dotenv import load_dotenv

# O CWD primeiro (o CI gera o .env.test no diretorio de trabalho do pytest) e
# depois o arquivo versionado, ancorado no caminho DESTE modulo -- caminho
# relativo resolve contra o CWD, entao `load_dotenv(".env.test")` sozinho nao
# carrega nada quando o pytest roda de services/api, e a suite acaba caindo no
# .env de desenvolvimento que Settings encontra subindo os diretorios.
TEST_ENV_FILE = Path(__file__).resolve().parent / ".env.test"

load_dotenv(".env.test")
load_dotenv(TEST_ENV_FILE)
