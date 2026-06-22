# Oraciones de Prueba — Chat con Aura AI

## Requisitos previos

- apiEjemplo corriendo con DB conectada (`docker compose up -d`)
- Knowledge Base con `Manual_Motor1.pdf` indexado y activo
- Ambos módulos (Knowledge + DB) habilitados en el chat

---

## 1. Base de Datos — Ruta rápida (query_resource_data)

| # | Oración | Qué prueba |
|---|---------|------------|
| 1 | "Muéstrame los datos de temperatura del Motor1 de las últimas 6 horas" | `query_resource_data(resource="Motor1", metric="temperature", hours=6)` |
| 2 | "Necesito ver la vibración del Motor1 en las últimas 24 horas" | Métrica distinta (`vibration`) con ventana default |
| 3 | "Consulta los registros del Motor1 de la última semana" | Ventana 168h. Como los datos son de mayo 2025, cae en fallback a histórico completo |
| 4 | "Dame los últimos datos del Motor1" | Sin métrica — busca todas las métricas del recurso |

## 2. Base de Datos — NL2SQL (execute_data_query, ruta lenta)

| # | Oración | Qué prueba |
|---|---------|------------|
| 5 | "¿Cuál es el promedio de temperatura del Motor1?" | Forza `execute_data_query` (NL2SQL) porque query_resource_data no agrega |
| 6 | "¿Cuál fue la temperatura máxima registrada del Motor1?" | NL2SQL con agregación + posiblemente sin filtro de tiempo |
| 7 | "¿Cuántos registros hay del Motor1 con vibración mayor a 0.08 mm/s?" | NL2SQL con filtro numérico |
| 8 | "Compara la temperatura promedio de los primeros 15 días de mayo vs los últimos 15" | NL2SQL complejo — agrupación temporal |

## 3. Base de Datos — Exploración de schema

| # | Oración | Qué prueba |
|---|---------|------------|
| 9 | "Lista las bases de datos disponibles" | `list_db_connections` |
| 10 | "Muéstrame el esquema de la base de datos" | `retrieve_relevant_schema` o `db_schema` |

## 4. RAG — Búsqueda de documentación

| # | Oración | Qué prueba |
|---|---------|------------|
| 11 | "Busca información sobre los límites de operación del Motor1" | RAG busca en `Manual_Motor1.pdf` — debe encontrar umbrales |
| 12 | "¿Qué dice la documentación sobre los umbrales críticos de vibración?" | RAG con keywords específicas |
| 13 | "¿Hay documentación sobre procedimientos de mantenimiento?" | RAG — posible miss si el manual no cubre mantenimiento |
| 14 | "¿Cuál es el consumo energético recomendado según el manual?" | RAG — prueba de pregunta que el manual puede no cubrir |

## 5. Combinadas — DB + RAG en paralelo

| # | Oración | Qué prueba |
|---|---------|------------|
| 15 | "Tengo datos del Motor1. Comparalos con los límites del manual y decime si está operando correctamente" | Dispatcher a db_analyst-agent y rag-agent en paralelo |
| 16 | "¿El Motor1 está fuera de especificación? Revisá los datos de la última hora y la documentación" | Análisis cruzado — DB da los valores, RAG da los umbrales |

## 6. Razonamiento directo (sin herramientas)

| # | Oración | Qué prueba |
|---|---------|------------|
| 17 | "Convierte 150 grados Celsius a Fahrenheit" | Respuesta directa, sin delegar a ningún agente |
| 18 | "Explicame qué es la desviación estándar" | Conocimiento general, sin herramientas |

## 7. Stress / Edge Cases

| # | Oración | Qué prueba |
|---|---------|------------|
| 19 | "Quiero ver los datos del Motor1 de los últimos 5 minutos" | Ventana muy corta — probablemente sin datos |
| 20 | "Consultá los registros del recurso Z999" | Recurso inexistente — debe reportar "sin datos" |
| 21 | "Dame todos los datos de todas las tablas" | NL2SQL sin WHERE — debe aplicar LIMIT automáticamente |

---

## Cómo ejecutar las pruebas

1. Abrí el chat en `http://localhost/chat`
2. Asegurate de que Knowledge Base y DB están seleccionados en los toggles del chat
3. Pegá una oración y observá:
   - Si usa `query_resource_data` (<1s) o `execute_data_query` (~5-15s)
   - Si el RAG devuelve citas del PDF
   - Si la respuesta final sintetiza correctamente
4. Alterná entre secciones para cubrir todos los flujos

## Resultados esperados

| Sección | Comportamiento esperado |
|---------|------------------------|
| 1 (query_resource_data) | Respuesta en <3s con tabla de datos. Agente llama una sola tool. |
| 2 (execute_data_query) | Respuesta en 10-20s. Varias llamadas (schema → SQL → execute → interpret). |
| 3 (Schema) | Lista conexiones, tablas y columnas. |
| 4 (RAG) | Citas textuales del PDF con fuente y relevancia. |
| 5 (Combinadas) | Dispatcher a 2 agentes. Respuesta sintetizada con datos + referencias al manual. |
| 6 (Razonamiento) | Respuesta inmediata, sin tool calls. |
| 7 (Edge) | Sin datos o error claro, sin crasheos. |
