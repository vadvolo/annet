# Annet REST API

REST API для приложения annet позволяет выполнять команды `ann get`, `ann diff`, `ann patch` и `ann deploy` через HTTP интерфейс.

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements-api.txt
```

### 2. Запуск сервера

```bash
# Запуск с параметрами по умолчанию
python -m annet rest-api

# Запуск на всех интерфейсах
python -m annet rest-api --host 0.0.0.0 --port 8080

# Запуск в режиме разработки
python -m annet rest-api --reload --log-level DEBUG
```

### 3. Проверка работы

```bash
curl http://localhost:8000/health
```

### 4. Просмотр документации

Откройте в браузере: http://localhost:8000/docs

## Основные команды

### Получить список устройств

```bash
curl "http://localhost:8000/api/v1/devices?query=router1&query=router2"
```

### Сгенерировать конфигурацию

```bash
curl -X POST "http://localhost:8000/api/v1/gen" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ["router1"],
    "config": "running",
    "parallel": 1
  }'
```

### Показать diff

```bash
curl -X POST "http://localhost:8000/api/v1/diff" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ["router1"],
    "config": "running",
    "show_rules": true
  }'
```

### Сгенерировать патч

```bash
curl -X POST "http://localhost:8000/api/v1/patch" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ["router1"],
    "config": "running"
  }'
```

### Деплой конфигурации

⚠️ **ОСТОРОЖНО**: Эта команда изменяет конфигурацию устройств!

```bash
curl -X POST "http://localhost:8000/api/v1/deploy" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ["router1"],
    "config": "running",
    "no_ask_deploy": true
  }'
```

## Использование клиента

В папке `examples/` находится готовый клиент для работы с API:

```bash
# Проверить здоровье API
python examples/api_client.py --query router1 health

# Получить список устройств
python examples/api_client.py --query router1 devices

# Сгенерировать конфигурацию
python examples/api_client.py --query router1 gen --allowed-gens hostname

# Показать diff
python examples/api_client.py --query router1 diff --show-rules

# Сгенерировать патч
python examples/api_client.py --query router1 patch

# Деплой (с подтверждением)
python examples/api_client.py --query router1 deploy
```

## Интеграция с другими системами

### Python

```python
import requests

# Создать клиент
api_url = "http://localhost:8000"

# Получить устройства
response = requests.get(f"{api_url}/api/v1/devices", 
                       params={"query": ["router1"]})
devices = response.json()

# Сгенерировать конфигурацию
response = requests.post(f"{api_url}/api/v1/gen", 
                        json={
                            "query": ["router1"],
                            "config": "running"
                        })
config = response.json()
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const api = axios.create({
  baseURL: 'http://localhost:8000'
});

// Получить устройства
const devices = await api.get('/api/v1/devices', {
  params: { query: ['router1'] }
});

// Сгенерировать конфигурацию
const config = await api.post('/api/v1/gen', {
  query: ['router1'],
  config: 'running'
});
```

### Bash/Shell

```bash
#!/bin/bash

API_URL="http://localhost:8000"
DEVICE="router1"

# Функция для выполнения запросов
api_request() {
  local method=$1
  local endpoint=$2
  local data=$3
  
  if [ "$method" = "GET" ]; then
    curl -s "$API_URL$endpoint"
  else
    curl -s -X "$method" "$API_URL$endpoint" \
      -H "Content-Type: application/json" \
      -d "$data"
  fi
}

# Получить устройства
devices=$(api_request GET "/api/v1/devices?query=$DEVICE")
echo "Devices: $devices"

# Сгенерировать конфигурацию
config=$(api_request POST "/api/v1/gen" '{"query":["'$DEVICE'"],"config":"running"}')
echo "Config: $config"
```

## Параметры конфигурации

### Основные параметры

- `query` - список запросов для поиска устройств
- `config` - источник конфигурации (`running`, `empty`, путь к файлу)
- `parallel` - количество параллельных процессов
- `tolerate_fails` - продолжать при ошибках

### Параметры генераторов

- `allowed_gens` - список разрешенных генераторов
- `excluded_gens` - список исключенных генераторов
- `force_enabled` - принудительно включенные генераторы
- `no_acl` - отключить ACL
- `acl_safe` - использовать безопасный ACL

### Параметры фильтрации

- `filter_acl` - дополнительный ACL фильтр
- `filter_ifaces` - фильтр по интерфейсам
- `filter_peers` - фильтр по пирам
- `filter_policies` - фильтр по политикам

### Параметры diff

- `show_rules` - показать правила rulebook
- `no_collapse` - не группировать одинаковые diff'ы

### Параметры patch

- `add_comments` - добавить комментарии

### Параметры deploy

- `no_ask_deploy` - не спрашивать подтверждение (всегда `true` в API)
- `no_check_diff` - не проверять diff после деплоя
- `dont_commit` - не выполнять commit
- `rollback` - включить возможность отката
- `max_deploy` - максимальное количество устройств для одновременного деплоя

## Безопасность

⚠️ **ВАЖНО**: REST API предоставляет прямой доступ к функциям annet, включая деплой конфигураций.

### Рекомендации по безопасности:

1. **Сетевая безопасность**
   - Запускайте API только в доверенной сети
   - Используйте firewall для ограничения доступа
   - Рассмотрите использование VPN

2. **Аутентификация** (не реализована в базовой версии)
   - Добавьте аутентификацию через токены
   - Используйте HTTPS в продакшене
   - Реализуйте авторизацию по ролям

3. **Мониторинг**
   - Логируйте все операции деплоя
   - Настройте алерты на критические операции
   - Ведите аудит изменений

4. **Ограничения**
   - Настройте rate limiting
   - Ограничьте размер запросов
   - Установите таймауты

## Мониторинг и отладка

### Логирование

```bash
# Запуск с детальным логированием
python -m annet rest-api --log-level DEBUG

# Логирование в файл
python -m annet rest-api --log-level INFO 2>&1 | tee api.log
```

### Метрики

API предоставляет базовые endpoint'ы для мониторинга:

- `GET /health` - проверка здоровья
- `GET /` - информация о версии

### Отладка

1. Проверьте доступность API:
   ```bash
   curl http://localhost:8000/health
   ```

2. Проверьте логи сервера

3. Используйте Swagger UI для тестирования:
   http://localhost:8000/docs

## Ограничения

1. **Функциональные**
   - Нет поддержки интерактивных операций
   - Все операции выполняются синхронно
   - Нет встроенной аутентификации

2. **Производительность**
   - Нет ограничений на количество одновременных запросов
   - Нет кеширования результатов
   - Нет пулинга соединений к устройствам

3. **Безопасность**
   - Нет шифрования трафика (HTTP)
   - Нет защиты от CSRF
   - Нет rate limiting

## Разработка и расширение

### Добавление новых endpoint'ов

1. Добавьте новую функцию в `annet/rest_api.py`
2. Определите модели данных с помощью Pydantic
3. Добавьте обработку ошибок
4. Обновите документацию

### Тестирование

```bash
# Запуск в режиме разработки
python -m annet rest-api --reload --log-level DEBUG

# Тестирование через curl
curl -X POST "http://localhost:8000/api/v1/gen" \
  -H "Content-Type: application/json" \
  -d '{"query":["test"],"config":"empty"}'
```

## Поддержка

- Документация: `docs/rest_api.md`
- Примеры: `examples/api_client.py`
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Лицензия

Использует ту же лицензию, что и основной проект annet.
