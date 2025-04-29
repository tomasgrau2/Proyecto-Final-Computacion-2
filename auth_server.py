import asyncio
import signal

# Conjunto para almacenar usuarios activos
usuarios_activos = set()

async def handle_auth(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    print(f"Conexión de autenticación desde: {addr}")
    
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
                
            comando = data.decode().strip()
            if comando.startswith("AUTH:"):
                # Formato: AUTH:username
                username = comando[5:]
                if username in usuarios_activos:
                    writer.write(b"NO\n")
                else:
                    usuarios_activos.add(username)
                    writer.write(b"OK\n")
            elif comando.startswith("LOGOUT:"):
                # Formato: LOGOUT:username
                username = comando[7:]
                if username in usuarios_activos:
                    usuarios_activos.remove(username)
                    writer.write(b"OK\n")
                else:
                    writer.write(b"NO\n")
            elif comando == "LIST":
                # Listar usuarios activos
                lista = ",".join(usuarios_activos)
                writer.write(f"{lista}\n".encode())
            else:
                writer.write(b"ERROR: Comando no reconocido\n")
            
            await writer.drain()
            
    except Exception as e:
        print(f"Error en la conexión de autenticación: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

async def shutdown(server: asyncio.Server):
    print(f"\n🛑 Iniciando apagado del servidor de autenticación")
    
    # Cerrar el servidor
    server.close()
    await server.wait_closed()
    
    # Limpiar usuarios activos
    usuarios_activos.clear()
    
    print("✅ Servidor de autenticación apagado correctamente")

async def main():
    server = await asyncio.start_server(handle_auth, '127.0.0.1', 9000)
    print("Servidor de autenticación escuchando en 127.0.0.1:9000")
    
    # Configurar el manejador de señales
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(server)))
    
    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass  # Ya no necesitamos llamar a shutdown aquí

if __name__ == "__main__":
    asyncio.run(main()) 