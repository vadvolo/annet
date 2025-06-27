# Annet REST API

REST API для приложения annet предоставляет HTTP endpoints для выполнения команд ann get, ann diff, ann patch и ann deploy через веб-интерфейс.

## Установка

Для работы REST API необходимо установить дополнительные зависимости:

```bash
pip install -r requirements-api.txt
```

## Запуск сервера

### Через CLI команду

```bash
# Запуск с параметрами по умолчанию (host=127.0.0.1, port=8000)
python -m annet rest-api

# Запуск с кастомными параметрами
python -m annet rest-api --host 0.0.0.0 --port 8080 --log-level DEBUG

# Запуск в режиме разработки с автоперезагрузкой
python -m annet rest-api --reload
```

### Прямой запуск модуля

```bash
python -m annet.rest_api --host 0.0.0.0 --port 8080
```

## API Endpoints

### Базовые endpoints

- `GET /` - Информация о сервисе
- `GET /health` - Проверка здоровья сервиса
- `GET /docs` - Автоматически сгенерированная документация Swagger UI
- `GET /redoc` - Альтернативная документация ReDoc

### Основные endpoints

#### `GET /api/v1/devices`

Получить список устройств по запросу.

**Параметры запроса:**
- `query` (обязательный) - список запросов для поиска устройств
- `hosts_range` (опциональный) - диапазон хостов

**Пример:**
```bash
curl "http://localhost:8000/api/v1/devices?query=router1&query=router2"
```

#### `POST /api/v1/gen`

Генерация конфигурации для устройств (аналог команды `ann gen`).

**Тело запроса:**
```json
{
  "query": ["router1", "router2"],
  "hosts_range": "10",
  "config": "running",
  "allowed_gens": ["hostname", "lldp"],
  "no_acl": false,
  "parallel": 2
}
```

#### `POST /api/v1/diff`

Показать diff конфигурации (аналог команды `ann diff`).

**Тело запроса:**
```json
{
  "query": ["router1"],
  "config": "running",
  "show_rules": true,
  "no_collapse": false
}
```

#### `POST /api/v1/patch`

Генерация патча для устройств (аналог команды `ann patch`).

**Тело запроса:**
```json
{
  "query": ["router1"],
  "config": "running",
  "add_comments": true
}
```

#### `POST /api/v1/deploy`

Деплой конфигурации на устройства (аналог команды `ann deploy`).

**Тело запроса:**
```json
{
  "query": ["router1"],
  "config": "running",
  "no_ask_deploy": true,
  "dont_commit": false,
  "rollback": false
}
```

## Модели данных

### DeviceQuery

```json
{
  "query": ["string"],
  "hosts_range": "string"
}
```

### GenerationOptions

```json
{
  "config": "running",
  "allowed_gens": ["string"],
  "excluded_gens": ["string"],
  "force_enabled": ["string"],
  "no_acl": false,
  "acl_safe": false,
  "filter_acl": "",
  "filter_ifaces": ["string"],
  "filter_peers": ["string"],
  "filter_policies": ["string"],
  "parallel": 1,
  "tolerate_fails": false,
  "annotate": false,
  "indent": "  "
}
```

### ApiResponse

```json
{
  "success": true,
  "message": "string",
  "data": {},
  "errors": ["string"]
}
```

## Примеры использования

### Python

```python
import requests
import json

# Базовый URL API
base_url = "http://localhost:8000"

# Получить список устройств
response = requests.get(f"{base_url}/api/v1/devices", params={
    "query": ["router1", "router2"]
})
devices = response.json()

# Сгенерировать конфигурацию
gen_request = {
    "query": ["router1"],
    "config": "running",
    "allowed_gens": ["hostname"],
    "parallel": 1
}

response = requests.post(f"{base_url}/api/v1/gen", json=gen_request)
result = response.json()

if result["success"]:
    for item in result["data"]:
        print(f"Device: {item['device']}")
        print(f"Config:\n{item['content']}")
else:
    print(f"Error: {result['message']}")
```

### curl

```bash
# Получить список устройств
curl -X GET "http://localhost:8000/api/v1/devices?query=router1"

# Сгенерировать конфигурацию
curl -X POST "http://localhost:8000/api/v1/gen" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ["router1"],
    "config": "running",
    "parallel": 1
  }'

# Показать diff
curl -X POST "http://localhost:8000/api/v1/diff" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ["router1"],
    "config": "running",
    "show_rules": true
  }'

# Сгенерировать патч
curl -X POST "http://localhost:8000/api/v1/patch" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ["router1"],
    "config": "running"
  }'

# Деплой (осторожно!)
curl -X POST "http://localhost:8000/api/v1/deploy" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ["router1"],
    "config": "running",
    "no_ask_deploy": true
  }'
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const baseURL = 'http://localhost:8000';
const api = axios.create({ baseURL });

async function getDevices(query) {
  try {
    const response = await api.get('/api/v1/devices', {
      params: { query }
    });
    return response.data;
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

async function generateConfig(query, options = {}) {
  try {
    const response = await api.post('/api/v1/gen', {
      query,
      config: 'running',
      parallel: 1,
      ...options
    });
    return response.data;
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

// Использование
(async () => {
  const devices = await getDevices(['router1']);
  console.log('Devices:', devices);
  
  const config = await generateConfig(['router1'], {
    allowed_gens: ['hostname']
  });
  console.log('Generated config:', config);
})();
```

## Обработка ошибок

API возвращает стандартные HTTP коды состояния:

- `200` - Успешный запрос
- `400` - Неверный запрос (ошибка валидации)
- `404` - Устройства не найдены
- `500` - Внутренняя ошибка сервера

Все ошибки возвращаются в формате:

```json
{
  "detail": "Описание ошибки"
}
```

## Безопасность

⚠️ **Важно**: REST API предоставляет прямой доступ к функциям annet, включая деплой конфигураций на сетевые устройства. Рекомендуется:

1. Запускать API только в доверенной сети
2. Использовать аутентификацию и авторизацию (не реализовано в базовой версии)
3. Настроить firewall для ограничения доступа
4. Логировать все операции деплоя
5. Использовать HTTPS в продакшене

## Мониторинг и логирование

API использует стандартное логирование Python. Для настройки уровня логирования используйте параметр `--log-level`:

```bash
python -m annet rest-api --log-level DEBUG
```

Доступные уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Ограничения

1. API не поддерживает интерактивные операции (например, подтверждение деплоя)
2. Все операции выполняются синхронно
3. Нет встроенной аутентификации
4. Нет ограничений на количество одновременных запросов

## Разработка

Для разработки используйте режим автоперезагрузки:

```bash
python -m annet rest-api --reload --log-level DEBUG
```

Swagger UI доступен по адресу: http://localhost:8000/docs
