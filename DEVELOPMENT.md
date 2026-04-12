# Development Guide

## Быстрая разработка без ребилдов

Код в `src/` теперь линкован через Docker volume, изменения применяются автоматически после перезапуска uvicorn внутри контейнера.

### Способ 1: Перезапуск контейнера (рекомендуется)

```bash
# Простой рестарт
docker compose restart

# Или с логами
docker compose restart && docker compose logs -f
```

### Способ 2: Hot reload (для быстрой разработки)

```bash
# Запустить с --reload флагом
docker compose down
docker compose up -d

# Или запустить напрямую с hot reload
docker exec -it mcp-ssh-server uvicorn src.server_http:create_app --factory \
  --host 0.0.0.0 --port 8000 --reload
```

## Директории

```
mcp-ssh/
├── src/              # Исходный код (volume, без ребилда!)
│   ├── server_http.py    # FastAPI + FastMCP Streamable HTTP + OAuth
│   ├── fastmcp_ssh_server.py  # Регистрация инструментов SDK
│   ├── mcp_oauth_provider.py  # Встроенный OAuth AS (логин по API token)
│   ├── server_stdio.py   # Stdio сервер для альтернативного транспорта
│   ├── mcp_handler.py    # MCP протокол логика
│   ├── mcp_tools.py      # Инструменты для DevOps
│   ├── ssh_manager.py    # SSH пул подключений
│   ├── command_executor.py # Выполнение команд
│   ├── config.py         # Конфигурация
│   ├── auth.py           # Аутентификация
│   ├── security.py       # Безопасность
│   ├── audit.py          # Аудит логирование
│   └── cli.py            # CLI менеджер
├── config/           # Конфигурация (volume)
│   ├── servers.json      # Список серверов
│   └── tokens.json       # API токены
├── keys/             # SSH ключи (volume)
│   └── server_ed25519    # ED25519 приватные ключи
├── logs/             # Логи (volume)
│   ├── mcp-ssh.log       # Основной лог
│   └── audit.log         # Аудит лог
└── docker-compose.yml    # Docker конфигурация
```

## Логирование

### Просмотр логов в реальном времени

```bash
# Все логи сервера
docker compose logs -f mcp-ssh-server

# Только аудит
docker exec mcp-ssh-server tail -f /app/logs/audit.log

# Основной лог
docker exec mcp-ssh-server tail -f /app/logs/mcp-ssh.log

# Фильтр по уровню
docker compose logs mcp-ssh-server | grep ERROR
docker compose logs mcp-ssh-server | grep WARNING
```

### Уровни логирования

```bash
# Изменить уровень (в docker-compose.yml)
environment:
  LOG_LEVEL: DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Перезапустить
docker compose restart
```

### Что логируется

1. **Все HTTP запросы** - метод, путь, клиент
2. **Авторизация** - успешная/неуспешная
3. **MCP запросы** - method, params, results
4. **SSH соединения** - open/close/errors
5. **Команды** - выполнение, результаты, ошибки
6. **Аудит** - кто, что, когда, результат

## Debugging

### 1. Проверка MCP endpoint

```bash
# GET /mcp - информация о сервере
curl http://localhost:8000/mcp | jq

# POST /mcp - JSON-RPC запрос
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }' | jq
```

### 2. Проверка авторизации

```bash
# Без токена - должно быть 401
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}'

# С неправильным токеном - должно быть 401
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer invalid_token" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}'

# С правильным токеном - должно быть 200
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer tok_145608d0c54d4501b504d2468bc9599e" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | jq
```

### 3. Проверка SSH подключений

```bash
# Список активных подключений
curl http://localhost:8000/health | jq '.ssh_connections'

# Тест SSH напрямую
docker exec mcp-ssh-server ssh -i /app/keys/node2_ed25519 ubuntu@192.168.10.10 "echo test"

# Проверка прав на ключи
docker exec mcp-ssh-server ls -la /app/keys/
```

### 4. Интерактивный Python shell

```bash
# Зайти в контейнер
docker exec -it mcp-ssh-server bash

# Запустить Python
python

# Импортировать модули
from src.config import Config
config = Config('/app/config')
print(config.servers)
print(config.tokens)
```

### 5. Проверка Cursor подключения

Смотрите логи когда Cursor пытается подключиться:

