# Proxy API Project

## Description


## Features
- Proxy server implementation
- HTTP request handling
- Configurable proxy settings

## Installation
1. Clone the repository:
2. Install dependencies:
```bash
pip install -r requirements.txt
rename and config - alembic.axample.ini

alembic upgrade head - update db
```
3. Create .env

## Usage
1. Configure your proxy settings in the configuration file
2. Run the proxy server:
```bash
uvicorn main:app
```

## Configuration
The proxy server can be configured through the `config.py` file. You can set:
- Proxy host and port
- Request timeout
- Other proxy-related settings

## Requirements
- Python 3.11+
- PostgreSQL 17+
- Required packages are listed in `requirements.txt`

alembic revision --autogenerate -m "name of migration" 
deactivation old proxy: python manage.py proxy-expiration deactivate 
check almost expired proxies: python manage.py notification-checker check-expired 