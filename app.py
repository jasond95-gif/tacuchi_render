from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    jsonify,
)
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_mas_seguro"

# =========================
# RUTAS DE ARCHIVOS
# =========================
# Cambia esta ruta si mueves tu proyecto a otra carpeta.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "pedidos_restaurante.csv")

# Archivo que guarda la fecha/hora del último "borrado" de historial web
RESET_FILE = os.path.join(os.path.dirname(CSV_FILE), "historial_reset.txt")


# =========================
# FUNCIONES DE APOYO
# =========================
def init_csv():
    """Crea el archivo CSV con cabeceras si no existe."""
    carpeta = os.path.dirname(CSV_FILE)
    if carpeta and not os.path.exists(carpeta):
        os.makedirs(carpeta, exist_ok=True)

    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["fecha_hora", "mesa", "detalle", "total"])


# Llamamos a init_csv() al iniciar la app
init_csv()


# =========================
# MENÚ DEL RESTAURANTE
# =========================
MENU = {
    "PARRILLAS": [
        {"id": 1, "name": "Parrilla Mixta", "price": 35.0},
        {"id": 2, "name": "Parrilla al Barril", "price": 38.0},
        {"id": 3, "name": "Parrilla Tacuchi", "price": 55.0},
    ],
    "HAMBURGUESAS": [
        {"id": 4, "name": "Clásica", "price": 7.0},
        {"id": 5, "name": "A lo Pobre", "price": 8.5},
        {"id": 6, "name": "Parrillera", "price": 10.0},
        {"id": 7, "name": "Surfer", "price": 12.0},
        {"id": 8, "name": "La Suprema", "price": 16.0},
    ],
    "BEBIDAS": [
        {"id": 9, "name": "Chicha Morada 1 lt", "price": 12.0},
        {"id": 10, "name": "Inka Cola 1/2 lt", "price": 4.0},
        {"id": 11, "name": "Coca Cola 1/2 lt", "price": 4.0},
    ],
}


# =========================
# FUNCIONES DEL CARRITO
# =========================
def get_item_by_id(item_id: int):
    """Busca un item del menú por ID."""
    for category, items in MENU.items():
        for item in items:
            if item["id"] == item_id:
                return item
    return None


def calcular_carrito(cart_dict):
    """Convierte el diccionario del carrito en una lista para mostrar."""
    cart_items = []
    total = 0.0

    for item_id_str, qty in cart_dict.items():
        item = get_item_by_id(int(item_id_str))
        if item:
            subtotal = item["price"] * qty
            total += subtotal
            cart_items.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "qty": qty,
                    "price": item["price"],
                    "subtotal": subtotal,
                }
            )
    return cart_items, total


def guardar_pedido_en_csv(fecha_hora, mesa, items, total):
    """Guarda un pedido en el CSV en formato texto (detalle)."""
    detalle_list = [
        f"{it['name']} x{it['qty']} = {float(it['subtotal']):.2f}"
        for it in items
    ]
    detalle = " | ".join(detalle_list)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            fecha_hora,
            mesa,
            detalle,
            f"{float(total):.2f}",
        ])


# =========================
# RUTAS PRINCIPALES
# =========================
@app.route("/", methods=["GET", "POST"])
def index():
    # Inicializar carrito en sesión
    if "cart" not in session:
        session["cart"] = {}

    # Si agregan un producto
    if request.method == "POST":
        item_id = int(request.form["item_id"])
        qty = int(request.form.get("qty", 1))
        if qty < 1:
            qty = 1

        cart = session["cart"]
        cart[str(item_id)] = cart.get(str(item_id), 0) + qty
        session["cart"] = cart

        flash("Producto agregado al pedido.")
        return redirect(url_for("index"))

    cart_items, total = calcular_carrito(session.get("cart", {}))
    return render_template("index.html", menu=MENU, cart_items=cart_items, total=total)


@app.route("/vaciar_carrito")
def vaciar_carrito():
    session["cart"] = {}
    flash("Carrito vaciado.")
    return redirect(url_for("index"))


@app.route("/eliminar_item/<int:item_id>")
def eliminar_item(item_id):
    cart = session.get("cart", {})
    cart.pop(str(item_id), None)
    session["cart"] = cart
    flash("Producto eliminado del pedido.")
    return redirect(url_for("index"))


