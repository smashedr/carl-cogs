import os
import sys
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

cog_jinja = 'cog.jinja'
info_jinja = 'info.jinja'
init_jinja = 'init.jinja'

base_dir = Path(__file__).parent.resolve()
cogs_path = base_dir.parent.parent.resolve()


if __name__ == '__main__':
    print(f'base_dir: {base_dir}')
    print(f'cogs_path: {cogs_path}')
    if len(sys.argv) < 1+2:
        print(f'Usage: {sys.argv[0]} [Name] [module]')
        sys.exit(1)
    data = {
        'name': sys.argv[1],
        'module': sys.argv[2],
    }
    print(f'data: {data}')
    print('-'*40)
    cog_dir = cogs_path / sys.argv[2]
    if os.path.exists(cog_dir):
        raise ValueError(f'Cog Directory Already Exist: {cog_dir}')

    os.mkdir(cog_dir)
    print(f'Created: {cog_dir}')

    env = Environment(loader=FileSystemLoader(base_dir))

    template = env.get_template(cog_jinja)
    rendered = template.render({'data': data})
    with open(cog_dir / f'{sys.argv[2]}.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(rendered)
        print(f'Generated: {f.name}')

    template = env.get_template(info_jinja)
    rendered = template.render({'data': data})
    with open(cog_dir / 'info.json', 'w', encoding='utf-8', newline='\n') as f:
        f.write(rendered)
        print(f'Generated: {f.name}')

    template = env.get_template(init_jinja)
    rendered = template.render({'data': data})
    with open(cog_dir / '__init__.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(rendered)
        print(f'Generated: {f.name}')
