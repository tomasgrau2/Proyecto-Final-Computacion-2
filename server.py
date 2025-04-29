import asyncio
import argparse
import signal

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
        print("❌ Error: No se pudo conectar con el servidor de filtrado. Los mensajes no serán filtrados.")
        return mensaje
    except Exception as e:
        print(f"Error en el filtrado de mensaje: {e}")
        return mensaje

async def autenticar_usuario(username: str) -> bool:
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 9000)
        writer.write(f"AUTH:{username}\n".encode())
        await writer.drain()
        respuesta = await reader.readline()
        writer.close()
        await writer.wait_closed()
        return respuesta.decode().strip() == "OK"
    except ConnectionRefusedError:
        raise  # Re-lanzamos la excepción para manejarla en handle_client
    except Exception as e:
        print(f"Error en autenticación: {e}")
        return False

async def logout_usuario(username: str):
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 9000)
        writer.write(f"LOGOUT:{username}\n".encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    except ConnectionRefusedError:
        print("❌ Error: No se pudo conectar con el servidor de autenticación para cerrar sesión.")
    except Exception as e:
        print(f"Error en logout: {e}")

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    print(f"Cliente conectado: {addr}")
    
    # Solicitar nombre de usuario
    writer.write(b"Ingrese su nombre de usuario: ")
    await writer.drain()
    
    data = await reader.readline()
    if not data:
        writer.close()
        await writer.wait_closed()
        return
        
    username = data.decode().strip()
    
    # Autenticar usuario
    try:
        if not await autenticar_usuario(username):
            writer.write(b"Nombre de usuario en uso. Conexion cerrada.\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return
    except ConnectionRefusedError:
        writer.write(b"El servidor de autenticacion no esta disponible en este momento. Por favor, intente mas tarde.\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return
    
    print(f"Usuario autenticado: {username}")
    clientes.add(writer)
    
    try:
        while True:
            data = await reader.readline()
            if not data:
                break  # El cliente cerró la conexión

            try:
                mensaje = data.decode().strip()
                
                # Verificar si el cliente quiere desconectarse
                if mensaje.lower() == "/exit":
                    print(f"Cliente {username} se desconectó usando el comando /exit")
                    break
                
                # Filtrar el mensaje
                mensaje_filtrado = await filtrar_mensaje(mensaje)
                
                print(f"📨 Mensaje de {username}: {mensaje_filtrado}")

                # Reenviar mensaje filtrado a todos los demás clientes
                for cliente in clientes:
                    if cliente != writer:
                        cliente.write(f"[{username}] {mensaje_filtrado}\n".encode())
                        await cliente.drain()
            except UnicodeDecodeError:
                print(f"⚠️ Datos inválidos recibidos de {username} - Cliente desconectado abruptamente")
                break
    except asyncio.IncompleteReadError:
        pass
    finally:
        print(f"Cliente desconectado: {username}")
        clientes.remove(writer)
        await logout_usuario(username)
        writer.close()
        await writer.wait_closed()

async def shutdown(servidor_ipv6: asyncio.Server, servidor_ipv4: asyncio.Server):
    print(f"\n🛑 Iniciando apagado del servidor")
    
    # Cerrar todas las conexiones de clientes
    for cliente in clientes.copy():
        cliente.close()
        await cliente.wait_closed()
    
    # Cerrar los servidores
    servidor_ipv6.close()
    servidor_ipv4.close()
    await servidor_ipv6.wait_closed()
    await servidor_ipv4.wait_closed()
    print("✅ Servidor apagado correctamente")

async def start_server(args):
    servidor_ipv6 = await asyncio.start_server(handle_client, '::', args.port)
    servidor_ipv4 = await asyncio.start_server(handle_client, '0.0.0.0', args.port)
    print(f"Servidor escuchando en IPv6 (::) y IPv4 (0.0.0.0) en el puerto {args.port}")
    
    # Configurar el manejador de señales
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(servidor_ipv6, servidor_ipv4)))
    
    try:
        async with servidor_ipv6, servidor_ipv4:
            await asyncio.gather(
                servidor_ipv6.serve_forever(),
                servidor_ipv4.serve_forever()
            )
    except asyncio.CancelledError:
        pass  # Ya no necesitamos llamar a shutdown aquí

async def main():
    parser = argparse.ArgumentParser(prog="Chat Server")
    parser.add_argument('-p', '--port', type=int, default=8888,
                        help='Puerto para el servidor de chat (default: 8888)')
    parser.add_argument('-H', '--host', default='::',
                        help='Dirección de host para el servidor (default: "::")')
    parser.add_argument('--debug', action='store_true',
                        help='Activar modo debug con mensajes detallados')
    args = parser.parse_args()

    await start_server(args)

if __name__ == "__main__":
    # Ejecutar el servidor
    asyncio.run(main())