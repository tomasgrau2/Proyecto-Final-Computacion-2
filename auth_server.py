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

async def main():
    server = await asyncio.start_server(handle_auth, '127.0.0.1', 9000)
    print("Servidor de autenticación escuchando en 127.0.0.1:9000")
    
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main()) 