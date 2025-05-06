import asyncio
import signal

# Conjunto para almacenar usuarios activos
usuarios_activos:dict = {}

async def handle_auth(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    print(f"Conexión de autenticación desde: {addr}")
    
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
                
            comando = data.decode().strip()
            parts = comando.split(":",2)
            pid = parts[1]
            username = parts[2]
            if comando.startswith("AUTH:"):
                # Formato: AUTH:pid:username
                print(pid)
                print(username)
                # Si la address no esta en el dict, crear address y agregar usuario
                if pid not in usuarios_activos:
                    usuarios_activos[pid]=[username]
                    writer.write(b"OK\n")
                else:
                    if username in usuarios_activos[pid]:
                        writer.write(b"NO\n")
                    else:
                        usuarios_activos[pid].append(username)
                        writer.write(b"OK\n")
                print(usuarios_activos)        
            elif comando.startswith("LOGOUT:"):
                # Formato: LOGOUT:username
                if username in usuarios_activos[pid]:
                    usuarios_activos[pid].remove(username)
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