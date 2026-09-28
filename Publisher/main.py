from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, date
import requests
import json

app = FastAPI()

# ---------------------------------------------------------
# Configuración de Solace Cloud (Reemplaza con tus datos)
# ---------------------------------------------------------
SOLACE_REST_URL = "https://mr-connection-9720beithj3.messaging.solace.cloud:9443"
SOLACE_USERNAME = "solace-cloud-client"
SOLACE_PASSWORD = "tb5lg4d3iitttp62u82u9heog2"
TOPIC_TRANSPORTISTAS = "pedidos/validos" # Cola para carriers
TOPIC_CLIENTES = "pedidos/estado"        # Cola para clientes

# ---------------------------------------------------------
# Modelos de Datos (Payload esperado)
# ---------------------------------------------------------
class Stop(BaseModel):
    stopNumber: int
    city: str
    state: str
    postalCode: str

class Vehicle(BaseModel):
    year: str
    make: str
    model: str

class DispatchPayload(BaseModel):
    shipperOrderId: str
    pickupDate: str
    deliveryDate: str
    price: float
    stops: list[Stop]
    vehicles: list[Vehicle]
    transportationReleaseNotes: str

# ---------------------------------------------------------
# Función para publicar en Solace vía REST
# ---------------------------------------------------------
def publicar_solace(topic: str, mensaje: dict):
    url = f"{SOLACE_REST_URL}/{topic}"
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        url, 
        auth=(SOLACE_USERNAME, SOLACE_PASSWORD), 
        headers=headers, 
        data=json.dumps(mensaje)
    )
    return response.status_code == 200

# ---------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------
@app.post("/api/dispatch")
def procesar_dispatch(payload: DispatchPayload):
    hoy = date.today()
    hora_actual = datetime.now().time()
    
    # Convertir strings a objetos date
    try:
        fecha_pickup = datetime.strptime(payload.pickupDate, "%Y-%m-%d").date()
        fecha_delivery = datetime.strptime(payload.deliveryDate, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")

    es_valido = True
    mensaje_error = ""

    # Regla 1 y 2: Validar Pickup Date y hora límite (3:00 PM)[cite: 1]
    if fecha_pickup < hoy:
        es_valido = False
        mensaje_error = "Pickup date cannot be earlier than the current date."
    elif fecha_pickup == hoy and hora_actual.hour >= 15:
        es_valido = False
        mensaje_error = "Shipments cannot be requested after 3:00 p.m. for same-day pickup."
        
    # Regla 3: Validar Delivery Date (al menos 1 día de diferencia)[cite: 1]
    if es_valido:
        diferencia_dias = (fecha_delivery - fecha_pickup).days
        if diferencia_dias < 1:
            es_valido = False
            mensaje_error = "Delivery date must be at least one day after pickup date."

    # Procesar según el resultado de las validaciones
    if es_valido:
        # Enviar payload original a la cola de transportistas[cite: 1]
        publicar_solace(TOPIC_TRANSPORTISTAS, payload.dict())
        
        # Enviar respuesta de aceptación a la cola de clientes[cite: 1]
        payload_cliente = {
            "shipperOrderId": payload.shipperOrderId,
            "status": "Accepted",
            "notes": "You will receive an email when a carrier accepts this dispatch request"
        }
        publicar_solace(TOPIC_CLIENTES, payload_cliente)
        
        return {"status": "success", "message": "Payload validado y encolado correctamente."}
        
    else:
        # Enviar respuesta de cancelación a la cola de clientes[cite: 1]
        payload_cancelado = {
            "shipperOrderId": payload.shipperOrderId,
            "status": "Cancelled",
            "notes": mensaje_error
        }
        publicar_solace(TOPIC_CLIENTES, payload_cancelado)
        
        return {"status": "rejected", "message": "Payload inválido reportado al cliente.", "reason": mensaje_error}
