# chat_server_files.py
import socket
import threading
import json
import struct

HOST = "0.0.0.0"
PORT = 65436

lock = threading.Lock()
usuarios = {}  # username -> socket


# ==== Utilidades de framing ====

def send_frame(sock: socket.socket, header: dict, payload: bytes = b""):
    header_bytes = json.dumps(header).encode("utf-8")
    header_len = len(header_bytes)
    sock.sendall(struct.pack("!I", header_len))  # 4 bytes longitud header
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
    # Leer primero 4 bytes de longitud
    raw_len = sock.recv(4)
    if not raw_len:
        raise ConnectionError("Socket cerrado al leer longitud de encabezado")
    (header_len,) = struct.unpack("!I", raw_len)
    header_bytes = recv_exact(sock, header_len)
    header = json.loads(header_bytes.decode("utf-8"))

    payload = b""
    if header.get("type") == "file":
        filesize = header.get("filesize", 0)
        if filesize > 0:
            payload = recv_exact(sock, filesize)

    return header, payload


# ==== Lógica del servidor ====

def broadcast_userlist():
    with lock:
        user_list = list(usuarios.keys())
        for user, sock in usuarios.items():
            header = {
                "type": "userlist",
                "from": "SERVER",
                "to": user,
                "users": user_list,
            }
            try:
                send_frame(sock, header)
            except OSError:
                pass


def manejar_cliente(sock: socket.socket, addr):
    username = None
    try:
        # Esperar frame de login
        header, _ = recv_frame(sock)
        if header.get("type") != "login":
            raise ValueError("Primer mensaje no es login")

        username = header.get("from")
        if not username:
            raise ValueError("Login sin nombre de usuario")

        with lock:
            if username in usuarios:
                # Nombre en uso
                error_header = {
                    "type": "system",
                    "from": "SERVER",
                    "to": username,
                    "message": "Nombre de usuario ya está en uso.",
                }
                send_frame(sock, error_header)
                raise ValueError("Username duplicado")
            usuarios[username] = sock

        print(f"[+] {username} conectado desde {addr}")
        # Avisar userlist nueva
        broadcast_userlist()

        # Bucle principal de recepción
        while True:
            header, payload = recv_frame(sock)
            mtype = header.get("type")

            if mtype == "text":
                destino = header.get("to")
                mensaje = header.get("message", "")
                print(f"[MSG] {username} -> {destino}: {mensaje}")

                with lock:
                    dest_sock = usuarios.get(destino)
                if dest_sock:
                    send_frame(dest_sock, header)  # reenviamos tal cual
                else:
                    # Enviar error al remitente
                    err = {
                        "type": "system",
                        "from": "SERVER",
                        "to": username,
                        "message": f"Usuario '{destino}' no existe o no está conectado.",
                    }
                    send_frame(sock, err)

            elif mtype == "file":
                destino = header.get("to")
                filename = header.get("filename", "archivo")
                print(f"[FILE] {username} -> {destino}: {filename}")

                with lock:
                    dest_sock = usuarios.get(destino)
                if dest_sock:
                    # Reenviar mismo header y payload al destinatario
                    send_frame(dest_sock, header, payload)
                else:
                    err = {
                        "type": "system",
                        "from": "SERVER",
                        "to": username,
                        "message": f"No se pudo entregar el archivo, usuario '{destino}' no está conectado.",
                    }
                    send_frame(sock, err)

            else:
                # Mensaje no soportado
                print(f"[WARN] Tipo no soportado: {mtype} de {username}")

    except (ConnectionError, OSError):
        print(f"[!] Conexión perdida con {addr} ({username})")
    except Exception as e:
        print(f"[ERR] Error con {addr} ({username}): {e}")
    finally:
        if username:
            with lock:
                if usuarios.get(username) is sock:
                    del usuarios[username]
            print(f"[-] {username} desconectado")
            broadcast_userlist()
        try:
            sock.close()
        except OSError:
            pass


def main():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PORT))
    servidor.listen()
    print(f"[SERVIDOR] Escuchando en {HOST}:{PORT} ...")

    try:
        while True:
            conn, addr = servidor.accept()
            hilo = threading.Thread(target=manejar_cliente, args=(conn, addr), daemon=True)
            hilo.start()
    except KeyboardInterrupt:
        print("\n[SERVIDOR] Cerrando por CTRL+C...")
    finally:
        servidor.close()


if __name__ == "__main__":
    main()
