#!/usr/bin/env python3
"""CLI for Fates Engine."""
import click
from orchestrator import orchestrator


@click.command()
@click.option('--birth', '-b', required=True, help='Birth datetime: "1990-06-15 14:30"')
@click.option('--location', '-l', required=True, help='Birth location: "London, UK"')
@click.option('--gender', '-g', default='unspecified', help='Gender: male/female/unspecified')
@click.option('--name', '-n', default='Unknown', help='Subject name')
@click.option('--output', '-o', default='./reports', help='Output directory')
def generate(birth, location, gender, name, output):
    """Generate astrological master report."""
    click.echo("🌟 Fates Engine Core v1.0")
    click.echo("=" * 60)

    try:
        report_path = orchestrator.generate_report(
            birth_datetime=birth,
            location=location,
            gender=gender,
            name=name,
            output_dir=output
        )
        click.echo(f"\n✨ Report generated successfully!")
        click.echo(f"   Location: {report_path}")
    except Exception as e:
        click.echo(f"\n❌ Error: {e}")
        import traceback
        click.echo(traceback.format_exc())
        raise click.Abort()


@click.group()
def cli():
    """Fates Engine - World-Class Astrological Analysis"""
    pass


cli.add_command(generate)

if __name__ == '__main__':
    cli()