# ForzudoOS - Roadmap
## Sistema híbrido de recordatorios inteligentes + dashboard

---

## Fase 1: Fundación ✅ COMPLETADA
**Objetivo:** Repo creado, estructura moderna Python, parser NL básico

- [x] Explorar repos existentes (BBD Analytics, Juan-Calendar, Juan-Training)
- [x] Crear repo `ForzudoOS` privado en GitHub
- [x] Setup proyecto Python moderno (uv, ruff, ty)
- [x] Diseñar arquitectura de datos (estado del sistema)
- [x] Implementar parser NL v0.1 (frases básicas)
- [x] Crear estructura de recordatorios (triggers, contexto, acciones)

**Entregable:** Repo funcional con parser que entienda "avísame si no entreno en 48h" ✅

---

## Fase 2: Integración Notion ✅ COMPLETADA
**Objetivo:** Leer datos de entrenos y crear contexto enriquecido

- [x] Crear módulo `forzudo.notion` con bases de datos **independientes** de BBD
- [x] Crear DBs propias: Recordatorios + Entrenos
- [x] Implementar `ContextEngine` con cálculos 5/3/1 propios
- [x] Comando `setup` para crear estructura en Notion
- [x] Comando `sync` para recibir datos de BBD (sin tocarlo)

**Entregable:** Sistema con bases de datos propias en Notion ✅

---

## Fase 3: Sistema de Cron Jobs ✅ COMPLETADA
**Objetivo:** Recordatorios programados que se ejecuten solos

- [x] Diseñar schema de cron jobs
- [x] Implementar `cron_manager.py` con integración OpenClaw
- [x] Crear 3 jobs iniciales:
  - **Check Workouts**: cada 6h verifica si hay recordatorios pendientes
  - **Daily Summary**: cada día a las 7am (Europe/Madrid)
  - **Deload Warning**: cada día verifica proximidad de deload
- [x] Comandos CLI: `cron list`, `cron export`, `cron register`
- [x] Jobs registrados y activos en OpenClaw Cron

**Entregable:** 3 cron jobs activos que ejecutan checks automáticos ✅

---

## Fase 4: Dashboard GitHub Pages ✅ COMPLETADA
**Objetivo:** Vista unificada web, privada, en tu repo

- [x] Crear estructura HTML/JS vanilla (sin frameworks pesados)
- [x] Página principal con:
  - Estado del mesociclo 5/3/1 (gráfico visual)
  - Próximo entreno (qué toca, pesos esperados)
  - Alertas activas (lo que necesita atención)
  - Calendario semanal
  - Stats rápidas
- [x] Tema oscuro, diseño minimalista
- [x] Dashboard generator: crea data.json desde Python
- [x] Responsive (mobile-first)
- [x] Documentado: local server o GitHub Pages (requiere Pro para privados)

**Entregable:** Dashboard funcional en `docs/` ✅

---

## Fase 5: Telegram Bot Integration ✅ COMPLETADA
**Objetivo:** Interacción rápida sin entrar al dashboard

- [x] 8 comandos implementados:
  - `/hoy` - Qué toca hoy (con pesos)
  - `/estado` - Resumen del ciclo
  - `/hecho` - Marcar entreno completado
  - `/manana` - Mover entreno a mañana
  - `/recordar [frase]` - Crear recordatorio con NL
  - `/alertas` - Ver alertas activas
  - `/pesos` - Ver pesos esperados
  - `/ayuda` - Mostrar ayuda
- [x] Respuestas enriquecidas con contexto (Markdown)
- [x] Soporte para lenguaje natural (sin comandos)
- [x] CLI para probar respuestas: `forzudo bot [mensaje]`
- [x] Webhook handler para integración con Telegram API

**Entregable:** Bot funcional con comandos útiles ✅

---

## Fase 6: Polish & Extras (Día 7+)
**Objetivo:** Sistema completo, robusto, con extras

- [ ] Tests automatizados
- [ ] Manejo de errores y retries
- [ ] Logging y monitoreo
- [ ] Integración con Juan-Training (app Flutter)
- [ ] Predicciones: "Basado en tu progreso, en 4 semanas tu TM debería ser..."
- [ ] Gamificación: streaks, logros, comparativa vs tiempos anteriores

**Entregable:** Sistema production-ready

---

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Lenguaje | Python 3.11+ |
| Gestión deps | uv |
| Lint/Format | ruff |
| Type check | ty |
| Testing | pytest |
| Datos | Notion API (ya configurado) |
| Scheduler | OpenClaw cron |
| Frontend | HTML/JS vanilla |
| Hosting | GitHub Pages (privado) |
| Comunicación | Telegram Bot |

---

## Notas

- **Reutilización máxima:** Copiar/adaptar de `bbd-analytics` todo lo posible
- **Privacidad:** Repo privado, datos sensibles en secrets
- **Escalabilidad:** Diseñar para que sea fácil añadir nuevos tipos de recordatorios
- **UX:** Mejor un sistema simple que funcione que uno complejo que no

---

*Creado: 2025-02-25*
*Estado: MVP COMPLETADO* ✅

## Resumen

ForzudoOS está listo para usar. Tiene:
- ✅ Parser NL que entiende recordatorios
- ✅ Integración Notion con bases de datos propias
- ✅ 3 cron jobs activos en OpenClaw
- ✅ Dashboard HTML funcional
- ✅ Telegram Bot con 8 comandos

## Próximos pasos (opcionales)

- [ ] Sincronización automática desde BBD Analytics
- [ ] Gamificación (streaks, logros)
- [ ] Predicciones de progreso
- [ ] App móvil (Flutter)
