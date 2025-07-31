# Configuration file for the Sphinx documentation builder.
import os
import sys
import urllib

import requests

# -- General configuration
sys.path.insert(0, os.path.abspath('../../'))
from ivoryos.version import __version__


# appending suite readme.rst to doc

external_readme = [
    {
        "name": 'plugin.rst',
        "url": "https://gitlab.com/heingroup/ivoryos-suite/ivoryos-plugin-template/-/raw/main/README.rst"
    },
    {
        "name": 'client.rst',
        "url": "https://gitlab.com/heingroup/ivoryos-suite/ivoryos-client/-/raw/main/README.rst"
    },
    {
        "name": 'mcp.rst',
        "url": "https://gitlab.com/heingroup/ivoryos-suite/ivoryos-mcp/-/raw/main/README.rst"
    }
]

for item in external_readme:
    readme_url = item['url']
    name = item['name']
    output_path = os.path.join(os.path.dirname(__file__), name)
    r = requests.get(readme_url, verify=False)
    if not os.path.exists(output_path):
        with open(output_path, "wb") as f:
            f.write(r.content)

# -- Project information
project = 'ivoryOS'
copyright = '2024, Ivory Zhang'
author = 'Ivory Zhang, Lucy Hao'
version = __version__

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinxcontrib.httpdomain',
    'sphinxcontrib.autohttp.flask',
    'sphinxcontrib.autohttp.flaskqref'
]

install_requires = [
    'sphinx-autodoc-typehints'
]
autodoc_mock_imports = ["flask_sqlalchemy", "another_hard_to_import_lib"]


intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

templates_path = ['_templates']

html_static_path = ['_static']
html_css_files = [
    'custom.css',
]

html_allow_raw_html = True

# -- Options for HTML output

html_theme = 'sphinx_rtd_theme'

# -- Options for EPUB output
epub_show_urls = 'footnote'

# The master toctree document.
master_doc = 'index'
