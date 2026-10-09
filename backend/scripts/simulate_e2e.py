"""Guion de prueba E2E (modo mock):
cliente pide por WhatsApp -> pedido pendiente -> dueño aprueba -> confirmación al cliente.
Run: python -m scripts.simulate_e2e  (requiere seed y el backend corriendo en :8000)"""
import sys

import httpx

API = "http://localhost:8000"
PHONE = "59899123456"

GUION = [
    "hola",
    "quiero 2 milanesa napolitana y una gaseosa 1.5l",
    "delivery",
    "dirección: Av. Italia 1234, apto 5",
    "sí",
]


def main():
    with httpx.Client(base_url=API, timeout=30) as c:
        print("== Conversación del cliente ==")
        for text in GUION:
            r = c.post("/webhook/simulate", json={"phone": PHONE, "text": text, "name": "Cliente Test"})
            reply = r.json()["reply"]
            print(f"\nCliente: {text}\nSabi:    {reply}")

        # Owner login and approval
        r = c.post("/api/auth/login", json={"slug": "la-esquina", "pin": "1234"})
        r.raise_for_status()
        token = r.json()["token"]
        h = {"X-Sabi-Token": token}
        orders = c.get("/api/orders", params={"status": "pending"}, headers=h).json()
        assert orders, "No hay pedidos pendientes"
        order = orders[0]
        print(f"\n== Panel del dueño ==\nPedido #{order['id']} pendiente: "
              + ", ".join(f"{i['quantity']}x {i['name']}" for i in order["items"])
              + f" — total ${order['total']:g}")
        c.post(f"/api/orders/{order['id']}/approve", headers=h).raise_for_status()
        print(f"Dueño aprobó el pedido #{order['id']}.")

        today = c.get("/api/today", headers=h).json()
        print("\n== Vista del día ==", today)
        print("\n✅ E2E OK: pedido creado, aprobado y confirmación registrada.")


if __name__ == "__main__":
    sys.exit(main())
