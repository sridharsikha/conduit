"""Conduit CLI — wraps the API."""
import typer
app = typer.Typer(name="conduit", help="Self-serve private networking for any cloud SaaS")

@app.command()
def connect(service: str, env: str = "dev", bw: int = 100):
    """Request a private connection."""
    typer.echo(f"Requesting {service} in {env} at {bw} Mbps...")
    typer.echo("POST /api/v1/connections → (call API)")

@app.command()
def status(conn_id: str):
    """Check connection status."""
    typer.echo(f"GET /api/v1/connections/{conn_id}/status")

@app.command()
def env(conn_id: str, format: str = "dotenv"):
    """Get env vars for a connection."""
    typer.echo(f"GET /api/v1/connections/{conn_id}/env?format={format}")

@app.command()
def ls(status: str = "active"):
    """List connections."""
    typer.echo(f"GET /api/v1/connections?status={status}")

@app.command()
def disconnect(conn_id: str):
    """Revoke a connection."""
    typer.echo(f"DELETE /api/v1/connections/{conn_id}")

@app.command()
def serve(config: str = "conduit.yaml", port: int = 8443):
    """Start the Conduit API server."""
    import uvicorn
    import os
    os.environ["CONDUIT_CONFIG"] = config
    typer.echo(f"Starting Conduit on port {port}...")
    uvicorn.run("conduit.main:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    app()
