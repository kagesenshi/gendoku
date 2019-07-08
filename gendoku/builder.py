import os
import fnmatch
from yaml import load as yaml_load
try:
    from yaml import CLoader as YAMLLoader
except ImportError:
    from yaml import Loader as YAMLLoader

from io import StringIO
import jinja2
import subprocess
import shutil

FILTERS = [
   'pandoc-plantuml'
]

LUA_FILTERS = [
    'odt-custom-styles.lua',
]

LUA_FILTER_DEPS = ['util.lua']

FILTER_DIR=os.path.join(os.path.dirname(__file__), 'filters')

ENV_CONFIG_KEYS = {
    'PLANTUML_BIN': 'plantuml_bin',
    'PLANTUML_JAR': 'plantuml_jar'
}

class TypeConfig(object):

    def __init__(self, extensions, headeropen, headerclose):
        self.extensions = extensions
        self.headeropen = headeropen
        self.headerclose = headerclose

class TypeRegistry(object):
    
    def __init__(self):
        self.registry = {}

    def add(self, typeconfig):
        for ext in typeconfig.extensions:
            self.registry[ext] = typeconfig

    def get_typeconfig(self, filename):
        ext = '.' + filename.split('.')[-1]
        return self.registry.get(ext, None)

class Document(object):

    def __init__(self, path, typeconfig):
        self.path = path
        self.dirname = os.path.dirname(path)
        self.filename = os.path.basename(path)
        self.extension = self.filename.split('.')[-1]
        self.typeconfig = typeconfig
        self._parse()

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def _parse(self):
        with open(self.path) as f:
            # extract headers
            headers = ''
            body = ''
            run_header = False
            run_body = False
            c = 0
            for l in f:
                if self.typeconfig:
                    if c == 0 and l.strip() == self.typeconfig.headeropen:
                        run_header = True
                    elif c == 0:
                        run_body = True
    
                    if c > 0 and run_header and l.strip() == self.typeconfig.headerclose:
                        run_header = False
                        run_body = True
                        continue

                    if run_header and c > 0:
                        headers += l
                else:
                    run_body = True

                if run_body:
                   body += l

                c += 1

        self.meta = yaml_load(headers, Loader=YAMLLoader)
        self.body = body

    def __repr__(self):
        return '<Document "%s">' % self.filename

class DocumentTree(object):

    def __init__(self, name):
        self.name = name
        self.tree = {}

    def __getitem__(self, key):
        return self.tree[key]

    def __getattr__(self, key):
        try:
            return self.tree[key]
        except KeyError:
            raise AttributeError(key)

    def dirs(self):
        res = {}
        for n,o in self.tree.items():
            if isinstance(o, DocumentTree):
                res[n] = o
        return res

    def files(self):
        res = {}
        for n,o in self.tree.items():
            if isinstance(o, Document):
                res[n] = o

        return res

    def add(self, doc: Document):
        path = doc.dirname.split('/')[1:]
        current = self
        for p in path:
            if p in current.tree.keys():
                current = current.tree[p]
            else:
                subtree =  DocumentTree(p)
                current.tree[p] = subtree
                current = subtree
        current.tree[doc.filename] = doc

    def __repr__(self):
        return '<DocumentTree "%s">' % self.name

class Walker(object):

    def __init__(self, types: TypeRegistry):
        self.types = types

    def walk(self, path):
        for root, d, files in os.walk(path):
            for f in files:
                fpath = '/'.join( [root] + [f])
                yield Document(fpath, typeconfig=self.types.get_typeconfig(fpath))


class Config(object):

    def __init__(self, path):
        with open(path) as f:
            self.config = yaml_load(f.read(), Loader=YAMLLoader)
    def __getitem__(self, key):
        return self.config[key]

def build():
    # scan content directories

    config = Config('config.yml')
    types = TypeRegistry()
    types.add(TypeConfig(['.md'], '---', '---'))
    types.add(TypeConfig(['.rst'], '---', '---'))


    walker = Walker(types=types)
    documents = []
    for d in walker.walk('content'):
        documents.append(d)

    doctree = DocumentTree('content')
    for d in documents:
        doctree.add(d)

    stream = StringIO()
    with open(config['document']) as fd:
        template = jinja2.Template(fd.read())
        stream.write(template.render(doctree=doctree, config=config))

    stagingfile = os.path.join(config['builddir'],
            '.'.join(config['document'].split('.')[:-1]))

    outputfile = os.path.join(config['builddir'], config['output'])
    with open(stagingfile, 'w') as fd:
        stream.seek(0)
        fd.write(stream.read())

    command = [config['pandoc'], stagingfile]

    for filtr in LUA_FILTER_DEPS:
        shutil.copyfile(os.path.join(FILTER_DIR, filtr),
                os.path.join(config['builddir'],filtr))

    for filtr in LUA_FILTERS:
        shutil.copyfile(os.path.join(FILTER_DIR, filtr),
                os.path.join(config['builddir'],filtr))
        command += ['--lua-filter', os.path.join(config['builddir'],filtr)]

    for filtr in FILTERS:
        command += ['--filter', filtr]

    command += ['--reference-doc', config['reference']]

    variables = {
        'title': config['title']
    }
    for k,v in variables.items():
        command += ['-M','%s:%s' % (k,v)]

    command += ['-o', outputfile]

    envs = os.environ.copy()
    for k, v in ENV_CONFIG_KEYS.items():
        envs[k] = config[v]

    print("Running: %s" % ' '.join(command))
    proc = subprocess.Popen(command, env=envs)
    res = proc.wait()
    if res == 0:
        print('Wrote %s' % outputfile)
