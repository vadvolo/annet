"""
REST API для приложения annet
Предоставляет HTTP endpoints для команд ann get, ann diff, ann patch и ann deploy
"""

import asyncio
import json
import logging
import os
import tempfile
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query as QueryParam
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
import uvicorn

from annet import api, cli_args, filtering
from annet.deploy import get_fetcher, get_deployer
from annet.gen import Loader
from annet.storage import get_storage, Query
from annet.api import Deployer
from annet.output import output_driver_connector


# Модели данных для API
class DeviceQuery(BaseModel):
    """Запрос устройств"""
    query: List[str] = Field(..., description="Список запросов для поиска устройств")
    hosts_range: Optional[str] = Field(None, description="Диапазон хостов (например, '10' или '10:20')")


class GenerationOptions(BaseModel):
    """Опции генерации конфигурации"""
    config: str = Field("running", description="Источник конфигурации: 'running', 'empty', путь к файлу или '-' (stdin)")
    allowed_gens: Optional[List[str]] = Field(None, description="Список разрешенных генераторов")
    excluded_gens: Optional[List[str]] = Field(None, description="Список исключенных генераторов")
    force_enabled: Optional[List[str]] = Field(None, description="Список принудительно включенных генераторов")
    no_acl: bool = Field(False, description="Отключить ACL для генерации конфигурации")
    acl_safe: bool = Field(False, description="Использовать безопасный ACL")
    filter_acl: str = Field("", description="Дополнительный ACL фильтр")
    filter_ifaces: Optional[List[str]] = Field(None, description="Фильтр по интерфейсам")
    filter_peers: Optional[List[str]] = Field(None, description="Фильтр по пирам")
    filter_policies: Optional[List[str]] = Field(None, description="Фильтр по политикам")
    parallel: int = Field(1, description="Количество параллельных процессов")
    tolerate_fails: bool = Field(False, description="Продолжать при ошибках")
    annotate: bool = Field(False, description="Аннотировать строки конфигурации")
    indent: str = Field("  ", description="Отступы для блоков")


class DiffOptions(GenerationOptions):
    """Опции для diff"""
    show_rules: bool = Field(False, description="Показать правила rulebook в diff")
    clear: bool = Field(False, description="Удалить команды генератора используя его ACL")
    no_collapse: bool = Field(False, description="Не группировать одинаковые diff'ы")


class PatchOptions(DiffOptions):
    """Опции для patch"""
    add_comments: bool = Field(False, description="Добавить комментарии")


class DeployOptions(PatchOptions):
    """Опции для deploy"""
    no_ask_deploy: bool = Field(True, description="Не спрашивать подтверждение на выполнение команд")
    no_check_diff: bool = Field(False, description="Не проверять diff после деплоя")
    dont_commit: bool = Field(False, description="Не выполнять команду 'commit' во время деплоя")
    rollback: bool = Field(False, description="Предложить откат после деплоя если возможно")
    max_deploy: int = Field(0, description="Количество устройств для одновременного деплоя")
    entire_reload: str = Field("yes", description="Запускать reload() при деплое Entire-генераторов")


class ApiResponse(BaseModel):
    """Базовый ответ API"""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None


class GenerationResult(BaseModel):
    """Результат генерации"""
    device: str
    content: str
    success: bool
    error: Optional[str] = None


class DiffResult(BaseModel):
    """Результат diff"""
    devices: List[str]
    diff: str
    success: bool
    error: Optional[str] = None


class DeployResult(BaseModel):
    """Результат deploy"""
    device: str
    success: bool
    duration: float
    error: Optional[str] = None


