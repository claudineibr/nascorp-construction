from pathlib import Path

from dotenv import load_dotenv

# O CWD primeiro (o CI gera o .env.test no diretorio de trabalho do pytest) e
# depois o arquivo local, ancorado no caminho DESTE modulo. Ele NAO vai para o
# repositorio: e uma credencial de banco, e cada ambiente tem a sua -- copie de
# .env.test.example. Sem ele os testes de integracao pulam, que e o que deve
# acontecer. Caminho
# relativo resolve contra o CWD, entao `load_dotenv(".env.test")` sozinho nao
# carrega nada quando o pytest roda de services/api, e a suite acaba caindo no
# .env de desenvolvimento que Settings encontra subindo os diretorios.
TEST_ENV_FILE = Path(__file__).resolve().parent / ".env.test"

load_dotenv(".env.test")
load_dotenv(TEST_ENV_FILE)
