# MCP Protocol Implementation

## Поддерживаемые транспорты

### 1. HTTP JSON-RPC (Основной, рекомендуется)

**Endpoint:** `POST /mcp`

Используется для Cursor и других MCP клиентов с поддержкой HTTP.

**Пример запроса:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "METHOD_NAME",
    "params": {...}
  }'
```

### 2. SSE (Server-Sent Events) - Legacy

**Endpoints:** 
- `GET /sse` - Открыть SSE соединение
- `POST /messages?sessionId=XXX` - Отправить сообщение

Поддерживается для обратной совместимости.

## Методы JSON-RPC

### initialize

Инициализация MCP сессии.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "cursor",
      "version": "1.0.0"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {},
      "resources": {},
      "prompts": {}
    },
    "serverInfo": {
      "name": "mcp-ssh-server",
      "version": "0.1.0",
      "protocol_version": "1.0.0"
    }
  }
}
```

### tools/list

Получить список доступных инструментов.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "execute_command",
        "description": "Execute a shell command on a remote server",
        "inputSchema": {
          "type": "object",
          "properties": {
            "server": {"type": "string"},
            "command": {"type": "string"},
            "timeout": {"type": "integer", "default": 300}
          },
          "required": ["server", "command"]
        }
      }
      // ... другие инструменты
    ]
  }
}
```

### tools/call

Вызвать инструмент.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "server": "prod-web-01",
      "command": "df -h",
      "timeout": 30
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"success\": true, \"output\": \"...\"}"
      }
    ],
    "isError": false
  }
}
```

### resources/list

Получить список ресурсов (пока не реализовано).

### prompts/list

Получить список промптов (пока не реализовано).

## Доступные инструменты

### 1. execute_command

Выполнить команду на сервере.

```json
{
  "name": "execute_command",
  "arguments": {
    "server": "prod-web-01",
    "command": "systemctl status nginx",
    "timeout": 30
  }
}
```

### 2. execute_on_multiple

Выполнить команду на нескольких серверах параллельно.

```json
{
  "name": "execute_on_multiple",
  "arguments": {
    "servers": ["prod-*", "test-web-01"],
    "command": "uptime",
    "timeout": 60
  }
}
```

### 3. read_file

Прочитать файл с сервера.

```json
{
  "name": "read_file",
  "arguments": {
    "server": "prod-web-01",
    "file_path": "/etc/nginx/nginx.conf"
  }
}
```

### 4. write_file

Записать файл на сервер.

```json
{
  "name": "write_file",
  "arguments": {
    "server": "prod-web-01",
    "file_path": "/tmp/test.txt",
    "contents": "Hello World",
    "mode": "overwrite"
  }
}
```

### 5. list_directory

Список файлов в директории.

```json
{
  "name": "list_directory",
  "arguments": {
    "server": "prod-web-01",
    "path": "/var/log",
    "detailed": true
  }
}
```

### 6. check_service_status

Проверить статус systemd сервиса.

```json
{
  "name": "check_service_status",
  "arguments": {
    "server": "prod-web-01",
    "service_name": "nginx"
  }
}
```

### 7. install_package

Установить пакет через package manager.

```json
{
  "name": "install_package",
  "arguments": {
    "server": "prod-web-01",
    "package_name": "htop",
    "package_manager": "auto"
  }
}
```

### 8. list_servers

Список доступных серверов.

```json
{
  "name": "list_servers",
  "arguments": {
    "tag": "production"
  }
}
```

### 9. get_system_info

Получить информацию о системе.

```json
{
  "name": "get_system_info",
  "arguments": {
    "server": "prod-web-01"
  }
}
```

## Аутентификация

Все запросы требуют Bearer токен в заголовке:

```http
Authorization: Bearer tok_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Токены управляются через CLI:

```bash
# Создать токен
docker exec -it mcp-ssh-server python -m src.cli token create

# Список токенов
docker exec -it mcp-ssh-server python -m src.cli token list

