"""Prueba el filtro de moderación de palabras en el chat."""
import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"

def login(email, password):
    data = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{BASE}/auth/login", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())["access_token"]

token = login("ana.perez@usbmed.edu.co", "123456")

def send(texto, label):
    data = json.dumps({"contenido": texto}).encode()
    req = urllib.request.Request(
        f"{BASE}/trueques/104/mensajes",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            resp = json.loads(r.read())
            contenido = resp["contenido"]
            print(f"[{label}] OK -> {repr(contenido)}")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        print(f"[{label}] BLOQUEADO ({e.code}): {body['detail']}")

send("Hola, nos vemos manana en la cafeteria", "Normal")
send("Eres un pendejo", "Leve - enmascarar")
send("Malparido no me hagas perder tiempo", "Medio - rechazar")
send("Te voy a matar", "Grave - bloquear")
