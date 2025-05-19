# 🧑‍💻 Sala de Chat Asíncrona (IPv4 + IPv6) - Proyecto Final Computación2

Este proyecto es una sala de chat implementada en Python como parte del trabajo final para la asignatura **Computación 2**. El objetivo principal es permitir que múltiples clientes, conectados utilizando **IPv4 o IPv6**, puedan comunicarse de forma simultánea a varios servidores programados usando `asyncio`, con autenticación de usuarios y un servidor central de logs para todas las salas.

---

## 📌 Características

- ✅ Soporte de conexiones **IPv4 e IPv6**.
- ✅ Programación **asíncrona** con `asyncio`.
- ✅ Manejo de múltiples clientes.
- ✅ Difusión de mensajes entre clientes conectados.
- ✅ Configuración del servidor por línea de comandos.
- ✅ Autenticación de usuarios.
- ✅ Servidor central de logs.

---

## 🧠 Arquitectura

![Arquitectura del chat](computacion2.png)

## 🚀 Cómo ejecutar el servidor

1. **Cloná el repositorio:**

   ```bash
   git clone https://github.com/tomasgrau2/Proyecto-Final-Computacion-2.git
   cd Proyecto-Final-Computacion-2

2. **Crear entorno virtual e instalar dependencias:** 

   ```bash
   $ python -m venv .
   $ source bin/activate
   $ pip install -r requirements.txt

3. **Configurar variables de entorno:**

   ```bash
   $ touch .env
   Una vez creado el archivo ".env" agregar las variables de entorno: 
   # Direccion del servidor de logs
   LOG_ADDRESS_HOST
   LOG_ADDRESS_PORT
   # Clave de autenticación --> necesaria! 
   LOG_AUTHKEY 
   # Path donde se guardará el archivo de logs 
   LOG_FILENAME
   # Dirección del servidor de autenticación de usuarios
   AUTH_ADDRESS_HOST
   AUTH_ADDRESS_PORT
   
4. **Ejecutar servidores:**  

```bash
   $ python log_server.py
   $ python auth_server.py
   $ python server.py