# Отключить токен
docker exec -it mcp-ssh-server python -m src.cli token disable TOKEN_NAME
```

## Rate Limiting

- Лимиты задаются в `config/servers.json` в секции `security.rate_limit` (requests_per_minute, commands_per_hour).
- В `config/tokens.json` для каждого токена задаётся `rate_limit_multiplier` (множитель к базовым лимитам).
- По умолчанию: 60 запросов/минуту, 500 команд/час.

## Безопасность

1. **SSH ключи** - используются ED25519 ключи без пароля
2. **Токены** - SHA-256 хэш с солью
3. **Аудит** - все команды логируются в `logs/audit.log`
4. **Permissions** - токены имеют ограничения на серверы и команды
5. **Timeout** - все SSH команды имеют таймаут (по умолчанию 300 сек)

## Логирование

### Аудит лог (`logs/audit.log`)
```json
{
  "timestamp": "2025-10-13T12:00:00",
  "token_name": "cursor-admin",
  "action": "execute_command",
  "server": "prod-web-01",
  "command": "ls -la",
  "success": true,
  "duration": 0.5
}
```

### Основной лог (`logs/mcp-ssh.log`)
Стандартный Python logging формат с уровнями:
- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

## Cursor Integration

### Конфигурация `~/.cursor/mcp.json`

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

### Использование в Cursor

В чате Cursor:
```
@ssh-devops выполни команду df -h на сервере prod-web-01
```

Cursor автоматически:
1. Вызовет `tools/list` для получения доступных команд
2. Выберет подходящий tool (`execute_command`)
3. Сформирует правильные аргументы
4. Отобразит результат

## Примеры использования

### Пример 1: Проверка диска
```
@ssh-devops проверь свободное место на всех production серверах
```

Cursor вызовет:
```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_on_multiple",
    "arguments": {
      "servers": ["prod-*"],
      "command": "df -h /"
    }
  }
}
```

### Пример 2: Обновление конфигурации
```
@ssh-devops обнови nginx конфиг на prod-web-01, добавь gzip compression
```

Cursor:
1. Прочитает текущий конфиг: `read_file`
2. Модифицирует его
3. Запишет обратно: `write_file`
4. Перезагрузит nginx: `execute_command`

### Пример 3: Установка софта
```
@ssh-devops установи Docker на test-web-01
```

Cursor вызовет:
```json
{
  "method": "tools/call",
  "params": {
    "name": "install_package",
    "arguments": {
      "server": "test-web-01",
      "package_name": "docker.io"
    }
  }
}
```

## Troubleshooting

### Ошибка: Method not found
- Проверьте правильность написания метода
- Используйте `initialize`, `tools/list`, `tools/call`

### Ошибка: Invalid token
- Проверьте токен в конфигурации
- Убедитесь что токен не отключен: `docker exec -it mcp-ssh-server python -m src.cli token list`

### Ошибка: Server not found
- Проверьте список серверов: `docker exec -it mcp-ssh-server python -m src.cli server list`
- Убедитесь что сервер включен (enabled: true)

### SSH connection failed
- Проверьте SSH ключи: `ls -la keys/`
- Тест вручную: `ssh -i keys/SERVER_ed25519 USER@HOST`
- Проверьте что публичный ключ установлен на сервере

## Расширение функционала

Для добавления нового tool:

1. Добавьте метод в `src/mcp_tools.py`
2. Зарегистрируйте в `TOOLS_REGISTRY`
3. Перезапустите сервер

Пример:
```python
async def my_custom_tool(
    token_config: TokenConfig,
    server: str,
    **kwargs
) -> Dict[str, Any]:
    # Ваша логика
    return {"success": True, "result": "..."}

TOOLS_REGISTRY["my_custom_tool"] = {
    "function": my_custom_tool,
    "schema": {
        "name": "my_custom_tool",
        "description": "...",
        "inputSchema": {...}
    }
}
```




