import tkinter as tk

EMOJIS = {
    "smile": "😄",
    "sad": "😢",
    "heart": "❤️",
    "thumbs_up": "👍",
    "fire": "🔥",
    "clap": "👏",
}

def get_emoji(name):
    return EMOJIS.get(name, "")

def insertar_emoji(cliente, name):
    if name in EMOJIS.values():
        emoji = name
    else:
        emoji = get_emoji(name)

    if emoji:
        try:
            cliente.entry_msg.insert(tk.END, emoji)
        except Exception:
            pass

    # Cerrar la paleta si está abierta
    try:
        if hasattr(cliente, 'paleta_emoji') and cliente.paleta_emoji:
            cliente.paleta_emoji.destroy()
    except Exception:
        pass

    return cliente

def mostrar_paleta_emojis(cliente):
    """Crea y muestra la ventana Toplevel con los botones de emoji."""
    cliente.paleta_emoji = tk.Toplevel(cliente.master)
    cliente.paleta_emoji.title("Emojis")
    cliente.paleta_emoji.geometry("150x120") 
    cliente.paleta_emoji.transient(cliente.master) # Mantiene la paleta encima de la ventana principal
    
    fila = 0
    columna = 0
    
    for nombre, caracter in EMOJIS.items():
        btn = tk.Button(cliente.paleta_emoji, text=caracter, font=("Arial", 16),
                        command=lambda c=caracter: insertar_emoji(cliente, c))
        btn.grid(row=fila, column=columna, padx=2, pady=2)
        
        columna += 1
        if columna >= 3: # 3 emojis por fila
            columna = 0
            fila += 1