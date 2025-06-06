import typer
from app.jobs import proxy_expiration
from app.jobs import notification_checker
from app.jobs import proxy_prolong

cli = typer.Typer()
cli.add_typer(proxy_expiration.app, name="proxy-expiration")
cli.add_typer(proxy_prolong.app, name="proxy-prolong")
cli.add_typer(notification_checker.app, name="notification-checker")

if __name__ == "__main__":
    cli()
