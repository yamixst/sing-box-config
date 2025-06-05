#!/usr/bin/env python3

import json
import urllib.parse
import argparse
import sys
import os
import re
from typing import Dict, Any, Optional

def parse_vless_url(vless_url: str) -> Dict[str, Any]:
    if not vless_url.startswith('vless://'):
        raise ValueError("URL must start with 'vless://'")

    url_without_prefix = vless_url[8:]
    parts = url_without_prefix.split('#')
    name = urllib.parse.unquote(parts[1]) if len(parts) > 1 else "VLESS Server"
    main_part, params_part = parts[0].split('?', 1)
    uuid_and_server = main_part.split('@')
    uuid = uuid_and_server[0]
    server_and_port = uuid_and_server[1].split(':')
    server = server_and_port[0]
    port = int(server_and_port[1]) if len(server_and_port) > 1 else 443
    params = urllib.parse.parse_qs(params_part)

    processed_params = {}
    for key, value in params.items():
        if isinstance(value, list) and len(value) == 1:
            processed_params[key] = value[0]
        else:
            processed_params[key] = value
    params = processed_params

    return {
        'name': name,
        'uuid': uuid,
        'server': server,
        'port': port,
        'security': params.get('security', 'none'),
        'encryption': params.get('encryption', 'none'),
        'headerType': params.get('headerType', 'none'),
        'fp': params.get('fp', 'chrome'),
        'type': params.get('type', 'tcp'),
        'flow': params.get('flow', ''),
        'pbk': params.get('pbk', ''),  # public key for Reality
        'sni': params.get('sni', ''),   # server name indication
        'sid': params.get('sid', ''),   # short id for Reality
        'path': params.get('path', ''),
        'host': params.get('host', ''),
        'alpn': params.get('alpn', ''),
        'all_params': params
    }

def sanitize_filename(name: str) -> str:
    """Convert server name to valid filename"""
    # Remove or replace invalid characters for filename
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    # Ensure it's not empty
    if not sanitized:
        sanitized = "vless_config"
    return sanitized + ".json"

def load_template(template_path: str) -> Dict[str, Any]:
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Template file not found: {template_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON template parsing error: {e}")

def update_vless_outbound(config: Dict[str, Any], vless_params: Dict[str, Any]) -> None:
    vless_outbound = None
    for outbound in config.get('outbounds', []):
        if outbound.get('type') == 'vless':
            vless_outbound = outbound
            break

    if not vless_outbound:
        raise ValueError("VLESS outbound not found in template")

    vless_outbound['server'] = vless_params['server']
    vless_outbound['server_port'] = vless_params['port']
    vless_outbound['uuid'] = vless_params['uuid']

    if vless_params['flow']:
        vless_outbound['flow'] = vless_params['flow']

    if vless_params['security'] == 'reality':
        tls_config = vless_outbound.setdefault('tls', {})
        tls_config['enabled'] = True

        if vless_params['sni']:
            tls_config['server_name'] = vless_params['sni']

        utls_config = tls_config.setdefault('utls', {})
        utls_config['enabled'] = True
        utls_config['fingerprint'] = vless_params['fp']

        reality_config = tls_config.setdefault('reality', {})
        reality_config['enabled'] = True

        if vless_params['pbk']:
            reality_config['public_key'] = vless_params['pbk']

        if vless_params['sid']:
            reality_config['short_id'] = vless_params['sid']

    elif vless_params['security'] == 'tls':
        tls_config = vless_outbound.setdefault('tls', {})
        tls_config['enabled'] = True

        if vless_params['sni']:
            tls_config['server_name'] = vless_params['sni']

        utls_config = tls_config.setdefault('utls', {})
        utls_config['enabled'] = True
        utls_config['fingerprint'] = vless_params['fp']

    if vless_params['type'] == 'ws':
        transport_config = vless_outbound.setdefault('transport', {})
        transport_config['type'] = 'ws'

        ws_config = transport_config.setdefault('ws', {})
        if vless_params['path']:
            ws_config['path'] = vless_params['path']
        if vless_params['host']:
            ws_config['headers'] = {'Host': vless_params['host']}

    elif vless_params['type'] == 'grpc':
        transport_config = vless_outbound.setdefault('transport', {})
        transport_config['type'] = 'grpc'

        if vless_params['path']:
            grpc_config = transport_config.setdefault('grpc', {})
            grpc_config['service_name'] = vless_params['path']

def generate_config(template_path: str, vless_url: str, output_path: Optional[str] = None) -> str:
    try:
        vless_params = parse_vless_url(vless_url)
        print(f"Successfully parsed VLESS URL for server: {vless_params['name']}")
        print(f"  Server: {vless_params['server']}:{vless_params['port']}")
        print(f"  UUID: {vless_params['uuid']}")
        print(f"  Security: {vless_params['security']}")
        if vless_params['sni']:
            print(f"  SNI: {vless_params['sni']}")
    except Exception as e:
        raise ValueError(f"VLESS URL parsing error: {e}")

    config = load_template(template_path)
    print(f"Loaded template: {template_path}")

    try:
        update_vless_outbound(config, vless_params)
        print("VLESS outbound configuration updated")
    except Exception as e:
        raise ValueError(f"Configuration update error: {e}")

    config_json = json.dumps(config, indent=2, ensure_ascii=False)

    if output_path:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(config_json)
            print(f"Configuration saved to: {output_path}")
        except Exception as e:
            raise IOError(f"File saving error: {e}")

    return config_json

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='sing-box configuration generator from VLESS URL',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '-u', '--url',
        required=True,
        help='VLESS URL for connection'
    )

    parser.add_argument(
        '-t', '--template',
        required=True,
        help='Path to JSON template file'
    )

    parser.add_argument(
        '-o', '--output',
        help='Path for saving configuration (default: auto-generate from server name)'
    )

    args = parser.parse_args()

    template_path = args.template
    if not template_path:
        print("Template file must be specified with -t/--template", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(template_path):
        print(f"Template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    try:
        output_path = args.output
        if not output_path:
            vless_params = parse_vless_url(args.url)
            output_path = sanitize_filename(vless_params['name'])

        generate_config(template_path, args.url, output_path)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
