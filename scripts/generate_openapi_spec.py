#!/usr/bin/env python3
"""
File Location: scripts/generate_openapi_spec.py

Generate OpenAPI specification from FastAPIVerseHub application.
Exports the API specification in JSON and YAML formats.
"""

import json
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
except ImportError:
    print("Installing PyYAML...")
    os.system("pip install PyYAML")
    import yaml

from app.main import app

def generate_openapi_spec():
    """Generate OpenAPI specification"""
    print("Generating OpenAPI specification for FastAPIVerseHub...")
    
    # Get the OpenAPI schema
    openapi_schema = app.openapi()
    
    # Create output directory
    output_dir = Path("docs/openapi")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate JSON specification
    json_file = output_dir / "openapi.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
    print(f"✓ Generated JSON specification: {json_file}")
    
    # Generate YAML specification
    yaml_file = output_dir / "openapi.yaml"
    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.dump(openapi_schema, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"✓ Generated YAML specification: {yaml_file}")
    
    # Generate Markdown documentation
    generate_markdown_docs(openapi_schema, output_dir)
    
    # Generate Postman collection
    generate_postman_collection(openapi_schema, output_dir)
    
    print(f"\n✅ OpenAPI specification generated successfully!")
    print(f"📁 Output directory: {output_dir}")
    print(f"🌐 View interactive docs: http://localhost:8000/docs")

def generate_markdown_docs(schema, output_dir):
    """Generate Markdown API documentation"""
    print("Generating Markdown documentation...")
    
    md_content = []
    md_content.append("# FastAPIVerseHub API Documentation\n")
    md_content.append(f"**Version:** {schema.get('info', {}).get('version', 'Unknown')}\n")
    md_content.append(f"**Description:** {schema.get('info', {}).get('description', 'No description')}\n")
    
    # Add server information
    servers = schema.get('servers', [])
    if servers:
        md_content.append("## Servers\n")
        for server in servers:
            md_content.append(f"- **{server.get('description', 'Server')}**: `{server.get('url', 'Unknown')}`")
        md_content.append("")
    
    # Add authentication information
    security_schemes = schema.get('components', {}).get('securitySchemes', {})
    if security_schemes:
        md_content.append("## Authentication\n")
        for name, scheme in security_schemes.items():
            scheme_type = scheme.get('type', 'Unknown')
            md_content.append(f"### {name}")
            md_content.append(f"- **Type**: {scheme_type}")
            if 'description' in scheme:
                md_content.append(f"- **Description**: {scheme['description']}")
            if scheme_type == 'http':
                md_content.append(f"- **Scheme**: {scheme.get('scheme', 'Unknown')}")
            md_content.append("")
    
    # Add endpoints
    paths = schema.get('paths', {})
    if paths:
        md_content.append("## Endpoints\n")
        
        # Group endpoints by tags
        endpoints_by_tag = {}
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                    tags = details.get('tags', ['Default'])
                    tag = tags[0] if tags else 'Default'
                    
                    if tag not in endpoints_by_tag:
                        endpoints_by_tag[tag] = []
                    
                    endpoints_by_tag[tag].append({
                        'path': path,
                        'method': method.upper(),
                        'details': details
                    })
        
        # Generate documentation for each tag
        for tag, endpoints in endpoints_by_tag.items():
            md_content.append(f"### {tag}\n")
            
            for endpoint in endpoints:
                path = endpoint['path']
                method = endpoint['method']
                details = endpoint['details']
                
                md_content.append(f"#### {method} {path}")
                
                if 'summary' in details:
                    md_content.append(f"**Summary**: {details['summary']}")
                
                if 'description' in details:
                    md_content.append(f"**Description**: {details['description']}")
                
                # Parameters
                parameters = details.get('parameters', [])
                if parameters:
                    md_content.append("**Parameters**:")
                    for param in parameters:
                        param_name = param.get('name', 'Unknown')
                        param_type = param.get('schema', {}).get('type', 'Unknown')
                        param_location = param.get('in', 'Unknown')
                        required = "Required" if param.get('required', False) else "Optional"
                        md_content.append(f"- `{param_name}` ({param_location}, {param_type}) - {required}")
                        if 'description' in param:
                            md_content.append(f"  {param['description']}")
                
                # Request Body
                request_body = details.get('requestBody')
                if request_body:
                    md_content.append("**Request Body**:")
                    content = request_body.get('content', {})
                    for content_type, body_details in content.items():
                        md_content.append(f"- Content-Type: `{content_type}`")
                        if 'schema' in body_details:
                            schema_ref = body_details['schema'].get('$ref', '')
                            if schema_ref:
                                schema_name = schema_ref.split('/')[-1]
                                md_content.append(f"  Schema: `{schema_name}`")
                
                # Responses
                responses = details.get('responses', {})
                if responses:
                    md_content.append("**Responses**:")
                    for status_code, response in responses.items():
                        description = response.get('description', 'No description')
                        md_content.append(f"- `{status_code}`: {description}")
                
                md_content.append("")
    
    # Write Markdown file
    md_file = output_dir / "api_documentation.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))
    print(f"✓ Generated Markdown documentation: {md_file}")

