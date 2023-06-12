import json
import os
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Dict, Union

cogs_path = Path('C:\\Users\\Shane\\IdeaProjects\\carl-cogs')
readme_jinja = 'readme.jinja2'
cog_file = 'cog.jinja2'


def get_data_from_path(path: Union[Path, str]) -> Dict[str, dict]:
    data_dict = {}
    for directory in os.listdir(path):
        dir_path = os.path.join(path, directory)
        if not os.path.isdir(dir_path):
            continue
        json_file = os.path.join(dir_path, 'info.json')
        if not os.path.isfile(json_file):
            continue
        with open(json_file, 'r') as info_file:
            info_data = json.load(info_file)
            info_data['cog'] = directory
            data_dict[directory] = info_data
            print(f'Parsed: {info_file.name}')
    return data_dict


if __name__ == '__main__':
    cog_data: Dict[str, dict] = get_data_from_path(cogs_path)
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template(readme_jinja)
    rendered = template.render({'cog_data': cog_data})
    with open(cogs_path / 'README.md', 'w') as f:
        f.write(rendered)
        print(f'Generating: {f.name}')

    for cog, data in cog_data.items():
        env = Environment(loader=FileSystemLoader('.'))
        template = env.get_template(cog_file)
        rendered = template.render({'data': data})
        with open(cogs_path / f'{cog}/README.md', 'w') as f:
            f.write(rendered)
            print(f'Generating: {f.name}')