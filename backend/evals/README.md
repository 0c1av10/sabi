# Evaluación conversacional interna

Estado: kit de revisión sin red ni modelo. No es evidencia de que el modelo ya responda bien.

## Ciclo de mejora
1. Elegir casos y fijar reloj, versión de código, prompt y fuentes.
2. Capturar conversación completa: contexto mínimo, pregunta, herramienta, resultado relevante y respuesta final. Sin teléfonos, correos, pagos, tokens ni conversaciones ajenas. Usar identificadores sintéticos. Guardar fuente/fecha de lectura, no sólo un resumen.
3. Puntuar cada turno y el cierre: veracidad, utilidad, naturalidad y uso del contexto, de0a2. Veracidad debe ser2 en todos los turnos. Otras dimensiones deben ser al menos1 en cada turno y2 en el cierre. Una compra inventada, fuente equivocada o fuga de datos bloquea siempre.
4. Localizar causa: enrutamiento, datos, manejo de parcial, prompt, memoria o entrega. Cambiar una cosa. No tapar con tono una fuente equivocada.
5. Repetir mismo caso con mismas fuentes; comparar versión anterior/candidata sin indicar cuál es cuál al revisor. Repetir también los demás casos para detectar regresiones.
6. Máximo dos iteraciones por ronda. Si persiste un fallo, registrar bloqueo y siguiente cambio propuesto. Publicación requiere decisión explícita, nunca un puntaje automático.

## Capas de evidencia
- Determinista: dobles de modelo/herramientas y fixtures etiquetados. Prueba flujo, límites y conservación de contexto, no calidad real de Claude.
- Lectura real: proveedor y HTML públicos, sin modelo ni cuenta/compra. Prueba datos y extracción en ese instante, no respuesta conversacional.
- Replay de modelo: conversaciones sintéticas y herramientas de sólo lectura simuladas, utilizando el mismo prompt y modelo. Consume saldo, requiere aprobación separada y límite monetario. Transporte reemplazado por capturador; ninguna salida a WhatsApp, BD de producción o comercio. Herramientas de pedido/pago/alta bloqueadas.
- Captura producción: diagnóstico de pruebas que el usuario hizo. No volver a enviar ni ejecutar. Minimizar y anonimizar antes de guardar.

`cases.json` tiene12conversaciones de3turnos. `review.py` consume capturas, detecta jerga, exceso de preguntas, longitud, posible dato personal y revisión faltante. No puntúa naturalidad con una regex. Un revisor asigna los puntajes y liga afirmaciones a fuentes. El resultado no publica nada.

```sh
python evals/review.py --transcripts candidate.json --output review.json
```

## Anclas observables
- Veracidad2: cada sede, fecha, horario, precio y estado tiene fuente correcta; se conserva parcial/sólo taquilla; ninguna promesa de compra.
- Utilidad2: responde la intención y da siguiente paso concreto; recomienda con razón cuando hay datos, no entrega sólo una lista o devuelve trabajo evitable.
- Naturalidad2: español cercano, frases cortas, sin códigos ni narración interna, una pregunta necesaria, sin descargos repetidos.
- Contexto2: recuerda ciudad/fecha/gusto explícitos, no pregunta de nuevo ni conserva tema viejo cuando cambia.

## Antes/después, sólo objetivo editorial
Antes observado en prueba del usuario: PlazaMayor no resuelto; explicación de código y oferta de otro cine.
Después deseado, NO salida comprobada del modelo: «En Plaza Mayor, para el17de noviembre, Las Altagracias en Navidad aparece a las5pm. Es comedia, así que encaja con lo que me dices. La venta figura sólo en taquilla. ¿Te provoca esa o prefieres otra opción?» Sólo sería válido con fecha, gusto y horarios respaldados por la captura del turno. Incluir enlace oficial al compartir horarios, sin repetir advertencias en cada respuesta.

## Ronda actual
Corrección PlazaMayor:9tests nuevos, suite total164pasan/3fallos preexistentes. Lectura pública real17nov2026 valida4funciones sólo taquilla en la misma sede. No se ejecutó replay pagado ni se evaluó como real una respuesta escrita a mano.

## Presupuesto pendiente
Ninguna llamada de modelo nueva autorizada o ejecutada. El código configura `claude-sonnet-5-5`, que puede ser reemplazado por configuración de producción. Antes de pedir aprobación: verificar modelo efectivo, tarifa de entrada/salida/caché y límite duro disponible en cuenta. Propuesta acotada:12casos x3turnos, máximo4consultas por turno y700tokens de salida por llamada; una conversación puede necesitar varias llamadas, así que36turnos NO equivalen a36llamadas. Medir tokens de entrada de prompts/herramientas/historial y cotizar techo con el número máximo de llamadas. No hay estimación monetaria verificada todavía. Sin aprobación, seguir sólo en capas determinista y lectura pública.
