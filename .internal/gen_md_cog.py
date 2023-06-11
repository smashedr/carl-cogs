import os
import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Union, Dict
from gen_md_cog_list import get_data_from_path

carl_cogs = Path('C:\\Users\\Shane\\IdeaProjects\\carl-cogs')
template_file = 'cog.jinja2'

cog_data = get_data_from_path(carl_cogs)
for cog, data in cog_data.items():
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template(template_file)
    rendered = template.render({'data': data})
    print(rendered)
    file = carl_cogs / f'{cog}/README.md'
    with open(file, 'w') as f:
        f.write(rendered)
