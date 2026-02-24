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

## Fase 3: Sistema de Cron Jobs (Día 3)
**Objetivo:** Recordatorios programados que se ejecuten solos

- [ ] Diseñar schema de cron jobs (qué guardar, cómo activar)
- [ ] Implementar `forzudo.scheduler` con OpenClaw cron
- [ ] Crear jobs iniciales:
  - Check entreno cada 6h (alerta si >48h sin entrenar)
  - Aviso deload 3 días antes
  - Recordatorio día de entreno (mañana)
- [ ] Sistema de "snooze" y "completado"

**Entregable:** Primer cron job activo que me avise por Telegram

---

## Fase 4: Dashboard GitHub Pages (Día 4-5)
**Objetivo:** Vista unificada web, privada, en tu repo

- [ ] Crear estructura HTML/JS vanilla (sin frameworks pesados)
- [ ] Página principal con:
  - Estado del mesociclo 5/3/1 (gráfico visual)
  - Próximo entreno (qué toca, pesos esperados)
  - Alertas activas (lo que necesita atención)
  - Citas/tareas del día (integración con Juan-Calendar)
- [ ] Deploy en GitHub Pages (privado, acceso solo tuyo)
- [ ] Tema oscuro, diseño minimalista

**Entregable:** URL funcional con dashboard personal

---

## Fase 5: Telegram Bot Integration (Día 6)
**Objetivo:** Interacción rápida sin entrar al dashboard

- [ ] Comandos:
  - `/hoy` - Qué toca hoy
  - `/estado` - Resumen del ciclo
  - `/hecho` - Marcar entreno completado
  - `/manana` - Mover entreno a mañana
  - `/recordar [frase]` - Crear recordatorio con NL
- [ ] Respuestas enriquecidas con contexto
- [ ] Callbacks para acciones rápidas (botones)

**Entregable:** Bot funcional con comandos útiles

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
*Fase actual: 3 (Cron Jobs)*
