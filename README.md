````markdown
# SuperVillanoChat
Chat grupal
--------------------
## Usuario ---> Funcionalidad
```
Pedro -----> Chat grupal ✅
Pedro -----> Sonido por mensaje ✅ REQUIRES pip install playsound==1.2.2
Pedro -----> Imagenes in-chat ✅ REQUIRES pip install Pillow
Cesar -----> Enviar audios ✅ REQUIRES pip install PyAudio (Windows) sudo apt-get install portaudio19-dev , pip install PyAudio (Ubuntu/Debian)
Cesar -----> Integracion de emojis ✅
Jorge -----> Mostrar la hora en cada mensaje 
Lenin -----> Integración de audio con Linux ✅
Lenin -----> Ventana emergente con la barra de progreso al enviar archivos ✅
Emiliano -----> Color aleatorio a cada nombre de usuario ✅
Emiliano -----> Buscador de mensajes ✅
Villa -----> Actualizacion de Readme y adicion del requirements.txt ✅
```

**Instrucciones de ejecución**

- **Requisitos:** Python 3.12.x instalado en el sistema.
- **Crear entorno virtual:**
  - PowerShell / Windows:
    - `python -m venv .venv`
  - (alternativa) Bash / WSL / macOS:
    - `python3 -m venv .venv`
- **Activar el entorno virtual:**
  - PowerShell (tu shell por defecto):
    - `.\.venv\Scripts\Activate.ps1`
  - CMD (Windows):
    - `.venv\Scripts\activate`
  - Bash / WSL / macOS:
    - `source .venv/bin/activate`
- **Instalar dependencias:**
  - `pip install -r requirements.txt`
- **Ejecutar la aplicación:**
  - Iniciar el servidor (en una terminal):
    - `python chat_server.py`
  - Iniciar el cliente GUI (en otra terminal):
    - `python chat_client_gui.py`
- **Salir / desactivar el venv:**
  - `deactivate`

````