@app.route("/confirmar_pedido", methods=["POST"])
def confirmar_pedido():
    """
    Flujo normal ONLINE:
    - Es llamado por el formulario cuando hay conexión con el servidor.
    - Calcula el carrito, guarda en CSV y muestra ticket.
    """
    mesa = request.form.get("mesa", "").strip()
    cart = session.get("cart", {})

    if not cart:
        flash("No hay productos en el pedido.")
        return redirect(url_for("index"))

    cart_items, total = calcular_carrito(cart)
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Guardar en CSV (histórico completo)
    items_para_guardar = [
        {
            "name": item["name"],
            "qty": item["qty"],
            "subtotal": item["subtotal"],
        }
        for item in cart_items
    ]
    guardar_pedido_en_csv(fecha_hora, mesa, items_para_guardar, total)

    # Vaciar carrito (el ticket usa la copia cart_items, no la sesión)
    session["cart"] = {}

    # Mostrar la pantalla de ticket
    return render_template(
        "ticket.html",
        mesa=mesa,
        cart_items=cart_items,
        total=total,
        fecha_hora=fecha_hora,
    )


# =========================
# API PARA SINCRONIZAR PEDIDOS OFFLINE (PWA)
# =========================
@app.route("/api/sync_pedidos_offline", methods=["POST"])
def sync_pedidos_offline():
    """
    Recibe un listado de pedidos guardados offline en la PWA.
    Espera JSON como:
    {
      "pedidos": [
        {
          "fecha_hora": "...",
          "mesa": "...",
          "total": 50.5,
          "items": [
            {"name": "...", "qty": 2, "subtotal": 20.0},
            ...
          ]
        },
        ...
      ]
    }
    """
    data = request.get_json(silent=True) or {}
    pedidos = data.get("pedidos", [])

    if not isinstance(pedidos, list):
        return jsonify({"status": "error", "message": "Formato inválido"}), 400

    for p in pedidos:
        fecha_hora = p.get("fecha_hora") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mesa = p.get("mesa", "N/A")
        total = p.get("total", 0.0)
        items = p.get("items", [])

        # Validación mínima
        if not isinstance(items, list) or len(items) == 0:
            continue

        guardar_pedido_en_csv(fecha_hora, mesa, items, total)

    return jsonify({"status": "ok", "synced": len(pedidos)})


# =========================
# HISTORIAL + "VACIAR" SOLO EN LA WEB
# =========================
@app.route("/pedidos")
def pedidos():
    registros = []

    # Leer la fecha/hora del último "borrado" de historial web (si existe)
    reset_time = None
    if os.path.exists(RESET_FILE):
        try:
            with open(RESET_FILE, "r", encoding="utf-8") as f:
                txt = f.read().strip()
                if txt:
                    reset_time = datetime.strptime(txt, "%Y-%m-%d %H:%M:%S")
        except Exception:
            reset_time = None  # si hay error, no filtramos

    # Leer el CSV completo (histórico)
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Ignoramos la cabecera
            if len(rows) > 1:
                for row in rows[1:]:
                    if len(row) >= 4:
                        fecha_txt = row[0]
                        try:
                            fecha_dt = datetime.strptime(fecha_txt, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            fecha_dt = None

                        # Si hay reset_time, solo mostramos pedidos posteriores
                        if reset_time and fecha_dt and fecha_dt <= reset_time:
                            continue

                        registros.append(
                            {
                                "fecha_hora": row[0],
                                "mesa": row[1],
                                "detalle": row[2],
                                "total": row[3],
                            }
                        )

    return render_template("pedidos.html", pedidos=registros)


@app.route("/vaciar_historial")
def vaciar_historial():
    # Guardar la fecha/hora actual como "punto de corte" del historial web
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(RESET_FILE, "w", encoding="utf-8") as f:
        f.write(ahora)

    flash("Historial de pedidos vaciado en la aplicación (el CSV sigue intacto).")
    return redirect(url_for("pedidos"))


# =========================
# SERVICE WORKER (PWA)
# =========================
@app.route("/sw.js")
def service_worker():
    """Sirve el service worker desde la raíz del proyecto."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(base_dir, "sw.js", mimetype="application/javascript")


# =========================
# EJECUCIÓN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

