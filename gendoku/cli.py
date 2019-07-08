import click 
from .builder import build as run_build

@click.group()
def cli():
    pass

@cli.command()
def genproject():
    print("Generate project")

@cli.command()
def build():
    run_build()

def main():
    cli()    
