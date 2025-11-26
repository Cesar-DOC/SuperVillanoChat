# chat_client_gui_files.py
import socket
import threading
import queue
import json
import struct
import os
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog

HOST_DEFECTO = "127.0.0.1"
PORT_DEFECTO = 65436

CARPETA_DESCARGAS = "descargas_chat"
os.makedirs(CARPETA_DESCARGAS, exist_ok=True)


# ==== Utilidades de framing ====

def send_frame(sock: socket.socket, header: dict, payload: bytes = b""):
    header_bytes = json.dumps(header).encode("utf-8")
    header_len = len(header_bytes)
    sock.sendall(struct.pack("!I", header_len))
    sock.sendall(header_bytes)
    if payload:
        sock.sendall(payload)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket cerrado mientras se recibían datos")
        data += chunk
    return data


def recv_frame(sock: socket.socket):
    raw_len = sock.recv(4)
    if not raw_len:
        raise ConnectionError("Socket cerrado al leer longitud header")
    (header_len,) = struct.unpack("!I", raw_len)
    header_bytes = recv_exact(sock, header_len)
    header = json.loads(header_bytes.decode("utf-8"))

    payload = b""
    if header.get("type") == "file":
        filesize = header.get("filesize", 0)
        if filesize > 0:
            payload = recv_exact(sock, filesize)

    return header, payload


class ChatClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Chat multiusuario con archivos")

        # Estado de red
        self.sock = None
        self.conectado = False
        self.username = None

        # Cola para mensajes entrantes (texto que se mostrará)
        self.cola_mensajes = queue.Queue()
        # Cola para updates de userlist (lista de strings)
        self.cola_userlist = queue.Queue()

        # ---- UI conexión ----
        frame_conn = tk.Frame(master)
        frame_conn.pack(padx=10, pady=5, fill="x")

        tk.Label(frame_conn, text="Servidor:").grid(row=0, column=0, sticky="e")
        self.entry_host = tk.Entry(frame_conn, width=15)
        self.entry_host.insert(0, HOST_DEFECTO)
        self.entry_host.grid(row=0, column=1, padx=3)

        tk.Label(frame_conn, text="Puerto:").grid(row=0, column=2, sticky="e")
        self.entry_port = tk.Entry(frame_conn, width=6)
        self.entry_port.insert(0, str(PORT_DEFECTO))
        self.entry_port.grid(row=0, column=3, padx=3)

        tk.Label(frame_conn, text="Usuario:").grid(row=0, column=4, sticky="e")
        self.entry_user = tk.Entry(frame_conn, width=12)
        self.entry_user.grid(row=0, column=5, padx=3)

        self.btn_conectar = tk.Button(frame_conn, text="Conectar", command=self.conectar)
        self.btn_conectar.grid(row=0, column=6, padx=5)

        # ---- UI principal: lista usuarios + chat ----
        frame_main = tk.Frame(master)
        frame_main.pack(padx=10, pady=5, fill="both", expand=True)

        # Lista de usuarios conectados
        frame_users = tk.Frame(frame_main)
        frame_users.pack(side="left", fill="y")

        tk.Label(frame_users, text="Usuarios conectados").pack()
        self.listbox_users = tk.Listbox(frame_users, height=20, width=20)
        self.listbox_users.pack(fill="y", expand=False)

        # Área de chat
        frame_chat = tk.Frame(frame_main)
        frame_chat.pack(side="left", fill="both", expand=True, padx=(10, 0))

        self.text_chat = scrolledtext.ScrolledText(frame_chat, state="disabled", width=60, height=20)
        self.text_chat.pack(fill="both", expand=True)

        # Campo mensaje + botones
        frame_bottom = tk.Frame(master)
        frame_bottom.pack(padx=10, pady=5, fill="x")

        self.entry_msg = tk.Entry(frame_bottom)
        self.entry_msg.pack(side="left", fill="x", expand=True)
        self.entry_msg.bind("<Return>", self.enviar_texto_evento)

        self.btn_enviar = tk.Button(frame_bottom, text="Enviar mensaje", command=self.enviar_texto)
        self.btn_enviar.pack(side="left", padx=5)

        self.btn_archivo = tk.Button(frame_bottom, text="Enviar archivo", command=self.enviar_archivo)
        self.btn_archivo.pack(side="left", padx=5)

        # Timer para procesar colas
        self.master.after(100, self.procesar_colas)

        # Cierre ordenado
        self.master.protocol("WM_DELETE_WINDOW", self.cerrar)

    # ========= Lógica de red =========

    def conectar(self):
        if self.conectado:
            messagebox.showinfo("Chat", "Ya estás conectado.")
            return

        host = self.entry_host.get().strip()
        port = int(self.entry_port.get().strip())
        username = self.entry_user.get().strip()

        if not username:
            messagebox.showwarning("Chat", "Debes escribir un nombre de usuario.")
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo conectar: {e}")
            return

        self.sock = sock
        self.conectado = True
        self.username = username

        # Enviar frame de login
        header = {
            "type": "login",
            "from": self.username,
            "to": "SERVER",
        }
        send_frame(self.sock, header)

        self.btn_conectar.config(state="disabled")
        self._log_local(f"[CLIENTE] Conectado a {host}:{port} como {username}\n")

        # Lanzar hilo de recepción
        hilo = threading.Thread(target=self.hilo_receptor, daemon=True)
        hilo.start()

    def hilo_receptor(self):
        try:
            while self.conectado and self.sock:
                header, payload = recv_frame(self.sock)
                mtype = header.get("type")

                if mtype == "userlist":
                    users = header.get("users", [])
                    self.cola_userlist.put(users)

                elif mtype == "text":
                    remitente = header.get("from")
                    destino = header.get("to")
                    msg = header.get("message", "")
                    self.cola_mensajes.put(f"{remitente} -> {destino}: {msg}\n")

                elif mtype == "file":
                    remitente = header.get("from")
                    destino = header.get("to")
                    filename = header.get("filename", "archivo")
                    ruta = os.path.join(CARPETA_DESCARGAS, filename)

                    # Evitar sobrescribir: si existe, agrega sufijo
                    base, ext = os.path.splitext(ruta)
                    i = 1
                    while os.path.exists(ruta):
                        ruta = f"{base}_{i}{ext}"
                        i += 1

                    with open(ruta, "wb") as f:
                        f.write(payload)

                    self.cola_mensajes.put(
                        f"[ARCHIVO] {remitente} te envió '{filename}'. Guardado en: {ruta}\n"
                    )

                elif mtype == "system":
                    msg = header.get("message", "")
                    self.cola_mensajes.put(f"[SERVIDOR] {msg}\n")

                else:
                    self.cola_mensajes.put(f"[WARN] Mensaje desconocido: {header}\n")

        except (ConnectionError, OSError):
            self.cola_mensajes.put("[CLIENTE] Conexión con el servidor perdida.\n")
        finally:
            self.conectado = False
            self.sock = None

    # ========= Envío de datos =========

    def _obtener_destinatario(self):
        seleccion = self.listbox_users.curselection()
        if not seleccion:
            messagebox.showwarning("Chat", "Selecciona un usuario en la lista para enviarle un mensaje/archivo.")
            return None
        usuario = self.listbox_users.get(seleccion[0])
        if usuario == self.username:
            if not messagebox.askyesno("Chat", "Seleccionaste tu propio usuario. ¿Quieres continuar?"):
                return None
        return usuario

    def enviar_texto_evento(self, event):
        self.enviar_texto()

    def enviar_texto(self):
        if not self.conectado or not self.sock:
            messagebox.showwarning("Chat", "No estás conectado.")
            return

        destino = self._obtener_destinatario()
        if not destino:
            return

        texto = self.entry_msg.get().strip()
        if not texto:
            return

        header = {
            "type": "text",
            "from": self.username,
            "to": destino,
            "message": texto,
        }

        try:
            send_frame(self.sock, header)
            # Mostrar en chat local
            self._log_local(f"Yo -> {destino}: {texto}\n")
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo enviar el mensaje: {e}")
            self.conectado = False
            self.sock = None

        self.entry_msg.delete(0, tk.END)

    def enviar_archivo(self):
        if not self.conectado or not self.sock:
            messagebox.showwarning("Chat", "No estás conectado.")
            return

        destino = self._obtener_destinatario()
        if not destino:
            return

        ruta = filedialog.askopenfilename(title="Selecciona un archivo para enviar")
        if not ruta:
            return

        try:
            tam = os.path.getsize(ruta)
            filename = os.path.basename(ruta)
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo leer el archivo: {e}")
            return

        if tam == 0:
            if not messagebox.askyesno("Archivo vacío", "El archivo mide 0 bytes. ¿Deseas enviarlo de todos modos?"):
                return

        header = {
            "type": "file",
            "from": self.username,
            "to": destino,
            "filename": filename,
            "filesize": tam,
        }

        try:
            with open(ruta, "rb") as f:
                datos = f.read()
            send_frame(self.sock, header, datos)
            self._log_local(f"[ARCHIVO] Yo -> {destino}: '{filename}' ({tam} bytes)\n")
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo enviar el archivo: {e}")

    # ========= GUI helpers =========

    def _log_local(self, texto: str):
        self.text_chat.config(state="normal")
        self.text_chat.insert(tk.END, texto)
        self.text_chat.see(tk.END)
        self.text_chat.config(state="disabled")

    def procesar_colas(self):
        # Mensajes de chat
        try:
            while True:
                msg = self.cola_mensajes.get_nowait()
                self._log_local(msg)
        except queue.Empty:
            pass

        # Actualizar lista de usuarios
        try:
            while True:
                users = self.cola_userlist.get_nowait()
                self.listbox_users.delete(0, tk.END)
                self.listbox_users.insert(tk.END, "Todos")
                for u in users:
                    self.listbox_users.insert(tk.END, u)
        except queue.Empty:
            pass

        self.master.after(100, self.procesar_colas)

    def cerrar(self):
        self.conectado = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
        self.master.destroy()


def main():
    root = tk.Tk()
    app = ChatClientGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
