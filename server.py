import asyncio
import argparse
import signal

# Lista global de clientes conectados
clientes = set()
# Variable para controlar el estado del servidor
servidor_activo = True

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    print(f"Cliente conectado: {addr}")
    clientes.add(writer)

    try:
        while servidor_activo:
            data = await reader.readline()
            if not data:
                break  # El cliente cerró la conexión

            try:
                mensaje = data.decode().strip()
                
                # Verificar si el cliente quiere desconectarse
                if mensaje.lower() == "/exit":
                    print(f"Cliente {addr} se desconectó usando el comando /exit")
                    break
                
                print(f"📨 Mensaje de {addr}: {mensaje}")

                # Reenviar mensaje a todos los demás clientes
                for cliente in clientes:
                    if cliente != writer:
                        cliente.write(f"[{addr}] {mensaje}\n".encode())
                        await cliente.drain()
            except UnicodeDecodeError:
                print(f"⚠️ Datos inválidos recibidos de {addr} - Cliente desconectado abruptamente")
                break
    except asyncio.IncompleteReadError:
        pass
    finally:
        print(f"Cliente desconectado: {addr}")
        clientes.remove(writer)
        writer.close()
        await writer.wait_closed()

async def shutdown(servidor_ipv6: asyncio.Server, servidor_ipv4: asyncio.Server):
    global servidor_activo
    if not servidor_activo:
        return  # Evitar apagado múltiple
    print(f"\n🛑 Iniciando apagado del servidor")
    servidor_activo = False
    
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