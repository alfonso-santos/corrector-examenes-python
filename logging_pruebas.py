import logging
import os

directorio_raiz = "/workspace"
dir_log = os.path.join(directorio_raiz, "logs")

# Crear el directorio si no existe
if not os.path.exists(dir_log):
    os.makedirs(dir_log)

log_file = os.path.join(dir_log, 'evaluacion.log')

logger = logging.getLogger(__name__)
# Configurar el logging para registrar errores tanto en consola como en el archivo de log
logging.basicConfig(filename=log_file, level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
# Registrar un mensaje de log
logging.error("Logging configurado correctamente. Comenzando la ejecución del script.")