# Глобальные переменные для кеширования
_storage_connector = None
_filterer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация и очистка ресурсов приложения"""
    global _storage_connector, _filterer
    
    # Инициализация
    _storage_connector, _ = get_storage()
    _filterer = filtering.filterer_connector.get()
    
    yield
    
    # Очистка ресурсов
    _storage_connector = None
    _filterer = None


# Создание FastAPI приложения
app = FastAPI(
    title="Annet REST API",
    description="REST API для управления сетевыми конфигурациями через annet",
    version="1.0.0",
    lifespan=lifespan
)


def _create_cli_args(query_data: DeviceQuery, options: GenerationOptions, args_class):
    """Создание объекта аргументов CLI из данных API"""
    # Создаем объект Query
    storage, _ = get_storage()
    query_type = storage.query()
    
    # Парсим hosts_range если указан
    hosts_range = None
    if query_data.hosts_range:
        if query_data.hosts_range.isdigit():
            hosts_range = slice(0, int(query_data.hosts_range))
        elif ":" in query_data.hosts_range:
            start_str, stop_str = query_data.hosts_range.split(":", 1)
            stop = None if not stop_str else int(stop_str)
            hosts_range = slice(int(start_str), stop)
    
    query = query_type.new(query_data.query, hosts_range=hosts_range)
    
    # Создаем объект аргументов
    args_dict = {
        'query': query,
        'hosts_range': hosts_range,
        'config': options.config,
        'allowed_gens': options.allowed_gens or [],
        'excluded_gens': options.excluded_gens or [],
        'force_enabled': options.force_enabled or [],
        'no_acl': options.no_acl,
        'acl_safe': options.acl_safe,
        'filter_acl': options.filter_acl,
        'filter_ifaces': options.filter_ifaces or [],
        'filter_peers': options.filter_peers or [],
        'filter_policies': options.filter_policies or [],
        'parallel': options.parallel,
        'tolerate_fails': options.tolerate_fails,
        'strict_exit_code': False,
        'annotate': options.annotate,
        'indent': options.indent,
        'no_mesh': False,
        'profile': False,
        'required_packages_check': False,
        'fail_on_empty_config': False,
        'generators_context': None,
        'no_acl_exclusive': False,
        'max_tasks': None,
        'ignore_disabled': False,
    }
    
    # Добавляем специфичные для diff опции
    if hasattr(options, 'show_rules'):
        args_dict.update({
            'show_rules': options.show_rules,
            'clear': options.clear,
            'no_collapse': options.no_collapse,
        })
    
    # Добавляем специфичные для patch опции
    if hasattr(options, 'add_comments'):
        args_dict.update({
            'add_comments': options.add_comments,
        })
    
    # Добавляем специфичные для deploy опции
    if hasattr(options, 'no_ask_deploy'):
        args_dict.update({
            'no_ask_deploy': options.no_ask_deploy,
            'no_check_diff': options.no_check_diff,
            'dont_commit': options.dont_commit,
            'rollback': options.rollback,
            'max_parallel': options.max_deploy,
            'entire_reload': cli_args.EntireReloadFlag(options.entire_reload),
            'ask_pass': False,
            'max_slots': 30,
            'no_progress': True,
            'connect_timeout': 20.0,
            'log_json': False,
            'log_dest': '/dev/null',
            'log_nogroup': False,
        })
    
    # Создаем объект аргументов нужного типа
    class MockArgs:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
        
        def stdin(self, filter_acl=None, config=None):
            return {
                'filter_acl': None,
                'config': None,
            }
    
    return MockArgs(**args_dict)


@app.get("/", response_model=ApiResponse)
async def root():
    """Корневой endpoint"""
    return ApiResponse(
        success=True,
        message="Annet REST API is running",
        data={"version": "1.0.0"}
    )


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy"}


@app.post("/api/v1/gen", response_model=ApiResponse)
async def generate_config(query: DeviceQuery, options: GenerationOptions):
    """
    Генерация конфигурации для устройств (аналог команды 'ann gen')
    """
    try:
        # Создаем аргументы CLI
        args = _create_cli_args(query, options, cli_args.ShowGenOptions)
        
        # Создаем loader
        connector, conf_params = get_storage()
        storage_opts = connector.opts().parse_params(conf_params, args)
        
        with connector.storage()(storage_opts) as storage:
            loader = Loader(storage, args=args)
            
            if not loader.devices:
                raise HTTPException(
                    status_code=404,
                    detail=f"No devices found for query: {query.query}"
                )
            
            # Выполняем генерацию
            success, fail = api.gen(args, loader)
            
            # Формируем результат
            results = []
            for device_id, items in success.items():
                device = loader.get_device(device_id)
                for item in items:
                    results.append(GenerationResult(
                        device=device.hostname,
                        content=item[1],
                        success=True
                    ))
            
            # Добавляем ошибки
            for device_id, error in fail.items():
                device = loader.get_device(device_id)
                results.append(GenerationResult(
                    device=device.hostname,
                    content="",
                    success=False,
                    error=str(error)
                ))
            
            return ApiResponse(
                success=True,
                message=f"Generated configuration for {len(success)} devices",
                data=results
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/diff", response_model=ApiResponse)
async def show_diff(query: DeviceQuery, options: DiffOptions):
    """
    Показать diff конфигурации (аналог команды 'ann diff')
    """
    try:
        # Создаем аргументы CLI
        args = _create_cli_args(query, options, cli_args.ShowDiffOptions)
        
        # Создаем loader
        connector, conf_params = get_storage()
        storage_opts = connector.opts().parse_params(conf_params, args)
        
        with connector.storage()(storage_opts) as storage:
            loader = Loader(storage, args=args)
            
            if not loader.devices:
                raise HTTPException(
                    status_code=404,
                    detail=f"No devices found for query: {query.query}"
                )
            
            # Выполняем diff
            success, fail = api.diff(args, loader, loader.device_ids)
            
            # Формируем результат
            from annet.diff import gen_sort_diff
            results = []
            
            diffs_by_device = {loader.get_device(k): v for k, v in success.items()}
            for dest_name, diff_content, _ in gen_sort_diff(diffs_by_device, args):
                if hasattr(diff_content, '__iter__') and not isinstance(diff_content, str):
                    diff_text = ''.join(diff_content)
                else:
                    diff_text = str(diff_content)
                
                results.append(DiffResult(
                    devices=[dest_name],
                    diff=diff_text,
                    success=True
                ))
            
            # Добавляем ошибки
            errors = []
            for device_id, error in fail.items():
                device = loader.get_device(device_id)
                errors.append(f"{device.hostname}: {str(error)}")
            
            return ApiResponse(
                success=True,
                message=f"Generated diff for {len(success)} devices",
                data=results,
                errors=errors if errors else None
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/patch", response_model=ApiResponse)
async def generate_patch(query: DeviceQuery, options: PatchOptions):
    """
    Генерация патча для устройств (аналог команды 'ann patch')
    """
    try:
        # Создаем аргументы CLI
        args = _create_cli_args(query, options, cli_args.ShowPatchOptions)
        
        # Создаем loader
        connector, conf_params = get_storage()
        storage_opts = connector.opts().parse_params(conf_params, args)
        
        with connector.storage()(storage_opts) as storage:
            loader = Loader(storage, args=args)
            
            if not loader.devices:
                raise HTTPException(
                    status_code=404,
                    detail=f"No devices found for query: {query.query}"
                )
            
            # Выполняем patch
            success, fail = api.patch(args, loader)
            
            # Формируем результат
            results = []
            for device_id, items in success.items():
                device = loader.get_device(device_id)
                for item in items:
                    results.append(GenerationResult(
                        device=device.hostname,
                        content=item[1],
                        success=True
                    ))
            
            # Добавляем ошибки
            for device_id, error in fail.items():
                device = loader.get_device(device_id)
                results.append(GenerationResult(
                    device=device.hostname,
                    content="",
                    success=False,
                    error=str(error)
                ))
            
            return ApiResponse(
                success=True,
                message=f"Generated patch for {len(success)} devices",
                data=results
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/deploy", response_model=ApiResponse)
async def deploy_config(query: DeviceQuery, options: DeployOptions):
    """
    Деплой конфигурации на устройства (аналог команды 'ann deploy')
    """
    try:
        # Создаем аргументы CLI
        args = _create_cli_args(query, options, cli_args.DeployOptions)
        
        # Создаем loader
        connector, conf_params = get_storage()
        storage_opts = connector.opts().parse_params(conf_params, args)
        
        with connector.storage()(storage_opts) as storage:
            loader = Loader(storage, args=args)
            
            if not loader.devices:
                raise HTTPException(
                    status_code=404,
                    detail=f"No devices found for query: {query.query}"
                )
            
            # Создаем необходимые объекты для деплоя
            deployer = Deployer(args)
            filterer = filtering.filterer_connector.get()
            fetcher = get_fetcher()
            deploy_driver = get_deployer()
            
            # Выполняем деплой
            exit_code = api.deploy(
                args=args,
                loader=loader,
                deployer=deployer,
                deploy_driver=deploy_driver,
                filterer=filterer,
                fetcher=fetcher,
            )
            
            # Формируем результат
            results = []
            for hostname, result in deployer.deploy_cmds.items():
                if isinstance(result, Exception):
                    results.append(DeployResult(
                        device=hostname,
                        success=False,
                        duration=0.0,
                        error=str(result)
                    ))
                else:
                    results.append(DeployResult(
                        device=hostname,
                        success=True,
                        duration=0.0  # TODO: получить реальное время
                    ))
            
            # Добавляем ошибки из failed_configs
            for hostname, error in deployer.failed_configs.items():
                results.append(DeployResult(
                    device=hostname,
                    success=False,
                    duration=0.0,
                    error=str(error)
                ))
            
            return ApiResponse(
                success=exit_code == 0,
                message=f"Deploy completed with exit code {exit_code}",
                data=results
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/devices", response_model=ApiResponse)
async def list_devices(
    query: List[str] = QueryParam(..., description="Device query"),
    hosts_range: Optional[str] = QueryParam(None, description="Hosts range")
):
    """
    Получить список устройств по запросу
    """
    try:
        # Создаем объект запроса
        device_query = DeviceQuery(query=query, hosts_range=hosts_range)
        options = GenerationOptions()
        args = _create_cli_args(device_query, options, cli_args.QueryOptions)
        
        # Создаем loader
        connector, conf_params = get_storage()
        storage_opts = connector.opts().parse_params(conf_params, args)
        
        with connector.storage()(storage_opts) as storage:
            loader = Loader(storage, args=args)
            
            devices_info = []
            for device in loader.devices:
                devices_info.append({
                    "id": device.id,
                    "hostname": device.hostname,
                    "fqdn": device.fqdn,
                    "vendor": device.hw.vendor if hasattr(device.hw, 'vendor') else 'unknown',
                    "breed": getattr(device, 'breed', 'unknown')
                })
            
            return ApiResponse(
                success=True,
                message=f"Found {len(devices_info)} devices",
                data=devices_info
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Annet REST API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "annet.rest_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level
    )