def generate_postman_collection(schema, output_dir):
    """Generate Postman collection from OpenAPI spec"""
    print("Generating Postman collection...")
    
    collection = {
        "info": {
            "name": schema.get('info', {}).get('title', 'FastAPIVerseHub API'),
            "description": schema.get('info', {}).get('description', ''),
            "version": schema.get('info', {}).get('version', '1.0.0'),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{auth_token}}",
                    "type": "string"
                }
            ]
        },
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "// Set base URL",
                        "pm.globals.set('base_url', 'http://localhost:8000');"
                    ]
                }
            }
        ],
        "variable": [
            {
                "key": "base_url",
                "value": "http://localhost:8000"
            },
            {
                "key": "auth_token",
                "value": ""
            }
        ],
        "item": []
    }
    
    # Group requests by tags
    paths = schema.get('paths', {})
    requests_by_tag = {}
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                tags = details.get('tags', ['Default'])
                tag = tags[0] if tags else 'Default'
                
                if tag not in requests_by_tag:
                    requests_by_tag[tag] = []
                
                # Create Postman request
                request = {
                    "name": details.get('summary', f"{method.upper()} {path}"),
                    "request": {
                        "method": method.upper(),
                        "header": [
                            {
                                "key": "Content-Type",
                                "value": "application/json",
                                "type": "text"
                            }
                        ],
                        "url": {
                            "raw": "{{base_url}}" + path,
                            "host": ["{{base_url}}"],
                            "path": [p for p in path.split('/') if p]
                        }
                    },
                    "response": []
                }
                
                # Add authentication if required
                security = details.get('security', [])
                if security:
                    request['request']['auth'] = {
                        "type": "bearer",
                        "bearer": [
                            {
                                "key": "token",
                                "value": "{{auth_token}}",
                                "type": "string"
                            }
                        ]
                    }
                
                # Add request body for POST/PUT/PATCH
                if method.lower() in ['post', 'put', 'patch']:
                    request_body = details.get('requestBody')
                    if request_body:
                        content = request_body.get('content', {})
                        if 'application/json' in content:
                            request['request']['body'] = {
                                "mode": "raw",
                                "raw": "{\n  // Add request body here\n}",
                                "options": {
                                    "raw": {
                                        "language": "json"
                                    }
                                }
                            }
                
                # Add query parameters
                parameters = details.get('parameters', [])
                query_params = [p for p in parameters if p.get('in') == 'query']
                if query_params:
                    request['request']['url']['query'] = [
                        {
                            "key": param.get('name', ''),
                            "value": "",
                            "description": param.get('description', ''),
                            "disabled": not param.get('required', False)
                        }
                        for param in query_params
                    ]
                
                requests_by_tag[tag].append(request)
    
    # Add folders for each tag
    for tag, requests in requests_by_tag.items():
        folder = {
            "name": tag,
            "item": requests
        }
        collection['item'].append(folder)
    
    # Add authentication request
    auth_folder = {
        "name": "Authentication",
        "item": [
            {
                "name": "Login",
                "request": {
                    "method": "POST",
                    "header": [
                        {
                            "key": "Content-Type",
                            "value": "application/x-www-form-urlencoded"
                        }
                    ],
                    "body": {
                        "mode": "urlencoded",
                        "urlencoded": [
                            {
                                "key": "username",
                                "value": "admin@example.com",
                                "type": "text"
                            },
                            {
                                "key": "password",
                                "value": "admin123",
                                "type": "text"
                            }
                        ]
                    },
                    "url": {
                        "raw": "{{base_url}}/api/v1/auth/token",
                        "host": ["{{base_url}}"],
                        "path": ["api", "v1", "auth", "token"]
                    }
                },
                "event": [
                    {
                        "listen": "test",
                        "script": {
                            "exec": [
                                "if (responseCode.code === 200) {",
                                "    const response = pm.response.json();",
                                "    pm.globals.set('auth_token', response.access_token);",
                                "    console.log('Token saved:', response.access_token);",
                                "}"
                            ],
                            "type": "text/javascript"
                        }
                    }
                ]
            }
        ]
    }
    
    # Insert auth folder at the beginning
    collection['item'].insert(0, auth_folder)
    
    # Write Postman collection
    postman_file = output_dir / "FastAPIVerseHub.postman_collection.json"
    with open(postman_file, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2, ensure_ascii=False)
    print(f"✓ Generated Postman collection: {postman_file}")

def main():
    """Main function"""
    try:
        generate_openapi_spec()
    except Exception as e:
        print(f"❌ Error generating OpenAPI specification: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()