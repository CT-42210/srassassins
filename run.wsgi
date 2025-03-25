import sys
sys.path.insert(0, '/var/www/srAssasin2')

activate = '/root/.local/share/virtualenvs/crimsassions-B3cZCAKl'

with open(activate) as file_:
    exec(file.read(), dict(__file__=activate))

from run import app