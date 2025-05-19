import socket
import asyncio
import argparse
import signal
import logging 
import os
import logging.handlers 
from multiprocessing.managers import BaseManager 
from dotenv import load_dotenv

load_dotenv()

# ---- Configuración de Logging Remoto ----
LOG_ADDRESS = (os.getenv('LOG_ADDRESS_HOST'),int(os.getenv('LOG_ADDRESS_PORT')))
print(LOG_ADDRESS)
LOG_AUTHKEY = os.getenv('LOG_AUTHKEY')
LOG_AUTHKEY = LOG_AUTHKEY.encode('utf-8')
print(LOG_AUTHKEY)

class QueueManager(BaseManager):
    pass

QueueManager.register('get_log_queue')

log_queue = None
try:
    manager = QueueManager(address=LOG_ADDRESS, authkey=LOG_AUTHKEY)
    manager.connect()
    log_queue = manager.get_log_queue()
    print(f"✅ Conectado al servidor de logs en {LOG_ADDRESS}")
except Exception as e:
    print(f"❌ Error al conectar con el servidor de logs: {e}. Se usarán logs locales (consola).")
    log_queue = None # Fallback a no usar la cola si falla la conexión

# Configurar el logger principal de esta instancia del servidor
logger = logging.getLogger('ChatServer') 
logger.setLevel(logging.INFO) # O logging.DEBUG si args.debug
formatter = logging.Formatter('%(asctime)s [%(processName)s/%(process)d] [%(levelname)s] %(name)s: %(message)s') # Mismo formato que el listener

if log_queue:
    # Si nos conectamos al manager, usamos QueueHandler
    queue_handler = logging.handlers.QueueHandler(log_queue)
    logger.addHandler(queue_handler)
else:
    # Si no, usamos un handler de consola como fallback
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Lista global de clientes conectados
clientes = set()

async def filtrar_mensaje(mensaje: str) -> str:
    """
    Envía el mensaje al servidor de filtrado y devuelve el mensaje filtrado.
    """
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 9010)
        writer.write(f"{mensaje}\n".encode())
        await writer.drain()
        mensaje_filtrado = await reader.readline()
        writer.close()
        await writer.wait_closed()
        return mensaje_filtrado.decode().strip()
    except ConnectionRefusedError:
        logger.error("No se pudo conectar con el servidor de filtrado. Los mensajes no serán filtrados.") 
        return mensaje
    except Exception as e:
        logger.exception(f"Error en el filtrado de mensaje")
        return mensaje

async def autenticar_usuario(username: str) -> bool:
    ### TO-DO: pasar la direccion del server para poder tener los mismos nombres de usuarios en servers distintos
    try:
        logger.debug(f'{os.getpid()}')
        reader, writer = await asyncio.open_connection(os.getenv('AUTH_ADDRESS_HOST'), int(os.getenv('AUTH_ADDRESS_PORT')))
        # Uso el pid como identificador de cada sala de chat
        writer.write(f"AUTH:{os.getpid()}:{username}\n".encode())
        await writer.drain()
        respuesta = await reader.readline()
        writer.close()
        await writer.wait_closed()
        return respuesta.decode().strip() == "OK"
    except ConnectionRefusedError:
        raise # Re-lanzamos la excepción para manejarla en handle_client
    except Exception as e:
        logger.exception(f"Error en autenticación para usuario '{username}'") 
        return False

