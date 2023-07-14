import json
import os
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Dict, Union

main_jinja = 'main.jinja2'
cog_jinja = 'cog.jinja2'

base_dir = Path(__file__).parent.resolve()
cogs_path = base_dir.parent.parent.resolve()


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


def get_cog_stats(cog_data: Dict[str, dict]) -> Dict[str, int]:
    stats = {'total': 0, 'public': 0, 'hidden': 0}
    tags = {}
    for _, data in cog_data.items():
        stats['total'] += 1
        if data['hidden']:
            stats['hidden'] += 1
        else:
            stats['public'] += 1
        for tag in data['tags']:
            if tag not in tags:
                tags[tag] = 1
            else:
                tags[tag] += 1
    stats['tags'] = tags
    return stats


if __name__ == '__main__':
    print(f'base_dir: {base_dir}')
    print(f'cogs_path: {cogs_path}')
    print('-'*40)

    cog_data: Dict[str, dict] = get_data_from_path(cogs_path)
    stats: Dict[str, int] = get_cog_stats(cog_data)
    env = Environment(loader=FileSystemLoader(base_dir))

    template = env.get_template(main_jinja)
    rendered = template.render({'cog_data': cog_data, 'stats': stats})
    with open(cogs_path / 'README.md', 'w', encoding='utf-8', newline='\n') as f:
        f.write(rendered)
        print(f'Generated: {f.name}')

    for cog, data in cog_data.items():
        template = env.get_template(cog_jinja)
        rendered = template.render({'data': data})
        with open(cogs_path / f'{cog}/README.md', 'w', encoding='utf-8', newline='\n') as f:
            f.write(rendered)
            print(f'Generated: {f.name}')
