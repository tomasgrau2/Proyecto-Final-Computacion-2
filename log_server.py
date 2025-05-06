import threading
import logging
import logging.handlers
import queue 
import signal
import sys
import time
from multiprocessing.managers import BaseManager
from multiprocessing import Queue as MpQueue # Usar la cola de multiprocessing para IPC

LOG_ADDRESS = ('localhost', 50000) # Dirección para el manager de la cola
LOG_AUTHKEY = b'miClaveSecretaParaLogs' # Clave de autenticación
LOG_FILENAME = 'combined_server.log'

# Cola compartida entre procesos
shared_log_queue = MpQueue()

# ---- Configuración del Manager para exponer la cola ----
class QueueManager(BaseManager):
    pass

QueueManager.register('get_log_queue', callable=lambda: shared_log_queue)

# ---- Configuración del Logging ----
log_formatter = logging.Formatter('%(asctime)s [%(processName)s/%(process)d] [%(levelname)s] %(name)s: %(message)s')

# Handler para escribir en el archivo
file_handler = logging.FileHandler(LOG_FILENAME, mode='a')
file_handler.setFormatter(log_formatter)

# Handler para mostrar logs en la consola del listener (opcional)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

# QueueListener toma los logs de la cola local y los pasa a los handlers
# Nota: Usamos queue.Queue normal aquí, NO la de multiprocessing directamente
# QueueHandler en el servidor pondrá en MpQueue, y aquí transferimos a queue.Queue
# Esto es más robusto y desacoplado.
local_log_queue = queue.Queue()
listener = logging.handlers.QueueListener(local_log_queue, file_handler, console_handler, respect_handler_level=True)

stop_event = False # Flag para detener el listener y el manager

def signal_handler(signum, frame):
    global stop_event
    print(f"\nSeñal {signal.Signals(signum).name} recibida. Deteniendo listener...")
    stop_event = True

def process_log_queue(mp_queue: MpQueue, local_queue: queue.Queue):
    """
    Proceso que lee de la cola de multiprocessing y pone en la cola local.
    """
    logging.info("Procesador de cola de logs iniciado.")
    while not stop_event:
        try:
            record = mp_queue.get(block=True, timeout=0.5) # Espera corta para poder chequear stop_event
            if record is None: # Señal para detenerse (opcional)
                print("Señal de parada recibida en la cola de logs.")
                break
            local_queue.put(record)
        except queue.Empty:
            continue # Seguir esperando si la cola está vacía
        except Exception as e:
            print(f"Error procesando cola de logs: {e}", file=sys.stderr)
            time.sleep(1) # Evitar spam si hay un error persistente
    print("Procesador de cola de logs detenido.")
    local_queue.put(None) # Señalizar al QueueListener que termine


def main():
    global stop_event
    # Configurar el logger raíz para capturar mensajes del listener mismo (opcional)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Asegurarse de no duplicar handlers si se corre varias veces en un entorno interactivo
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
         root_logger.addHandler(console_handler)

    print(f"Iniciando Log Manager en {LOG_ADDRESS}")
    manager = QueueManager(address=LOG_ADDRESS, authkey=LOG_AUTHKEY)
    server = manager.get_server()

    print(f"Iniciando Log Listener para escribir en '{LOG_FILENAME}'")
    listener.start()
    print("Log Listener iniciado.")

    # Iniciar el servidor del manager en un hilo para que no bloquee
    manager_thread = threading.Thread(target=server.serve_forever, daemon=True)
    manager_thread.start()
    print("Log Manager escuchando...")

    # Iniciar el proceso que mueve logs de la MpQueue a la cola local
    log_processor_thread = threading.Thread(target=process_log_queue, args=(shared_log_queue, local_log_queue), daemon=True)
    log_processor_thread.start()

    # Configurar manejadores de señales para detenerse limpiamente
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Listener listo. Esperando logs... (Presiona Ctrl+C para detener)")
    # Mantener el proceso principal vivo hasta que se reciba una señal
    while not stop_event:
        time.sleep(0.5)

    # --- Proceso de apagado ---
    print("Deteniendo Log Manager...")
    print("Deteniendo procesador de cola de logs...")
    # El flag stop_event debería detener el bucle de process_log_queue
    log_processor_thread.join(timeout=2) # Esperar un poco a que termine

    print("Deteniendo Log Listener...")
    listener.stop() # Esto esperará a que la cola local se vacíe
    print("Log Listener detenido.")
    print("Apagado completo.")

if __name__ == "__main__":
    main()