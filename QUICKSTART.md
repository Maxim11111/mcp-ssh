# Quick Start Guide

## 1. Запуск сервера

```bash
# Скопировать конфигурацию окружения
cp .env.example .env

# При необходимости изменить настройки (например, порт)
# nano .env

# Запустить Docker контейнер
docker compose up -d

# Проверить что сервер работает
curl http://localhost:8000/health
```

**Примечание:** По умолчанию сервер запускается на порту 8000. Чтобы изменить внешний порт, отредактируйте файл `.env` и установите `EXTERNAL_PORT=9000` (или любой другой порт).

## 2. Создание токена

```bash
# Создать токен для Cursor
docker exec -it mcp-ssh-server python -m src.cli token create

# Скопируйте сгенерированный токен (например: tok_145608d0c54d4501b504d2468bc9599e)
```

## 3. Добавление сервера

```bash
# Добавить сервер через CLI
docker exec -it mcp-ssh-server python -m src.cli server add

# Следуйте интерактивным подсказкам:
# - Server name: node2
# - Hostname: 192.168.10.10
# - SSH Port: 22
# - SSH Username: ubuntu
# - Description: My Server
# - Tags: production,web
```

CLI автоматически:
- Сгенерирует ED25519 SSH ключ
- Подключится к серверу по паролю
- Установит публичный ключ в `~/.ssh/authorized_keys`
- Проверит беспарольное подключение

## 4. Настройка Cursor

Создайте/измените файл `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ssh-devops": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

**Замените** `YOUR_TOKEN_HERE` на токен из шага 2.

**Примечание:** Если вы изменили порт в `.env` файле, используйте соответствующий URL в конфигурации Cursor.

## 5. Перезапустите Cursor

После перезапуска Cursor увидит MCP сервер и вы сможете:

### Доступные команды:

1. **Выполнить команду на сервере**
   ```
   @ssh-devops execute_command на node2: df -h
   ```

2. **Выполнить на нескольких серверах**
   ```
   @ssh-devops execute_on_multiple на prod-*: uptime
   ```

3. **Прочитать файл**
   ```
   @ssh-devops read_file /etc/nginx/nginx.conf с node2
   ```

4. **Записать файл**
   ```
   @ssh-devops write_file /tmp/test.txt на node2
   ```

5. **Список серверов**
   ```
   @ssh-devops list_servers
   ```

6. **Информация о системе**
   ```
   @ssh-devops get_system_info node2
   ```

7. **Проверить сервис**
   ```
   @ssh-devops check_service_status nginx на node2
   ```

8. **Установить пакет**
   ```
   @ssh-devops install_package docker.io на node2
   ```

## Проверка работы

### Тест из командной строки:

```bash
# Initialize
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }' | jq

# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }' | jq

# Call tool
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "list_servers"
    }
  }' | jq
```

## Управление серверами

```bash
# Список серверов
docker exec -it mcp-ssh-server python -m src.cli server list

# Включить/отключить сервер
docker exec -it mcp-ssh-server python -m src.cli server enable node2
docker exec -it mcp-ssh-server python -m src.cli server disable node2

# Удалить сервер
docker exec -it mcp-ssh-server python -m src.cli server remove node2
```

## Управление токенами

```bash
# Список токенов
docker exec -it mcp-ssh-server python -m src.cli token list

# Включить/отключить токен
docker exec -it mcp-ssh-server python -m src.cli token enable cursor-admin
docker exec -it mcp-ssh-server python -m src.cli token disable cursor-admin

# Отозвать токен
docker exec -it mcp-ssh-server python -m src.cli token revoke cursor-admin
```

## Логи

```bash
# Просмотр логов сервера
docker compose logs -f mcp-ssh-server

# Аудит логи
docker exec mcp-ssh-server tail -f /app/logs/audit.log

# Основные логи
docker exec mcp-ssh-server tail -f /app/logs/mcp-ssh.log
```

## Troubleshooting

### Cursor не видит MCP сервер

1. Проверьте что сервер работает: `curl http://localhost:8000/health`
2. Проверьте токен в `~/.cursor/mcp.json`
3. Перезапустите Cursor полностью
4. Проверьте логи: `docker compose logs mcp-ssh-server`

### SSH подключение не работает

1. Проверьте что ключ создан: `ls -la keys/`
2. Проверьте конфигурацию: `docker exec mcp-ssh-server cat /app/config/servers.json`
3. Тест SSH вручную: `ssh -i keys/node2_ed25519 ubuntu@192.168.10.10`

### Ошибки прав доступа

```bash
# Исправить права на ключи
chmod 600 keys/*_ed25519
chmod 644 keys/*.pub
```

## Продакшн развертывание

Для продакшна используйте HTTPS через nginx-proxy-manager:

```json
{
  "mcpServers": {
    "ssh-devops": {
      "url": "https://mcp.yourcompany.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_PRODUCTION_TOKEN"
      }
    }
  }
}
```

Подробнее см. [DEPLOYMENT.md](DEPLOYMENT.md)

## Конфигурация через .env

Все настройки сервера можно изменить через файл `.env`:

```bash
# Основные настройки
HOST=0.0.0.0                    # Адрес привязки
PORT=8000                        # Внутренний порт контейнера
EXTERNAL_PORT=8000               # Внешний порт Docker хоста

# Безопасность
SECRET_KEY=your-secret-key       # Измените в продакшене!
TOKEN_EXPIRY_HOURS=8760         # Срок действия токенов

# Ограничения скорости
RATE_LIMIT_PER_MINUTE=60        # Запросов в минуту
RATE_LIMIT_PER_HOUR=500         # Команд в час

# SSH настройки
SSH_CONNECTION_TIMEOUT=30       # Таймаут SSH подключения
SSH_COMMAND_TIMEOUT=300         # Таймаут выполнения команд
```

### Примеры конфигурации

**Изменение порта:**
```bash
# В .env файле
EXTERNAL_PORT=9000

# Тогда в Cursor используйте:
# "url": "http://localhost:9000/mcp"
```

**Увеличение лимитов:**
```bash
# В .env файле
RATE_LIMIT_PER_MINUTE=120
RATE_LIMIT_PER_HOUR=1000
```

**Отладка:**
```bash
# В .env файле
DEBUG=true
LOG_LEVEL=DEBUG
```

## Reverse Proxy (Продакшн)

Для продакшн развертывания с reverse proxy:

### nginx-proxy-manager

```bash
# Использовать proxy compose файл
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

### Traefik

```bash
# Использовать proxy compose файл
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

### Кастомные сети

```bash
# Создать сети
docker network create proxy-network
docker network create monitoring-network

# Использовать proxy compose файл
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```




