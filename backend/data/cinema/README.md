# Base de cartelera Markdown, preparación

Estado: NO activa en producción, sincronizador/cron no registrado y ningún DDL ejecutado en producción.

## Persistencia propuesta
La aplicación ya tiene SQLAlchemy y conexión Postgres/Supabase según `app/db.py`, pero se debe verificar el destino efectivo de producción y su cuota sin exponer credenciales antes de activar. Nueva tabla `cinema_snapshots`: única por proveedor/sede/fecha, payload validado y Markdown completo guardado en columnasText, fetched_at/expires_at. El archivo es una representación de la misma captura, no un informe separado. Exportar el Markdown persistido a descarga `.md`; conservar originales por fecha para revisión. El filesystem deVercel no es la base durable. No añadir almacenamiento externo ni contratación.

## Preparado y probado
`app/cinema_snapshot.py` implementa almacenamiento, exportaciónMarkdown y read-first `snapshot_first`. Una consulta fresca va a DB sin tocar proveedor; miss/caducada refresca una sola vez y guarda. Sólo consulta completa de misma sede/día con fuentes yfechas reemplaza dato bueno. Lista parcial/paginada, sede equivocada, fecha vieja o fallos no borran último dato bueno. Dato viejo permanece sólo comohistórico, nunca sirve una respuesta vigente. Horarios pasados se filtran incluso antes de caducidad.

Caduca al menor de24h desde fuente más antigua y medianoche local del día de funciones. Si proveedor usa caché, el reloj nace en lectura delproveedor, no en nuestra importación. Precaución:24h es política propuesta de cartelera diaria, no garantía delcine; consulta fresca a petición explícita, y precios/asientos/compras nunca usan esta base.

Semilla real incluida: `cinex/plaza-mayor/2026-11-17.md`, extraída03:31:43America/Caracas. No es cron en marcha. Los tests usan sólo SQLite y datos sintéticos.

## Activación pendiente, con decisión agrupada
Propuesta por contexto: piloto Oriente con PlazaMayorLechería, CinesUnidosReginaPuertoLaCruz y SupercinesPuenteRealBarcelona. Usuario no ha aprobado cobertura nacional. Regina tiene que implementar extractor oficial/adapter porque Cinve devuelve error actualmente; PlazaMayor ya posee fallback. Primero aceptar3sedes o elegir sóloPlazaMayor.

Actualización diaria propuesta09:00-09:59America/Caracas para funciones del mismo día; a esa hora tiene sentido cartelera actual y respeta precisiónHobby. CronVercel incluido enplan, pero cada ejecución consume funciones/DB/red. Sin modelo, saldoAPI ni WhatsApp. Falta verificar cuota actual y límite de coste deinfra efectiva. Tres sedes no implican tresHTTP: Supercines llama catálogo+una consulta por película; medimos antes de aceptar presupuesto. Si falta cartelera deunasede, marcar fallo y mantener histórico, no publicar lista vacía ni otrocine.

Todavía falta cablear servicio diario, endpoint privado autenticado cron/export, migración registrada/RLS, read-first al flujo real por sede resuelta, manejo concurrencia con UPSERT/lock, alertas fallo y retención acordada. La función preparada no cambia comportamiento deproducción por sísola. No activarla como si ya fuera basefuncionando. La cuota, cobertura yactivación deben cerrarse con el usuario.

Fuente límitescron verificada17nov2026: https://vercel.com/docs/cron-jobs/usage-and-pricing . Hobby:1vez/día,precisiónporhora, consumodefunción; no se promete coste0.
