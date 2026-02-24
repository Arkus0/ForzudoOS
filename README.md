# ForzudoOS 🏋️

Sistema híbrido de recordatorios inteligentes + dashboard para forzudos.

## ¿Qué es?

Un sistema que entiende recordatorios en lenguaje natural y los enriquece con contexto de tu entrenamiento:

- **Parser NL**: Entiende frases como "avísame si no entreno en 48h"
- **Context Engine**: Consulta tus datos de Notion antes de avisarte
- **Scheduler**: Cron jobs que verifican condiciones
- **Dashboard**: Vista unificada (próximamente)
- **Telegram Bot**: Interacción rápida (próximamente)

## Instalación

```bash
# Clonar
git clone https://github.com/Arkus0/ForzudoOS.git
cd ForzudoOS

# Instalar dependencias
uv sync --all-groups

# Configurar variables de entorno
export NOTION_TOKEN="tu-token-de-notion"
export NOTION_531_LOGBOOK_DB="id-de-tu-base-de-datos"
```

## Uso

### CLI

```bash
# Ver estado actual
uv run forzudo status

# Parsear una frase (sin crear recordatorio)
uv run forzudo parse "avísame si no he entrenado en 48h"

# Crear un recordatorio
uv run forzudo recordar "avísame del deload 3 días antes"

# Ejecutar checks
uv run forzudo check
```

### Ejemplos de frases soportadas

| Frase | Qué hace |
|-------|----------|
| "avísame si no he entrenado en 48h" | Check cada 6h, alerta si >48h sin entreno |
| "avísame del deload 3 días antes" | Aviso cuando queden 3 días para deload |
| "qué toca hoy" | Muestra próximo entreno con pesos |

## Arquitectura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Parser    │────>│  Scheduler  │────>│    Cron     │
│     NL      │     │             │     │   Jobs      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                        ┌──────────────────────┘
                        ▼
               ┌─────────────────┐
               │  Context Engine │
               │  (Notion API)   │
               └─────────────────┘
```

## Desarrollo

```bash
# Tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .

# Type check
uv run ty check src/
```

## Roadmap

- [x] Parser NL básico
- [x] Integración Notion
- [x] Scheduler con cron jobs
- [ ] Dashboard GitHub Pages
- [ ] Telegram Bot
- [ ] Integración con Juan-Training app

## Stack

- Python 3.11+
- uv (gestión de dependencias)
- ruff (lint/format)
- ty (type checking)
- pytest (testing)

---

*Para forzudos que odian las apps genéricas.*
