# Cobertura de la entrega

| Área | Implementado | Límite explícito |
|---|---|---|
| FOCUS / DuckDB | CSV directo, SHA-256, deduplicación de identidad, rollback, filtros UTC/moneda/cliente | Esquema FOCUS de los docs; sin conectores cloud |
| KPIs | Catálogo de 13 métricas con fórmulas y enlaces | Faltantes se marcan no disponibles; sin libro de repartos |
| LangGraph | 5 especialistas declarativos, runner compartido, orden causal y SSE | Nodos secuenciales para evitar escrituras concurrentes del estado |
| Memoria | Entidades/pasajes, Personalized PageRank, grafos canónico y por cliente | Implementación local inspirada en Dual HippoRAG; sin dependencia de investigación |
| Tickets | 6 estados, feedback, huella determinista, ledger tipado, Markdown y grafo durable | Recuperación al reiniciar para proyecciones de archivos |
| Forecast y baseline | Run rate EOM ajustado, escenario trimestral, propuesta de presupuesto y holdback | Sin estacionalidad, backtesting o drivers inferidos automáticamente |
| LLM | Factory Anthropic/OpenAI/Vertex y fallback determinista sin claves | Adaptadores externos sin verificación con credenciales reales |
| UI | Resumen, orquestador, KPIs, kanban, reportes, cliente/datos | App local sin cuentas multiusuario |
| Datos demo | 60 filas, 20 días, tres servicios, pico sintético de AI | Etiquetados como demostración |

## Validación ejecutada

- 30 pruebas pytest: SQL, idempotencia, atomicidad, memoria, contexto aprobado con caducidad,
  cinco especialistas, flujo onboarding/daily, feedback, API con SSE y lecturas concurrentes de dashboard.
- Ruff sin errores y mypy estricto sobre los 25 módulos Python.
- Build React/TypeScript/Vite de producción exitoso.
- Navegador móvil: 390 px, sin desbordamiento horizontal.
- Navegador: resumen, ejecución completa de los siete nodos, reporte y edición persistente de un ticket.
- Límites del repositorio: archivos de código de hasta 180 líneas, funciones Python de hasta 35 líneas.

Los documentos originales se conservan en `docs/`. No se ha publicado ni configurado un servicio remoto.
