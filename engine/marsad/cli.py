"""Command line: marsad --help"""

import getpass
import logging

import typer
from sqlalchemy import select

from marsad.config import get_settings
from marsad.db import session_factory, session_scope

app = typer.Typer(help="Marsad engine commands", no_args_is_help=True)
sources_app = typer.Typer(help="Inspect and verify sources", no_args_is_help=True)
app.add_typer(sources_app, name="sources")


def _logging(verbose: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command("db-upgrade")
def db_upgrade():
    """Apply database migrations."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    cfg = Config()  # no ini file needed: works both from a checkout and from an installed package
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations"))
    command.upgrade(cfg, "head")


@app.command()
def seed():
    """Load or refresh sources, taxonomy and the starter glossary (editorial choices are kept)."""
    from marsad.seed import seed_all

    with session_scope() as s:
        typer.echo(seed_all(s))


@app.command("create-user")
def create_user(email: str, name: str, role: str = typer.Option("editor", help="admin | editor")):
    """Create an editor account (password is asked interactively)."""
    from marsad.api.auth import hash_password
    from marsad.models import User

    password = getpass.getpass("Password: ")
    if len(password) < 10:
        raise typer.BadParameter("password must be at least 10 characters")
    with session_scope() as s:
        user = s.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email)
            s.add(user)
        user.name, user.role, user.password_hash, user.is_active = name, role, hash_password(password), True
    typer.echo(f"user {email} saved with role {role}")


@sources_app.command("list")
def sources_list():
    """Show sources with rights level and fetch health."""
    from marsad.models import Source

    with session_scope() as s:
        for src in s.scalars(select(Source).order_by(Source.is_active.desc(), Source.slug)):
            state = "active " if src.is_active else "inactive"
            health = "error: " + src.last_error[:60] if src.last_error else (
                f"ok {src.last_success_at:%Y-%m-%d %H:%M}" if src.last_success_at else "never fetched")
            typer.echo(f"{src.slug:24} {state} rights={src.rights_level.value} {src.fetch_method:8} {health}")


@sources_app.command("set")
def sources_set(slug: str, active: bool = typer.Option(None, "--active/--inactive"),
                feed_url: str = typer.Option(None, help="replace the feed or listing URL")):
    """Activate/deactivate a source or fix its feed URL (rights changes go through the editor dashboard)."""
    from marsad.models import Source

    with session_scope() as s:
        src = s.scalar(select(Source).where(Source.slug == slug))
        if src is None:
            raise typer.BadParameter(f"unknown source {slug}")
        if active is not None:
            src.is_active = active
        if feed_url:
            src.feed_url = feed_url
        typer.echo(f"{src.slug}: active={src.is_active} feed={src.feed_url}")


@sources_app.command("check")
def sources_check(slug: str = typer.Argument(None, help="one source; default: all with a feed URL")):
    """Fetch feeds without saving anything, to verify URLs, robots.txt and full-text availability."""
    from marsad.fetch.http import PoliteClient
    from marsad.fetch.listing import parse_listing
    from marsad.fetch.rss import parse_feed
    from marsad.extract.html import paragraphs_from_fragment
    from marsad.models import Source
    from marsad.normalize import word_count

    settings = get_settings().model_copy(update={"per_host_delay_s": 1.0})
    client = PoliteClient(settings)
    with session_scope() as s:
        q = select(Source).where(Source.feed_url.is_not(None)).order_by(Source.slug)
        if slug:
            q = q.where(Source.slug == slug)
        for src in s.scalars(q):
            try:
                res = client.get(src.feed_url)
                if src.fetch_method == "listing":
                    entries = parse_listing(res.content.decode("utf-8", "replace"), res.url, src.listing_config)
                else:
                    entries = parse_feed(res.content)
                full = sum(1 for e in entries if e.content_html and word_count(paragraphs_from_fragment(e.content_html)) >= 250)
                first = entries[0].title[:50] if entries else "-"
                typer.echo(f"OK    {src.slug:24} {len(entries):3} items, {full:3} with full text | {first}")
            except Exception as exc:  # noqa: BLE001
                typer.echo(f"FAIL  {src.slug:24} {type(exc).__name__}: {str(exc)[:90]}")
    client.close()


@app.command()
def fetch(slug: str = typer.Argument(None)):
    """Fetch one source (or all due sources) now."""
    from marsad.fetch.http import PoliteClient
    from marsad.fetch.run import due_sources, fetch_source
    from marsad.models import Source

    _logging()
    client = PoliteClient(get_settings())
    with session_scope() as s:
        targets = [s.scalar(select(Source).where(Source.slug == slug))] if slug else due_sources(s)
        for src in targets:
            typer.echo(f"{src.slug}: {fetch_source(s, src, client)} new")


@app.command()
def worker(once: bool = typer.Option(False, help="run a single cycle and exit"), verbose: bool = False):
    """Run the fetch + pipeline worker."""
    from marsad.fetch.http import PoliteClient
    from marsad.worker import make_llm, run_forever, run_once

    _logging(verbose)
    settings = get_settings()
    if once:
        from marsad.embed import make_embedder

        typer.echo(run_once(session_factory(), make_llm(settings), PoliteClient(settings), settings,
                            make_embedder(settings)))
    else:
        run_forever(session_factory(), settings)


@app.command()
def embed():
    """Embed every published document that has no vector yet (backfill after enabling semantic search)."""
    from marsad.embed import embed_pending, make_embedder

    embedder = make_embedder(get_settings())
    if embedder is None:
        raise typer.BadParameter("no embedding backend: set MARSAD_VOYAGE_API_KEY or MARSAD_EMBED_BACKEND")
    total = 0
    with session_scope() as s:
        while n := embed_pending(s, embedder):
            total += n
    typer.echo(f"embedded {total} documents with {embedder.model}")


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000):
    """Serve the HTTP API."""
    import uvicorn

    uvicorn.run("marsad.api.app:app_factory", factory=True, host=host, port=port)


@app.command()
def demo(publish: bool = True):
    """Load three fictional demo articles (no network, no model calls)."""
    from marsad.demo import load_demo
    from marsad.seed import seed_all

    with session_scope() as s:
        seed_all(s)
        ids = load_demo(s, get_settings(), publish_items=publish)
    typer.echo(f"demo documents: {ids}")


if __name__ == "__main__":
    app()
