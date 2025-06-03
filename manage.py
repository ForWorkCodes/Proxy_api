import typer
from app.jobs import proxy_expiration

cli = typer.Typer()
cli.add_typer(proxy_expiration.app, name="proxy-expiration")

if __name__ == "__main__":
    cli()
