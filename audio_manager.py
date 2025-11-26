import pyaudio
import wave
import threading
import os
import time
from playsound import playsound

# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 512

class AudioManager:
    def __init__(self, master=None):
        """Inicializa el gestor de audio.

        master: referencia al cliente GUI (puede ser None en pruebas)
        download_folder: carpeta donde se guardan archivos temporales
        """
        self.master = master
        self.folder_sent = "audios_enviados"
        self.folder_received = "audios_recibidos"

        # PyAudio
        self.p = pyaudio.PyAudio()

        # Estado de grabación
        self.recording = False
        self.audio_frames = []
        self.stream = None
        self.recording_thread = None

    def _get_temp_filename(self, username):
        return f"audio_{username}_{int(time.time())}.wav" #Returna un nombre de archivo temporal único
    
    def start_recording(self):
        if self.recording:
            if self.master:
                self.master._log_local("Ya está grabando!\n")
            return

        # Reiniciar buffer
        self.audio_frames = []

        # Abrir stream de entrada
        try:
            self.stream = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        except Exception as e:
            if self.master:
                self.master._log_local(f"[ERROR] No se pudo abrir el micrófono: {e}\n")
            return

        self.recording = True
        # iniciar stream de grabación en un hilo separado
        self.recording_thread = threading.Thread(target=self._record, daemon=True)
        self.recording_thread.start()

        if self.master:
            try:
                self.master._log_local("Grabando audio...\n")
                self.master.master.after(0, self.master.actualizar_botones_audio, True)
            except Exception:
                pass

    def _record(self):
        while self.recording:
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                self.audio_frames.append(data)
            except Exception:
                # Ignorar errores menores de overflow
                pass

        try:
            if self.stream is not None:
                self.stream.stop_stream()
                self.stream.close()
        except Exception:
            pass

    def stop_recording(self, destino, sender_username, send_frame_func, log_local_func):
        if not self.recording:
            log_local_func("No está grabando!\n")
            return

        self.recording = False
        if self.recording_thread:
            self.recording_thread.join()
        log_local_func("[PROCESANDO] Guardando y enviando nota de voz...\n")

        hilo_envio = threading.Thread(
            target=self._hilo_guardar_enviar,
            args=(destino, sender_username, send_frame_func, log_local_func),
            daemon=True,
        )
        hilo_envio.start()

        if self.master:
            try:
                self.master.master.after(0, self.master.actualizar_botones_audio, False)
            except Exception:
                pass

    def _hilo_guardar_enviar (self, destino, sender_username, send_frame_func, log_local_func): #Guarda el audio y lo envía
        nombre_archivo = self._get_temp_filename(sender_username)
        ruta_temporal = os.path.join(self.folder_sent, nombre_archivo)

        # Guardar el archivo WAV
        try:
            if len(self.audio_frames) < 5:
                log_local_func("[ERROR] La grabación fue demasiado corta o falló. No se enviará audio.\n")
                return
            os.makedirs(self.folder_sent, exist_ok=True)
            with wave.open(ruta_temporal, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.p.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(self.audio_frames))
            tam = os.path.getsize(ruta_temporal)
            if tam < 1000:
                log_local_func("[ERROR] El archivo de audio puede estar corrupto. No se enviará audio.\n")
                return
        except Exception as e:
            log_local_func(f"[ERROR] Fallo al guardar audio: {e}\n")
            return
        finally:
            # Limpiar buffer local
            self.audio_frames = []

        # Enviar como frame con tipo "audio"
        try:
            tam = os.path.getsize(ruta_temporal)

            header = {
                "type": "audio",
                "from": sender_username,
                "to": destino,
                "filename": nombre_archivo,
                "filesize": tam,
            }

            with open(ruta_temporal, "rb") as f:
                datos = f.read()

            send_frame_func(header, datos)
            log_local_func(f"[AUDIO] Yo -> {destino}: '{nombre_archivo}' ({tam} bytes)\n")

        except Exception as e:
            log_local_func(f"[ERROR] No se pudo enviar el audio: {e}\n")

    def reproducir_audio(self, ruta_audio, log_local_func):
        """Inicia la reproducción de un archivo WAV en un nuevo hilo."""
        hilo = threading.Thread(target=self._hilo_reproductor, args=(ruta_audio, log_local_func), daemon=True)
        hilo.start()
    
    def _hilo_reproductor(self, ruta_audio, log_local_func):
        """Ejecuta la reproducción real del archivo WAV."""
        try:
            if not os.path.exists(ruta_audio):
                raise FileNotFoundError(f"archivo no encontrado: {ruta_audio}")
            with wave.open(ruta_audio, 'rb') as wf:
                
                # Abrir stream de reproducción
                stream = self.p.open(format=self.p.get_format_from_width(wf.getsampwidth()),
                                     channels=wf.getnchannels(),
                                     rate=wf.getframerate(),
                                     output=True)

                data = wf.readframes(CHUNK)
                while data:
                    stream.write(data)
                    data = wf.readframes(CHUNK)

                stream.stop_stream()
                stream.close()
                log_local_func(f"[AUDIO] Reproducción de '{os.path.basename(ruta_audio)}' finalizada.\n")

        except Exception as e:
            # Intentar fallback con playsound si PyAudio falla
            log_local_func(f"[WARN] Reproducción con PyAudio falló: {e}. Intentando fallback...\n")
            try:
                playsound(ruta_audio)
                log_local_func(f"[AUDIO] Reproducción (fallback) de '{os.path.basename(ruta_audio)}' finalizada.\n")
            except Exception as e2:
                log_local_func(f"[ERROR] Fallo al reproducir audio '{os.path.basename(ruta_audio)}' (playsound): {e2}\n")

    def terminate(self):
        try:
            self.p.terminate()
        except Exception:
            pass