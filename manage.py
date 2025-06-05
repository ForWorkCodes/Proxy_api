import typer
from app.jobs import proxy_expiration
from app.jobs import notification_checker

cli = typer.Typer()
cli.add_typer(proxy_expiration.app, name="proxy-expiration")
cli.add_typer(notification_checker.app, name="notification-checker")

if __name__ == "__main__":
    cli()
