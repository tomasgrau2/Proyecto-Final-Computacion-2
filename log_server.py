import threading
import logging
import os
import signal
import sys
import queue
from multiprocessing.managers import BaseManager
from multiprocessing import Queue as MpQueue
from dotenv import load_dotenv

load_dotenv()

LOG_ADDRESS = (os.getenv('LOG_ADDRESS_HOST'),int(os.getenv('LOG_ADDRESS_PORT')))
LOG_AUTHKEY = os.getenv('LOG_AUTHKEY')
LOG_AUTHKEY = LOG_AUTHKEY.encode('utf-8')
LOG_FILENAME = 'combined_server.log'

# Cola compartida entre procesos - usamos solo una cola de multiprocessing
shared_log_queue = MpQueue()

# ---- Configuración del Manager para exponer la cola ----
class QueueManager(BaseManager):
    pass

QueueManager.register('get_log_queue', callable=lambda: shared_log_queue)

# ---- Configuración del Logging ----
log_formatter = logging.Formatter('%(asctime)s [%(processName)s/%(process)d] [%(levelname)s] %(name)s: %(message)s')

# Handler para escribir en el archivo
file_handler = logging.FileHandler(LOG_FILENAME, mode='w')
file_handler.setFormatter(log_formatter)

# Handler para mostrar logs en la consola del listener
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

stop_event = False  # Flag para detener el listener y el manager

def signal_handler(signum, frame):
    global stop_event
    print(f"\nSeñal {signal.Signals(signum).name} recibida. Deteniendo servidor de logs...")
    stop_event = True


def main():
    global stop_event
    # Configurar el logger raíz para capturar mensajes del listener mismo
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Asegurarse de no duplicar handlers
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(console_handler)
    if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        root_logger.addHandler(file_handler)

    print(f"Iniciando Log Manager en {LOG_ADDRESS}")
    manager = QueueManager(address=LOG_ADDRESS, authkey=LOG_AUTHKEY)
    server = manager.get_server()

    # Configurar manejadores de señales para detenerse limpiamente
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"Procesador de logs configurado para escribir en '{LOG_FILENAME}'")
    print("Log Manager iniciando...")
    
    # Iniciar el servidor del manager
    manager_thread = threading.Thread(target=server.serve_forever, daemon=True)
    manager_thread.start()
    print("Log Manager escuchando...")

    print("Servidor de logs listo. Procesando logs... (Presiona Ctrl+C para detener)")
    
    # El thread principal procesa los logs directamente - no necesitamos otro thread
    while not stop_event:
        try:
            # Timeout corto para poder chequear stop_event regularmente
            record = shared_log_queue.get(block=True, timeout=0.5)
            
            if record is None:  # Señal para detenerse (opcional)
                print("Señal de parada recibida en la cola de logs.")
                break
                
            # Procesar el registro directamente con el logger raíz
            root_logger.handle(record)
            
        except queue.Empty:
            # Ignorar excepciones de timeout (cola vacía)
            pass
        except Exception as e:
            print(f"Error procesando cola de logs: {e}", file=sys.stderr)

    # --- Proceso de apagado ---
    print("Deteniendo Log Manager...")
    print("Apagado completo.")

if __name__ == "__main__":
    main()