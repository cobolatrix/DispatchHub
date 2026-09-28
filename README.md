# Sistema de Despacho DispatchHub

Sistema de despacho de envíos basado en eventos que conecta a clientes y transportistas. Utiliza un backend ligero en Python para la validación de reglas de negocio, Solace Cloud como bróker de mensajería (Event Broker) y OutSystems Developer Cloud (ODC) para las interfaces de usuario (Dashboards) y la persistencia de datos.

## Arquitectura del Sistema

El flujo de información opera bajo un modelo de publicación y suscripción (Pub/Sub) conectado a través de Webhooks (Push):

1. **Backend (Publisher):** Una API REST en Python (FastAPI) recibe la solicitud original, ejecuta validaciones de fecha/hora y publica eventos en tópicos específicos de Solace.
2. **Event Broker (Middleware):** Solace Cloud recibe los mensajes en tópicos, los encola mediante suscripciones y utiliza un REST Delivery Point (RDP) para hacer *push* de los datos.
3. **Frontend y Base de Datos (Consumer):** OutSystems Developer Cloud expone APIs REST públicas para recibir los webhooks desde Solace, procesando los JSON y guardando la información en las entidades nativas mediante acciones de base de datos directas.

## Reglas de Negocio Implementadas

El backend valida estrictamente cada solicitud de envío bajo las siguientes reglas:
* **Fecha mínima de recolección:** La fecha de *pickup* no puede ser anterior a la fecha actual del sistema.
* **Límite de horario:** Las recolecciones programadas para el mismo día (*same-day pickup*) deben solicitarse obligatoriamente antes de las 15:00 horas (3:00 PM).
* **Tiempo de tránsito:** La fecha de entrega (*delivery*) debe tener al menos un día (24 horas) de diferencia respecto a la fecha de recolección.

## Configuración de Solace Cloud

El enrutamiento de mensajes requiere la siguiente configuración en el *Broker Manager*:

### Enrutamiento de Tópicos a Colas

| Tópico (Publicador Python) | Cola de Mensajes (Queue) | Propósito |
| :--- | :--- | :--- |
| `pedidos/validos` | `Q_pedidos_validos` | Solicitudes que pasaron todas las validaciones. Destinadas al dashboard de transportistas. |
| `pedidos/estado` | `Q_estado_cliente` | Actualizaciones de estado (Accepted/Cancelled) y notas de error. Destinadas al dashboard de clientes. |

### REST Delivery Point (RDP)

Para que Solace envíe los mensajes automáticamente a OutSystems, el RDP debe configurarse con los siguientes parámetros de red y seguridad:
* **REST Consumer Host:** Dominio raíz de ODC (ej. `https://personal-xxxx-dev.outsystems.app`).
* **Puerto y Seguridad:** Puerto `443` con la opción **TLS Enabled** activada.
* **Queue Bindings (Post Request Target):**
  * `Q_pedidos_validos` apunta a `/DispatchHub/rest/BrokerAPI/PostPedidoValido`
  * `Q_estado_cliente` apunta a `/DispatchHub/rest/BrokerAPI/PostEstadoCliente`

## Configuración en OutSystems Developer Cloud (ODC)

Para permitir el ingreso correcto de los mensajes automatizados desde Solace sin generar errores de tipo `OS-BERT-00000` (Permisos denegados):

1. **Autenticación de la API:** La propiedad *Authentication* en el módulo REST (Expose) debe estar en `None`.
2. **Escritura Directa a Base de Datos:** Los flujos de las APIs deben evitar el uso de *Server Actions* autogenerados para la persistencia, ya que estos heredan validaciones de roles de usuario (ej. Admin, Transporter). En su lugar, se deben arrastrar las **acciones nativas de base de datos** (ej. `CreateOrUpdatePedidoDisponible`) directamente desde la pestaña *Data* hacia la lógica de la API.
3. **Generación de Identificadores:** Al mapear los datos hacia la acción de base de datos, el atributo `Id` debe asignarse a `NullIdentifier()` para garantizar la creación de un nuevo registro.

## Instalación y Ejecución Local

**Prerrequisitos:**
* Python 3.9 o superior.

**Instalación de dependencias:**
```bash
pip install fastapi uvicorn pydantic requests
```

**Ejecución del servidor:**
```bash
python -m uvicorn main:app --reload
```

Una vez que el servidor esté corriendo, puedes acceder a la interfaz interactiva de Swagger UI en http://127.0.0.1:8000/docs para enviar cargas de prueba (payloads) simulando un cliente externo, o enviar peticiones POST directamente a http://127.0.0.1:8000/api/dispatch.
