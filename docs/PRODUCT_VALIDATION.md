# Sabi: construir por evidencia

17 noviembre 2026. Propuesta aplicada a la referencia compartida por Octavio; no añade permisos de publicación, contacto, datos personales o gasto.

## Referencia y alcance

Post: https://x.com/santtiagom_/status/2122333890350051378?s=46
Guía enlazada: https://assets.claude.com/503ee04b4aa55a4db49a69b993463b6fa8dad6d8.pdf
The Founder's Playbook: Building an AI-Native Startup, 36 páginas. Revisadas secciones clave 9, 16, 22, 26 y 32, no auditoría de todas sus afirmaciones comerciales.

La guía separa idea, MVP, launch y scale. Distingue un prototipo que funciona de evidencia de un problema real y de que un grupo de usuarios vuelve, paga o recomienda. Es una guía del proveedor; sus promesas de velocidad no son garantías técnicas.

## Hipótesis, aún por validar

Personas que resuelven compras y reservas por WhatsApp pierden tiempo saltando entre sitios y repitiendo datos; valorarían un asistente que verifique opciones, conserve contexto y prepare una selección trazable, dejando confirmación y pago a la persona. Debemos validar frecuencia, intensidad y alternativa actual, no suponer mercado porque el código funciona.

## Piloto técnico con Octavio

Mantener tres casos acordados: búsqueda/comparación Mercado Libre, selección entradas MiTickera y pedido Yummy Marketplace. Implementar uno a la vez y documentar cada límite. La compra actual no se usa como experimento de desarrollo.

Por cada tarea, registrar solo lo necesario, con consentimiento y retención definida antes de producción:
- Resultado verificado y evidencia, o bloqueo preciso; selección no equivale a pedido.
- Tiempo hasta selección útil y comparación con hacerlo manualmente.
- Número de preguntas repetidas e intervenciones necesarias.
- Errores de precio, cantidad, identidad o afirmaciones sin fuente.
- Consumo y costo por tarea cuando exista servicio facturable aprobado.
- Si la persona vuelve a usarlo voluntariamente y por qué.

Criterio de seguridad: ningún pago, envío, login de comercio, pedido o cargo no autorizado. Los tests locales no prueban valor de mercado ni fiabilidad de sitios reales. No declarar product-market fit por tres recorridos exitosos.

## Puertas para avanzar

1. Idea: problema y persona concretos, ejemplos recientes y evidencia que pueda contradecir la hipótesis. No inventar entrevistas ni hacer outreach sin autorización.
2. MVP: tarea mínima útil, ejecución real trazable y uso repetido, no lista extensa de funciones. Conservar decisiones y límites entre cambios de código.
3. Launch: revisión técnica y de permisos, aislamiento, observabilidad, seguridad, recuperación, costos y soporte. Requiere aprobación de despliegue aparte.
4. Scale: ampliar solo con evidencia de demanda, retención y economía sostenible. Datos propios no significa acumular conversaciones privadas sin propósito ni consentimiento.

Próxima decisión técnica sugerida: primer conector de solo lectura y métricas mínimas; no contratar un stack entero antes de medirlo. Los umbrales de éxito se fijan antes del piloto real, no después de ver los resultados.
