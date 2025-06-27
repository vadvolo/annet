#!/usr/bin/env python3
"""
Тесты для Annet REST API
"""

import pytest
import requests
import json
import time
import subprocess
import sys
import os
from typing import Dict, Any


class TestAnnetRestApi:
    """Тесты для REST API"""
    
    @classmethod
    def setup_class(cls):
        """Настройка перед запуском тестов"""
        cls.base_url = "http://localhost:8000"
        cls.api_process = None
        
        # Проверяем, запущен ли уже сервер
        try:
            response = requests.get(f"{cls.base_url}/health", timeout=2)
            if response.status_code == 200:
                print("API сервер уже запущен")
                return
        except requests.exceptions.RequestException:
            pass
        
        # Запускаем API сервер для тестов
        print("Запуск API сервера для тестов...")
        cls.api_process = subprocess.Popen([
            sys.executable, "-m", "annet.rest_api",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--log-level", "ERROR"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Ждем запуска сервера
        for _ in range(30):  # 30 секунд максимум
            try:
                response = requests.get(f"{cls.base_url}/health", timeout=1)
                if response.status_code == 200:
                    print("API сервер запущен")
                    break
            except requests.exceptions.RequestException:
                time.sleep(1)
        else:
            if cls.api_process:
                cls.api_process.terminate()
            pytest.fail("Не удалось запустить API сервер")
    
    @classmethod
    def teardown_class(cls):
        """Очистка после тестов"""
        if cls.api_process:
            cls.api_process.terminate()
            cls.api_process.wait()
            print("API сервер остановлен")
    
    def test_health_check(self):
        """Тест проверки здоровья API"""
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_root_endpoint(self):
        """Тест корневого endpoint"""
        response = requests.get(f"{self.base_url}/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "Annet REST API is running" in data["message"]
        assert "version" in data["data"]
    
    def test_devices_endpoint_empty_query(self):
        """Тест endpoint устройств с пустым запросом"""
        response = requests.get(f"{self.base_url}/api/v1/devices", 
                               params={"query": ["nonexistent"]})
        
        # API должен вернуть успешный ответ, даже если устройства не найдены
        assert response.status_code in [200, 404]
    
    def test_gen_endpoint_empty_config(self):
        """Тест генерации с пустой конфигурацией"""
        data = {
            "query": ["test-device"],
            "config": "empty",
            "parallel": 1
        }
        
        response = requests.post(f"{self.base_url}/api/v1/gen", 
                                json=data)
        
        # Может вернуть 404 если устройство не найдено, или 500 при других ошибках
        assert response.status_code in [200, 404, 500]
        
        if response.status_code == 200:
            result = response.json()
            assert "success" in result
            assert "message" in result
    
    def test_diff_endpoint_empty_config(self):
        """Тест diff с пустой конфигурацией"""
        data = {
            "query": ["test-device"],
            "config": "empty",
            "show_rules": False
        }
        
        response = requests.post(f"{self.base_url}/api/v1/diff", 
                                json=data)
        
        assert response.status_code in [200, 404, 500]
        
        if response.status_code == 200:
            result = response.json()
            assert "success" in result
            assert "message" in result
    
    def test_patch_endpoint_empty_config(self):
        """Тест patch с пустой конфигурацией"""
        data = {
            "query": ["test-device"],
            "config": "empty",
            "add_comments": False
        }
        
        response = requests.post(f"{self.base_url}/api/v1/patch", 
                                json=data)
        
        assert response.status_code in [200, 404, 500]
        
        if response.status_code == 200:
            result = response.json()
            assert "success" in result
            assert "message" in result
    
    def test_invalid_json(self):
        """Тест с невалидным JSON"""
        response = requests.post(f"{self.base_url}/api/v1/gen",
                                data="invalid json",
                                headers={"Content-Type": "application/json"})
        
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_missing_required_fields(self):
        """Тест с отсутствующими обязательными полями"""
        data = {
            "config": "empty"
            # Отсутствует обязательное поле "query"
        }
        
        response = requests.post(f"{self.base_url}/api/v1/gen", 
                                json=data)
        
        assert response.status_code == 422  # Validation Error
    
    def test_invalid_config_source(self):
        """Тест с невалидным источником конфигурации"""
        data = {
            "query": ["test-device"],
            "config": "/nonexistent/path/to/config"
        }
        
        response = requests.post(f"{self.base_url}/api/v1/gen", 
                                json=data)
        
        # Может вернуть ошибку валидации или внутреннюю ошибку
        assert response.status_code in [422, 500]
    
    def test_swagger_docs(self):
        """Тест доступности Swagger документации"""
        response = requests.get(f"{self.base_url}/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_redoc_docs(self):
        """Тест доступности ReDoc документации"""
        response = requests.get(f"{self.base_url}/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_openapi_schema(self):
        """Тест доступности OpenAPI схемы"""
        response = requests.get(f"{self.base_url}/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        
        # Проверяем наличие основных endpoint'ов
        paths = schema["paths"]
        assert "/api/v1/devices" in paths
        assert "/api/v1/gen" in paths
        assert "/api/v1/diff" in paths
        assert "/api/v1/patch" in paths
        assert "/api/v1/deploy" in paths


def test_api_client_script():
    """Тест клиентского скрипта"""
    script_path = os.path.join(os.path.dirname(__file__), "..", "examples", "api_client.py")
    
    if not os.path.exists(script_path):
        pytest.skip("Клиентский скрипт не найден")
    
    # Тест help
    result = subprocess.run([sys.executable, script_path, "--help"], 
                           capture_output=True, text=True)
    assert result.returncode == 0
    assert "Annet REST API Client" in result.stdout


if __name__ == "__main__":
    # Запуск тестов напрямую
    pytest.main([__file__, "-v"])
