import click 
from .builder import build as run_build
from cookiecutter.main import cookiecutter
from pkg_resources import resource_filename

@click.group()
def cli():
    pass

@cli.command()
def create():
    cookiecutter(resource_filename('gendoku', 'templates/basic'))

@cli.command()
def build():
    run_build()

def main():
    cli()    
