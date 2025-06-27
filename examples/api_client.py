#!/usr/bin/env python3
"""
Пример клиента для Annet REST API
Демонстрирует основные операции через HTTP API
"""

import requests
import json
import sys
import argparse
from typing import List, Dict, Any, Optional


class AnnetApiClient:
    """Клиент для работы с Annet REST API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Выполнить HTTP запрос к API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"Детали ошибки: {error_detail}")
                except:
                    print(f"Ответ сервера: {e.response.text}")
            sys.exit(1)
    
    def health_check(self) -> Dict[str, Any]:
        """Проверить здоровье API"""
        return self._make_request('GET', '/health')
    
    def get_devices(self, query: List[str], hosts_range: Optional[str] = None) -> Dict[str, Any]:
        """Получить список устройств"""
        params = {'query': query}
        if hosts_range:
            params['hosts_range'] = hosts_range
        
        return self._make_request('GET', '/api/v1/devices', params=params)
    
    def generate_config(self, query: List[str], **options) -> Dict[str, Any]:
        """Сгенерировать конфигурацию"""
        data = {'query': query, **options}
        return self._make_request('POST', '/api/v1/gen', json=data)
    
    def show_diff(self, query: List[str], **options) -> Dict[str, Any]:
        """Показать diff конфигурации"""
        data = {'query': query, **options}
        return self._make_request('POST', '/api/v1/diff', json=data)
    
    def generate_patch(self, query: List[str], **options) -> Dict[str, Any]:
        """Сгенерировать патч"""
        data = {'query': query, **options}
        return self._make_request('POST', '/api/v1/patch', json=data)
    
    def deploy_config(self, query: List[str], **options) -> Dict[str, Any]:
        """Деплой конфигурации"""
        data = {'query': query, **options}
        return self._make_request('POST', '/api/v1/deploy', json=data)


def print_response(response: Dict[str, Any], title: str = "Ответ"):
    """Красиво вывести ответ API"""
    print(f"\n=== {title} ===")
    print(f"Успех: {response.get('success', 'N/A')}")
    print(f"Сообщение: {response.get('message', 'N/A')}")
    
    if response.get('errors'):
        print("Ошибки:")
        for error in response['errors']:
            print(f"  - {error}")
    
    if response.get('data'):
        print("Данные:")
        if isinstance(response['data'], list):
            for i, item in enumerate(response['data']):
                print(f"  [{i+1}] {json.dumps(item, indent=2, ensure_ascii=False)}")
        else:
            print(f"  {json.dumps(response['data'], indent=2, ensure_ascii=False)}")


def main():
    parser = argparse.ArgumentParser(description="Annet REST API Client")
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='Base URL of Annet API server')
    parser.add_argument('--query', nargs='+', required=True,
                       help='Device query')
    parser.add_argument('--config', default='running',
                       help='Config source (running, empty, file path)')
    parser.add_argument('--parallel', type=int, default=1,
                       help='Number of parallel processes')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Health check
    subparsers.add_parser('health', help='Check API health')
    
    # Devices
    devices_parser = subparsers.add_parser('devices', help='List devices')
    devices_parser.add_argument('--hosts-range', help='Hosts range')
    
    # Generate
    gen_parser = subparsers.add_parser('gen', help='Generate configuration')
    gen_parser.add_argument('--allowed-gens', nargs='+', help='Allowed generators')
    gen_parser.add_argument('--no-acl', action='store_true', help='Disable ACL')
    gen_parser.add_argument('--annotate', action='store_true', help='Annotate config')
    
    # Diff
    diff_parser = subparsers.add_parser('diff', help='Show configuration diff')
    diff_parser.add_argument('--show-rules', action='store_true', help='Show rulebook rules')
    diff_parser.add_argument('--no-collapse', action='store_true', help='Do not collapse diffs')
    
    # Patch
    patch_parser = subparsers.add_parser('patch', help='Generate configuration patch')
    patch_parser.add_argument('--add-comments', action='store_true', help='Add comments')
    
    # Deploy
    deploy_parser = subparsers.add_parser('deploy', help='Deploy configuration')
    deploy_parser.add_argument('--dont-commit', action='store_true', help='Do not commit')
    deploy_parser.add_argument('--rollback', action='store_true', help='Enable rollback')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Создаем клиент
    client = AnnetApiClient(args.url)
    
    try:
        if args.command == 'health':
            response = client.health_check()
            print_response(response, "Health Check")
        
        elif args.command == 'devices':
            response = client.get_devices(
                query=args.query,
                hosts_range=getattr(args, 'hosts_range', None)
            )
            print_response(response, "Устройства")
        
        elif args.command == 'gen':
            options = {
                'config': args.config,
                'parallel': args.parallel
            }
            if hasattr(args, 'allowed_gens') and args.allowed_gens:
                options['allowed_gens'] = args.allowed_gens
            if hasattr(args, 'no_acl') and args.no_acl:
                options['no_acl'] = True
            if hasattr(args, 'annotate') and args.annotate:
                options['annotate'] = True
            
            response = client.generate_config(query=args.query, **options)
            print_response(response, "Генерация конфигурации")
        
        elif args.command == 'diff':
            options = {
                'config': args.config,
                'parallel': args.parallel
            }
            if hasattr(args, 'show_rules') and args.show_rules:
                options['show_rules'] = True
            if hasattr(args, 'no_collapse') and args.no_collapse:
                options['no_collapse'] = True
            
            response = client.show_diff(query=args.query, **options)
            print_response(response, "Diff конфигурации")
        
        elif args.command == 'patch':
            options = {
                'config': args.config,
                'parallel': args.parallel
            }
            if hasattr(args, 'add_comments') and args.add_comments:
                options['add_comments'] = True
            
            response = client.generate_patch(query=args.query, **options)
            print_response(response, "Патч конфигурации")
        
        elif args.command == 'deploy':
            options = {
                'config': args.config,
                'parallel': args.parallel,
                'no_ask_deploy': True  # Всегда True для API
            }
            if hasattr(args, 'dont_commit') and args.dont_commit:
                options['dont_commit'] = True
            if hasattr(args, 'rollback') and args.rollback:
                options['rollback'] = True
            
            print("⚠️  ВНИМАНИЕ: Выполняется деплой конфигурации!")
            confirm = input("Продолжить? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                print("Деплой отменен.")
                sys.exit(0)
            
            response = client.deploy_config(query=args.query, **options)
            print_response(response, "Деплой конфигурации")
    
    except KeyboardInterrupt:
        print("\nОперация прервана пользователем.")
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