```bash
# В одном терминале - логи
docker compose logs -f mcp-ssh-server

# В другом терминале - рестарт Cursor
# Перезапустите Cursor и смотрите что происходит в логах
```

Ищите:
- `Incoming: POST /mcp` - запросы от Cursor
- `Authenticated as: XXX` - успешная авторизация
- `MCP Request from` - какие методы вызывает Cursor
- `400 Bad Request` или `401 Unauthorized` - ошибки

## Cursor не видит MCP сервер?

### Checklist:

1. **Сервер работает?**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Токен правильный?**
   ```bash
   # Проверьте ~/.cursor/mcp.json
   cat ~/.cursor/mcp.json
   
   # Проверьте что токен существует
   docker exec mcp-ssh-server python -m src.cli token list
   ```

3. **Формат конфигурации правильный?**
   ```json
   {
     "mcpServers": {
       "ssh-devops": {
         "url": "http://localhost:8000/mcp",
         "headers": {
           "Authorization": "Bearer tok_YOUR_TOKEN_HERE"
         }
       }
     }
   }
   ```

4. **Cursor перезапущен?**
   - Полностью закройте Cursor (Cmd+Q)
   - Перезапустите

5. **Логи показывают запросы?**
   ```bash
   docker compose logs -f mcp-ssh-server | grep "172.19"
   # Должны быть POST запросы от Cursor (IP может отличаться)
   ```

6. **Тестовый запрос работает?**
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Authorization: Bearer $(grep tok_ config/tokens.json | head -1 | cut -d'"' -f2)" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq
   ```

## Добавление нового инструмента

1. Открыть `src/mcp_tools.py`
2. Добавить функцию:

```python
async def my_new_tool(
    token_config: TokenConfig,
    server: str,
    my_param: str,
    **kwargs
) -> Dict[str, Any]:
    """My new tool description."""
    # Validate permissions
    if server not in token_config.allowed_servers and "*" not in token_config.allowed_servers:
        return {"success": False, "error": f"Access denied to server {server}"}
    
    # Your logic here
    result = do_something(server, my_param)
    
    return {
        "success": True,
        "result": result
    }
```

3. Зарегистрировать в `TOOLS_REGISTRY`:

```python
TOOLS_REGISTRY["my_new_tool"] = {
    "function": my_new_tool,
    "schema": {
        "name": "my_new_tool",
        "description": "My new tool description",
        "inputSchema": {
            "type": "object",
            "properties": {
                "server": {"type": "string", "description": "Server name"},
                "my_param": {"type": "string", "description": "My parameter"}
            },
            "required": ["server", "my_param"]
        }
    }
}
```

4. Перезапустить:
```bash
docker compose restart
```

5. Проверить:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools[] | select(.name=="my_new_tool")'
```

## Тестирование

```bash
# Запустить все тесты
docker exec mcp-ssh-server pytest

# Конкретный тест
docker exec mcp-ssh-server pytest tests/test_config.py

# С coverage
docker exec mcp-ssh-server pytest --cov=src tests/

# С verbose
docker exec mcp-ssh-server pytest -v
```

## Production deploy

См. [DEPLOYMENT.md](DEPLOYMENT.md) для настройки:
- HTTPS через nginx-proxy-manager
- Systemd service
- Мониторинг
- Backup

## Полезные команды

```bash
# Проверить синтаксис Python
docker exec mcp-ssh-server python -m py_compile src/server_http.py

# Проверить все файлы
docker exec mcp-ssh-server find src/ -name "*.py" -exec python -m py_compile {} \;

# Список всех серверов
docker exec mcp-ssh-server python -m src.cli server list

# Список всех токенов
docker exec mcp-ssh-server python -m src.cli token list

# Добавить новый сервер
docker exec -it mcp-ssh-server python -m src.cli server add

# Создать новый токен
docker exec -it mcp-ssh-server python -m src.cli token create

# Проверка конфигурации
docker exec mcp-ssh-server cat /app/config/servers.json | jq
docker exec mcp-ssh-server cat /app/config/tokens.json | jq

# Очистка SSH подключений
docker exec mcp-ssh-server python -c "from src.ssh_manager import get_connection_pool; import asyncio; asyncio.run(get_connection_pool().close_all_connections())"
```




