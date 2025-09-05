# Telegram SMS Bot (Postgres + Redis) - Minimal Starter

Este ZIP contiene una **versión funcional mínima** del bot solicitado, usando:
- Python (python-telegram-bot)
- PostgreSQL (docker-compose service `db`)
- Redis + RQ (docker-compose service `redis` & `worker`)
- FastAPI admin (service `web`)

**Objetivo:** darte un repo listo para levantar en Docker (local/Render) y empezar a probar los flujos principales. 
Incluye scripts de inicialización de la BD (db/init.sql) para crear tablas básicas.

---
## Cómo usar (Docker, recomendado)

1. Copia el archivo `.env.example` a `.env` y ajusta variables.
2. Levanta los servicios: `docker-compose up --build`
3. Espera a que `db` y `redis` estén listos. El bot se conectará automáticamente.

## Rutas y comandos importantes
- Bot: usa `BOT_TOKEN` del .env
- Panel admin: `http://localhost:8000` (FastAPI)
- Worker RQ: procesa tareas en background (timeouts)

## Notas
- Este es un starter: implementa flujos básicos (crear orden, aceptar con captcha, recarga con comprobante) y la integración con Postgres/Redis.
- Te enseñaré paso a paso el uso de PostgreSQL y Redis si quieres (comandos, psql, redis-cli).
