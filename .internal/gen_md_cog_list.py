import os
import json
import re
from pathlib import Path
from typing import Union, Dict


def get_data_from_path(path: Union[Path, str]) -> Dict[str, dict]:
    data_dict = {}
    for directory in os.listdir(path):
        dir_path = os.path.join(path, directory)
        if not os.path.isdir(dir_path):
            continue
        json_file_path = os.path.join(dir_path, 'info.json')
        if not os.path.isfile(json_file_path):
            continue
        with open(json_file_path, 'r') as info_file:
            info_data = json.load(info_file)
            info_data['cog'] = directory
            data_dict[directory] = info_data
    return data_dict


def parse_cog_data(cog_data: Dict[str, dict]) -> str:
    public, hidden = [], []
    for _, d in cog_data.items():
        if d['disabled']:
            continue
        if d['hidden']:
            hidden.append(d)
        else:
            public.append(d)
    lines = ['### Public Cogs\n\n| Cog | Description |\n| --- | --- |']
    for cog in public:
        lines.append(gen_line(cog))
    lines.append('\n### Internal/Hidden Cogs\n\n| Cog | Description |\n| --- | --- |')
    for cog in hidden:
        lines.append(gen_line(cog))
    return '\n'.join(lines)


def gen_line(cog):
    pre = '**'
    if 'deprecated' in cog['tags']:
        pre += 'Deprecated'
    elif 'wip' in cog['tags']:
        pre += 'WIP'
    else:
        if 'api' in cog['tags']:
            pre += 'API, '
        if 'redis' in cog['tags']:
            pre += 'Redis, '
    pre = re.sub(', $', '', pre).strip()
    pre = pre + '** - ' if pre.strip('*') else ''
    name = cog['cog']
    return f"| **[{name}]({name}/{name}.py)** | {pre}{cog['description']} |"


data = get_data_from_path('C:\\Users\\Shane\\IdeaProjects\\carl-cogs')
wiki_string = parse_cog_data(data)
print(wiki_string)
