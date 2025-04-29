import asyncio
import signal

PALABRAS_INADECUADAS = {
    "mala", "groseria", "insulto", "palabra1", "palabra2", "palabra3"
}

def filtrar_mensaje(mensaje: str) -> str:
    """
    Filtra el mensaje reemplazando palabras inadecuadas con asteriscos.
    """
    palabras = mensaje.split()
    resultado = []
    for palabra in palabras:
        if palabra.lower() in PALABRAS_INADECUADAS:
            resultado.append("*" * len(palabra))
        else:
            resultado.append(palabra)
    return " ".join(resultado)

async def handle_filter(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    print(f"Conexión de filtrado desde: {addr}")
    
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
                
            mensaje = data.decode().strip()
            mensaje_filtrado = filtrar_mensaje(mensaje)
            
            # Enviamos el mensaje filtrado de vuelta
            writer.write(f"{mensaje_filtrado}\n".encode())
            await writer.drain()
            
    except Exception as e:
        print(f"Error en la conexión de filtrado: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

async def shutdown(server: asyncio.Server):
    print(f"\n🛑 Iniciando apagado del servidor de filtrado")
    
    # Cerrar el servidor
    server.close()
    await server.wait_closed()
    
    print("✅ Servidor de filtrado apagado correctamente")

async def main():
    server = await asyncio.start_server(handle_filter, '127.0.0.1', 9010)
    print("Servidor de filtrado escuchando en 127.0.0.1:9010")
    
    # Configurar el manejador de señales
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(server)))
    
    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass  

if __name__ == "__main__":
    asyncio.run(main()) 