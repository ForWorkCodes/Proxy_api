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
prolog proxy: python manage.py proxy-prolong prolong

*/30 * * * * docker exec web-botapi-1 /usr/local/bin/python3 /app/manage.py proxy-prolong prolong >> /var/log/proxy_prolong.log 2>&1
0 */2 * * * docker exec web-botapi-1 /usr/local/bin/python3 /app/manage.py proxy-expiration deactivate >> /var/log/proxy_expiration.log 2>&1
0 */2 * * * docker exec web-botapi-1 /usr/local/bin/python3 /app/manage.py notification-checker check-expired >> /var/log/proxy_notification.log 2>&1
0 * * * * flock -n /tmp/currency_rate.lock docker exec web-botapi-1 /usr/local/bin/python3 /app/manage.py currency-rate collect --run-once >> /var/log/currency-rate.log 2>&1
