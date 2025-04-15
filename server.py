import asyncio
import argparse
import socket

# Lista global de clientes conectados
clientes = set()

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    print(f"Cliente conectado: {addr}")
    clientes.add(writer)

    try:
        while True:
            data = await reader.readline()
            if not data:
                break  # El cliente cerró la conexión

            mensaje = data.decode().strip()
            print(f"📨 Mensaje de {addr}: {mensaje}")

            # Reenviar mensaje a todos los demás clientes
            for cliente in clientes:
                if cliente != writer:
                    cliente.write(f"[{addr}] {mensaje}\n".encode())
                    await cliente.drain()
    except asyncio.IncompleteReadError:
        pass
    finally:
        print(f"Cliente desconectado: {addr}")
        clientes.remove(writer)
        writer.close()
        await writer.wait_closed()

async def start_server(args):
    servidor_ipv6 = await asyncio.start_server(handle_client, '::', args.port)
    servidor_ipv4 = await asyncio.start_server(handle_client, '0.0.0.0', args.port)
    print(f"Servidor escuchando en IPv6 (::) y IPv4 (0.0.0.0) en el puerto {args.port}")
    
    async with servidor_ipv6, servidor_ipv4:
        await asyncio.gather(
            servidor_ipv6.serve_forever(),
            servidor_ipv4.serve_forever()
        )

async def main():
    parser = argparse.ArgumentParser(prog="Chat Server")
    parser.add_argument('-p', '--port', type=int, default=8888,
                        help='Puerto para el servidor de chat (default: 8888)')
    parser.add_argument('-H', '--host', default='::',
                        help='Dirección de host para el servidor (default: "::")')
    ### Usar logger para debug
    parser.add_argument('--debug', action='store_true',
                        help='Activar modo debug con mensajes detallados')
    args = parser.parse_args()

    await start_server(args)

    

# Ejecutar el servidor
asyncio.run(main())