async def logout_usuario(username: str):
    try:
        reader, writer = await asyncio.open_connection(os.getenv('AUTH_ADDRESS_HOST'), int(os.getenv('AUTH_ADDRESS_PORT')))
        writer.write(f"LOGOUT:{os.getpid()}:{username}\n".encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        logger.info(f"Logout enviado al servidor de autenticación para '{username}'") 
    except ConnectionRefusedError:
        logger.error("No se pudo conectar con el servidor de autenticación para cerrar sesión.") 
    except Exception as e:
        logger.exception(f"Error en logout para usuario '{username}'") 

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    logger.info(f"Cliente conectado: {addr}") 

    # Solicitar nombre de usuario
    writer.write(b"Ingrese su nombre de usuario: ")
    await writer.drain()

    data = await reader.readline()
    if not data:
        writer.close()
        await writer.wait_closed()
        logger.warning(f"Cliente {addr} desconectado antes de enviar usuario.") 
        return

    try:
        username = data.decode().strip()
    except UnicodeDecodeError:
        writer.close()
        await writer.wait_closed()
        logger.warning(f"Datos inválidos (no UTF-8) recibidos - Desconectando.") 
        return
    if not username:
        writer.write(b"Nombre de usuario vacio no permitido. Conexion cerrada.\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        logger.warning(f"Cliente {addr} intentó usar nombre de usuario vacío.") 
        return

    # Autenticar usuario
    try:
        if not await autenticar_usuario(username):
            logger.warning(f"Autenticación fallida para '{username}' desde {addr}. Nombre en uso.") 
            writer.write(b"Nombre de usuario en uso. Conexion cerrada.\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return
    except ConnectionRefusedError:
        logger.error("El servidor de autenticación no está disponible. Rechazando conexión.") 
        writer.write(b"El servidor de autenticacion no esta disponible en este momento. Por favor, intente mas tarde.\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return
    except Exception: # Captura cualquier otra excepción durante la autenticación
        logger.exception(f"Error inesperado durante la autenticación de '{username}' desde {addr}.")
        writer.write(b"Error interno durante la autenticacion. Conexion cerrada.\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    logger.info(f"Usuario autenticado: '{username}' desde {addr}") 
    clientes.add(writer)

    try:
        while True:
            data = await reader.readline()
            if not data:
                logger.info(f"Cliente '{username}' {addr} cerró la conexión (EOF).") 
                break # El cliente cerró la conexión

            try:
                mensaje = data.decode().strip()
                if not mensaje: # Ignorar líneas vacías
                    continue

                # Verificar si el cliente quiere desconectarse
                if mensaje.lower() == "/exit":
                    logger.info(f"Cliente '{username}' {addr} se desconectó usando el comando /exit") 
                    break

                # Filtrar el mensaje
                mensaje_filtrado = await filtrar_mensaje(mensaje)

                logger.info(f"Mensaje de '{username}' [{addr}]: {mensaje_filtrado}") 

                # Reenviar mensaje filtrado a todos los demás clientes
                for cliente in clientes:
                    if cliente != writer:
                        cliente.write(f"[{username}] {mensaje_filtrado}\n".encode())
                        await cliente.drain()

            except UnicodeDecodeError:
                logger.warning(f"Datos inválidos (no UTF-8) recibidos de '{username}' {addr} - Desconectando.") 
                break
            except Exception:
                logger.exception(f"Error inesperado manejando mensaje de '{username}' {addr}.")  
                break # Desconectar en caso de error grave

    except asyncio.IncompleteReadError:
        logger.warning(f"Lectura incompleta desde '{username}' {addr}. Probable desconexión abrupta.") 
    except Exception as e:
        logger.exception(f"Error en el bucle principal de manejo para '{username}' {addr}.") 
    finally:
        logger.info(f"Cliente desconectado: '{username}' {addr}") 
        clientes.remove(writer)
        # Intentar cerrar sesión en el servidor de autenticación
        # Usar create_task para no bloquear el cierre si el servidor no responde rápido
        asyncio.create_task(logout_usuario(username))
        if not writer.is_closing():
             try:
                 writer.close()
                 await writer.wait_closed()
             except Exception as e_close:
                 logger.warning(f"Error al cerrar writer para '{username}': {e_close}")


async def shutdown(servidor_ipv6: asyncio.Server, servidor_ipv4: asyncio.Server):
    logger.info("Iniciando apagado del servidor de chat...") 

    # Cerrar todas las conexiones de clientes
    # Crear tasks para cerrar clientes concurrentemente
    close_tasks = []
    for cliente in list(clientes): # Iterar sobre una copia
        if not cliente.is_closing():
            cliente.close()
            close_tasks.append(asyncio.create_task(cliente.wait_closed()))

    if close_tasks:
        logger.info(f"Cerrando {len(close_tasks)} conexiones de clientes...")
        await asyncio.gather(*close_tasks, return_exceptions=True) # Esperar a que se cierren
        logger.info("Conexiones de clientes cerradas.")
    else:
        logger.info("No hay clientes conectados para cerrar.")

    # Cerrar los servidores
    logger.info("Cerrando sockets del servidor...")
    servidor_ipv6.close()
    servidor_ipv4.close()
    await servidor_ipv6.wait_closed()
    await servidor_ipv4.wait_closed()
    logger.info("Servidor de chat apagado correctamente.") 


async def start_server(args):
    # Configurar nivel de log según argumento --debug
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.info("Modo DEBUG activado.")
    else:
        logger.setLevel(logging.INFO)

    servidor_ipv6 = await asyncio.start_server(handle_client, args.host, args.port, family=socket.AF_INET6)
    servidor_ipv4 = await asyncio.start_server(handle_client, '0.0.0.0', args.port, family=socket.AF_INET) # Escuchar explícitamente en IPv4 también
    addr_ipv6 = servidor_ipv6.sockets[0].getsockname()
    addr_ipv4 = servidor_ipv4.sockets[0].getsockname()
    logger.debug(f"{addr_ipv4}")
    logger.info(f"Servidor escuchando en IPv6 [{addr_ipv6[0]}]:{addr_ipv6[1]} y IPv4 {addr_ipv4[0]}:{addr_ipv4[1]}") 

    # Configurar el manejador de señales
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(servidor_ipv6, servidor_ipv4)))

    try:
        # Ejecutar ambos servidores concurrentemente
        await asyncio.gather(
            servidor_ipv6.serve_forever(),
            servidor_ipv4.serve_forever()
        )
    except asyncio.CancelledError:
        pass
   
async def main():
    parser = argparse.ArgumentParser(description="Servidor de Chat Async con Logging Centralizado") 
    parser.add_argument('-p', '--port', type=int, default=8888,
                        help='Puerto para el servidor de chat (default: 8888)')
    parser.add_argument('-H', '--host', default='::',
                        help='Dirección de host IPv6 para escuchar (default: "::", escucha en todas las interfaces IPv6)')
    parser.add_argument('-d','--debug', action='store_true',
                        help='Activar modo debug con mensajes detallados')
    args = parser.parse_args()

    await start_server(args)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # Capturar cualquier error fatal durante el inicio/ejecución de asyncio.run
        logging.critical(f"Error fatal no manejado: {e}", exc_info=True)