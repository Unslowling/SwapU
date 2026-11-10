import urllib.request
import json

BASE = 'http://127.0.0.1:8000'

def post(url, data, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(BASE + url, data=json.dumps(data).encode(), headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def get(url, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(BASE + url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def main():
    u1 = 'test1_p2p@correo.com'
    try:
        post('/auth/register', {'email': u1, 'password': 'password123', 'name': 'Juan Perez'})
    except Exception:
        pass
    tok1_resp = post('/auth/login', {'email': u1, 'password': 'password123'})
    token1 = tok1_resp['access_token']
    me1 = get('/usuarios/me', token=token1)

    u2 = 'test2_p2p@correo.com'
    try:
        post('/auth/register', {'email': u2, 'password': 'password123', 'name': 'Maria Gomez'})
    except Exception:
        pass
    tok2_resp = post('/auth/login', {'email': u2, 'password': 'password123'})
    token2 = tok2_resp['access_token']
    me2 = get('/usuarios/me', token=token2)

    print(f"Users: {me1['name']} (ID {me1['id']}) and {me2['name']} (ID {me2['id']})")

    # 1. Register books
    p1 = post('/publicaciones/', {
        'titulo': 'Calculo de Varias Variables',
        'autor': 'James Stewart',
        'isbn': '9780538497817',
        'categoria_id': 3,
        'estado_conservacion': 'bueno',
        'intereses_intercambio': 'Fisica Cuantica'
    }, token=token1)

    p2 = post('/publicaciones/', {
        'titulo': 'Fisica para Ingenieria',
        'autor': 'Sears Zemansky',
        'isbn': '9786073221900',
        'categoria_id': 3,
        'estado_conservacion': 'excelente',
        'intereses_intercambio': 'Calculo'
    }, token=token2)
    print(f"Books created: ID {p1['id']} ({p1['titulo']}) & ID {p2['id']} ({p2['titulo']})")

    # 2. Propose trade
    t = post('/trueques/proponer', {
        'usuario_recibe_id': int(me2['id']),
        'publicacion_origen_id': p1['id'],
        'publicacion_destino_id': p2['id']
    }, token=token1)
    tid = t['id']
    print(f"Trade proposed: ID {tid}, estado: {t['estado']}")

    # 3. Check info endpoint
    info = get(f"/trueques/{tid}/info", token=token1)
    print(f"Trade Info retrieved: {info['usuario_propone_nombre']} -> {info['usuario_recibe_nombre']}")
    print(f"Libros: {info['libro_propone']} <--> {info['libro_recibe']}")

    # 4. Chat while state is propuesto (P2P pre-agreement negotiation)
    m1 = post(f"/trueques/{tid}/mensajes", {'contenido': 'Hola Maria! Me interesa tu libro. ¿Podemos vernos mañana?'}, token=token1)
    print(f"Msg 1 (propuesto): [{m1['remitente_nombre']}]: {m1['contenido']}")

    m2 = post(f"/trueques/{tid}/mensajes", {'contenido': 'Hola Juan! Si claro, a las 3 en la biblioteca.'}, token=token2)
    print(f"Msg 2 (propuesto): [{m2['remitente_nombre']}]: {m2['contenido']}")

    # 5. Receiver confirms trade
    c = post(f"/trueques/{tid}/confirmar", {}, token=token2)
    print(f"Trade confirmed! Nuevo estado: {c['estado']}")

    # 6. Chat while state is confirmado
    m3 = post(f"/trueques/{tid}/mensajes", {'contenido': 'Listo, confirmado. Llevo el libro empacado.'}, token=token1)
    print(f"Msg 3 (confirmado): [{m3['remitente_nombre']}]: {m3['contenido']}")

    # 7. Complete trade
    comp = post(f"/trueques/{tid}/completar", {}, token=token1)
    print(f"Trade completed! Estado final: {comp['estado']}")

    # 8. Verify history
    all_msgs = get(f"/trueques/{tid}/mensajes", token=token1)
    print(f"Total messages in conversation history: {len(all_msgs)}")
    for msg in all_msgs:
        print(f"  - {msg['remitente_nombre']}: \"{msg['contenido']}\"")

    print("\n>>> FULL P2P CONVERSATION AND TRADE FLOW OPERATIONAL! <<<")

if __name__ == '__main__':
    main()
