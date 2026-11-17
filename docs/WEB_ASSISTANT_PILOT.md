# Sabi: primera etapa del piloto

17 noviembre 2026. Rama aislada; no publicar ni fusionar todavía.

## Cambios reales

- Adaptador Zernio de reacciones y typing según documentación actual. Ambos quedan inactivos por defecto; requieren flag y lista de teléfonos. Solo usan conversación proveniente del webhook entrante firmado. Ninguna búsqueda automática de conversaciones para estos efectos.
- Estados de tarea y evidencia para una futura capa web. Las respuestas anteriores (búsqueda y cantidad) no se pierden al llegar otro fragmento. No es un intérprete de lenguaje natural ni una memoria completa.
- Ejercicio local real en Chromium: abre una página ficticia, escribe una búsqueda, elige cantidad, lee el total, deja selección para revisión y toma captura. Toda petición fuera del servidor local se bloquea; también métodos distintos de GET y WebSockets. Una petición deliberada a un dominio externo es bloqueada como prueba.

## Límites de esta entrega

No se ha integrado búsqueda pública, navegación de comercios reales, login, carritos reales, pagos ni un modelo nuevo. La prueba local NO demuestra integración con Mercado Libre, Yummy o MiTickera. Las páginas se tratan como datos, no instrucciones. El modelo web está separado del webhook de producción. No hay nuevos endpoints públicos ni credenciales en código. Las autorizaciones de compra reales no se obtienen de texto de páginas ni de un plan generado.

El envío real de WhatsApp sigue sin probarse. Una respuesta HTTP 200 no equivale a visibilidad de typing/reacciones. No se reintentan timeouts ambiguos. Typing marca leído el mensaje entrante y dura hasta 25 segundos según Zernio. La activación futura exige revisión y autorización aparte; no activar contra todo el público.

## Reproducir sin servicios pagos

Desde `backend/`, instalar `requirements-dev.txt` en un entorno virtual y ejecutar:

```
python -m pytest tests/test_presence_pilot.py tests/test_web_tasks.py -q
```

Para el recorrido de navegador, instalar `pilot/requirements-web.txt` en el mismo entorno y disponer de Chromium local (`google-chrome-stable` o `chromium`):

```
python pilot/web_local_demo.py /tmp/sabi-web-demo
```

Se escriben PNG y JSON locales. No se crea una cuenta ni se usa cloud. Playwright está fijado para repetir esta prueba; revisar actualizaciones de seguridad antes de producción. No usar la imagen ficticia como evidencia de stock/precios reales.

Para probar payloads Zernio se usa `httpx.MockTransport` con valores ficticios. Los tests no consumen API.

## Antes de activarlo

1. Validar permisos, términos y rutas útiles de cada sitio. Empezar por búsqueda/lectura verificadas, sin prometer compra API.
2. Resolver ejecución de navegador fuera del proceso serverless, aislamiento de red, controles DNS/SSRF por petición, redirecciones y subrecursos, retención de capturas, tiempos y límites. `validate_public_url` es solo allowlist sintáctica, no una defensa SSRF completa.
3. Integrar el estado de tareas con persistencia y el agente existente. Agrupar mensajes seguidos y probar cambio de tema/cancelación sin repetir preguntas.
4. Elegir si el piloto podrá acceder a cuentas. Todavía no está aprobado. No copiar sesiones, cookies o contraseñas a código.
5. Prueba E2E sin outbound real; luego revisión para habilitar únicamente al teléfono autorizado. Un carrito o selección no es reserva ni pedido confirmado. El usuario confirma y paga.

## Guardas de despliegue

El proyecto `sabi-api` tiene integración Git activa en Vercel. Se añade `git.deploymentEnabled` para deshabilitar **solo esta rama de prueba** en root, backend y web. Se mantienen las demás opciones. No fusionar configuraciones sin revisar. No se cambia la conexión Git ni settings de producción. Workflow GitHub actual es de ejecución manual; no se despacha. No se abre PR automáticamente.

Documentación: https://vercel.com/docs/project-configuration/git-configuration

## Contratos públicos

- https://docs.zernio.com/messages/send-typing-indicator
- https://docs.zernio.com/messages/add-message-reaction
- https://playwright.dev/python/docs/intro

Las funciones son código preparado y probado localmente, no una promesa de servicio en producción.
