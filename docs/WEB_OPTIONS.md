# Opciones para Sabi - 17 noviembre 2026

## Recomendación

Empezar con Playwright Python y flujos limitados por sitio, en un proceso de navegador separado del webhook. Mantener conversación y estado en Sabi. No contratar aún una plataforma de agentes: primero medir éxito, errores y costo por tarea en Mercado Libre, MiTickera y Yummy Marketplace. La prueba entregada usa solo una tienda local ficticia, no demuestra acceso a esos comercios.

## Comparación, por función

1. **Playwright, primera etapa.** Biblioteca Apache-2.0, sin licencia de pago. Navega, llena campos, toma capturas y permite pruebas repetibles. No decide por sí sola: el equipo mantiene selectores, permisos, verificación y estado. Infraestructura y modelo se pagan aparte si se usan. Menor dependencia de proveedor; mayor trabajo propio.
2. **Browser Use, posible capa de decisión después.** Biblioteca MIT; el servicio cloud es aparte. Aporta agente para tareas web variables, pero requiere políticas y verificación externa del éxito. Cloud publica navegador a $0.06/h más tráfico ($5/GB residencial o $0.20/GB directo); modelo/agente adicionales. No es el precio total de una tarea. Probar primero sin cuentas ni efectos, con límite de pasos, tiempo y costo. Dependencia mayor de su capa de agente y versiones. Un issue cerrado de usuarios reporta fallos headless/CDP en una versión concreta: evidencia anecdótica, no benchmark ni afirmación de fallo actual.
3. **Firecrawl, lectura y búsqueda, no sustituto de checkout.** Servicio: 1.000 créditos gratis al mes; Hobby $19/mes con pago mensual según página consultada. Scrape desde 1 crédito/página; búsqueda 2 créditos/10 resultados. Interacción puede costar 2-7 créditos/minuto; PDF, extracción y otros modos añaden consumo. Repositorio principal AGPL-3.0, algunos SDK MIT. Revisar obligaciones de licencia antes de alojar/modificar e integrar. Útil para leer páginas públicas; contenido enviado al proveedor requiere revisar privacidad, retención y ubicación. No se adoptó.
4. **Browserbase, alojamiento si hace falta.** No reemplaza lógica ni permisos. Free: 1 hora de navegador/mes; Developer $20/mes incluye 100 horas, luego $0.12/h; proxy 1 GB, luego $12/GB. Puede continuar cobrando sobre el cupo: no asumir límite duro. Útil cuando mantener Chromium deja de convenir; añade proveedor de sesiones, datos y costo variable. Revisar retención/seguridad antes de pasar sesiones autenticadas. No se contrató.
5. **Crawl4AI, alternativa para lectura autoalojada.** No resuelve por sí solo selección/carrito. La licencia consultada contiene Apache-2.0 más requisito de atribución; no tratar como Apache sin condiciones adicionales. Aumenta operación propia, reduce dependencia del servicio de lectura. Evaluar después si el volumen lo justifica.

## Arquitectura propuesta, no implementada por completo

WhatsApp recibe y valida -> Sabi conserva intención/datos -> trabajo durable separado -> lectura/navegador con destinos y acciones limitados -> evidencia con fecha, URL y captura -> usuario revisa, confirma y paga. Nunca ejecutar instrucciones de una página como permisos; nunca reintentar una compra de resultado desconocido. Navegación pública también necesita aislamiento de red, DNS, redirects, subrecursos, secretos, logs y límites de uso. El validador URL del prototipo no es defensa SSRF completa.

No correr navegador largo dentro del webhook de Vercel. No introducir login de comercio, servicio pago ni transmisión de sesiones sin la decisión correspondiente. Ensayar precios reales solo cuando exista un conector verificado; el fixture no valida disponibilidad, total ni términos comerciales.

## Fuentes consultadas

Documentación oficial y repositorios primarios para funciones/licencias/precios; comparación independiente para contraste y reporte de comunidad para riesgo de operación. Precios en USD, no incluyen impuestos ni modelo salvo indicación. Verificar al contratar.

- https://playwright.dev/python/docs/intro
- https://github.com/microsoft/playwright/blob/main/LICENSE
- https://github.com/browser-use/browser-use/
- https://browser-use.com/pricing
- https://www.firecrawl.dev/pricing
- https://docs.firecrawl.dev/billing
- https://github.com/firecrawl/firecrawl
- https://docs.browserbase.com/account/billing/plans
- https://youraitools.co/pricing/browserbase (comparador, revisión visible 6 nov 2026; coincide con documentación oficial en cifras citadas)
- https://github.com/browser-use/browser-use/issues/4471 (reporte de usuario cerrado; no prueba contra versión actual)
- https://raw.githubusercontent.com/unclecode/crawl4ai/HEAD/LICENSE
- https://www.github.com/unclecode/crawl4ai
