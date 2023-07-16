import os
import json
from pathlib import Path

INSTALL_MSG = (
    '**{name}:** View Help: `[p]help {name}`\n'
    '**README:** <https://github.com/smashedr/carl-cogs/tree/master/{module}>\n'
)
DEFAULTS = {
    'author': ['shanerice'],
    'end_user_data_statement': 'Caveat Emptor!',
}

base_dir = Path(__file__).parent.resolve()
cogs_path = base_dir.parent.parent.resolve()


if __name__ == '__main__':
    for directory in os.listdir(cogs_path):
        dir_path = cogs_path / directory
        if not os.path.isdir(dir_path):
            continue
        file_path = dir_path / 'info.json'
        if not os.path.isfile(file_path):
            continue
        with open(file_path, 'r+') as file:
            print(file_path)
            data = json.load(file)
            data.update(DEFAULTS)
            data['install_msg'] = INSTALL_MSG.format(**data, module=directory)
            if data['tags']:
                tags = ', '.join([f'`{x}`' for x in data['tags']])
                data['install_msg'] += f'\n**Tags:** {tags}'
            print(data)
            file.seek(0)
            json.dump(data, file, indent=4)
            file.truncate()
            break
