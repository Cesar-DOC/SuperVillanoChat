import os
import threading
import time
import wave

import numpy as np
import sounddevice as sd

# Parámetros de audio
CHANNELS = 1
RATE = 44100
CHUNK = 512
FORMAT_BYTES = 2  # 16 bits = 2 bytes por muestra


class AudioManager:
    def __init__(self, master=None):
        self.master = master

        self.folder_sent = "audios_enviados"
        self.folder_received = "audios_recibidos"

        self.recording = False
        self.audio_buffer = []
        self.recording_thread = None

    def _get_temp_filename(self, username):
        return f"audio_{username}_{int(time.time())}.wav"

    # -----------------------
    # GRABACIÓN
    # -----------------------

    def start_recording(self):
        if self.recording:
            if self.master:
                self.master._log_local("Ya está grabando!\n")
            return

        self.audio_buffer = []
        self.recording = True

        # Hilo de captura
        self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.recording_thread.start()

        if self.master:
            self.master._log_local("Grabando audio...\n")
            self.master.master.after(0, self.master.actualizar_botones_audio, True)

    def _record_loop(self):
        """Captura audio en CHUNKS usando sounddevice."""
        try:
            with sd.InputStream(
                channels=CHANNELS,
                samplerate=RATE,
                blocksize=CHUNK,
                dtype="int16",
                callback=self._record_callback,
            ):
                while self.recording:
                    sd.sleep(10)
        except Exception as e:
            if self.master:
                self.master._log_local(f"[ERROR] No se pudo grabar audio: {e}\n")

    def _record_callback(self, indata, frames, time_, status):
        """Callback de sounddevice: guarda chunks de audio."""
        if self.recording:
            self.audio_buffer.append(indata.copy())

    def stop_recording(self, destino, sender_username, send_frame_func, log_local_func):
        if not self.recording:
            log_local_func("No está grabando!\n")
            return

        self.recording = False
        if self.recording_thread:
            self.recording_thread.join()

        log_local_func("[PROCESANDO] Guardando y enviando nota de voz...\n")

        threading.Thread(
            target=self._save_and_send,
            args=(destino, sender_username, send_frame_func, log_local_func),
            daemon=True,
        ).start()

        if self.master:
            try:
                self.master.master.after(0, self.master.actualizar_botones_audio, False)
            except Exception:
                pass

    def _save_and_send(self, destino, sender_username, send_frame_func, log_local_func):
        if len(self.audio_buffer) < 5:
            log_local_func("[ERROR] Grabación demasiado corta.\n")
            return

        os.makedirs(self.folder_sent, exist_ok=True)

        filename = self._get_temp_filename(sender_username)
        path = os.path.join(self.folder_sent, filename)

        # Guardar WAV
        try:
            audio = np.concatenate(self.audio_buffer, axis=0)

            with wave.open(path, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(FORMAT_BYTES)
                wf.setframerate(RATE)
                wf.writeframes(audio.tobytes())

        except Exception as e:
            log_local_func(f"[ERROR] Fallo al guardar audio: {e}\n")
            return

        # Enviar
        try:
            tam = os.path.getsize(path)

            header = {
                "type": "audio",
                "from": sender_username,
                "to": destino,
                "filename": filename,
                "filesize": tam,
            }

            with open(path, "rb") as f:
                datos = f.read()

            send_frame_func(header, datos)
            log_local_func(f"[AUDIO] Yo -> {destino}: '{filename}' ({tam} bytes)\n")

        except Exception as e:
            log_local_func(f"[ERROR] No se pudo enviar audio: {e}\n")

        self.audio_buffer = []

    # -----------------------
    # REPRODUCCIÓN
    # -----------------------

    def reproducir_audio(self, ruta_audio, log_local_func):
        threading.Thread(
            target=self._play_audio, args=(ruta_audio, log_local_func), daemon=True
        ).start()

    def _play_audio(self, ruta_audio, log_local_func):
        try:
            if not os.path.exists(ruta_audio):
                raise FileNotFoundError("No existe el archivo WAV")

            with wave.open(ruta_audio, "rb") as wf:
                channels = wf.getnchannels()
                rate = wf.getframerate()
                sampwidth = wf.getsampwidth()

                if sampwidth != 2:
                    raise ValueError("Solo se soportan WAV de 16 bits")

                data = wf.readframes(CHUNK)

                while data:
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    sd.play(audio_np, samplerate=rate)
                    sd.wait()
                    data = wf.readframes(CHUNK)

            log_local_func(
                f"[AUDIO] Reproducción '{os.path.basename(ruta_audio)}' finalizada.\n"
            )

        except Exception as e:
            log_local_func(f"[ERROR] Fallo al reproducir audio: {e}\n")

    def terminate(self):
        pass  # No es necesario con sounddevice
