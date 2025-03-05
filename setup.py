from setuptools import setup, find_packages


def get_version():
    version = {}
    with open("ivoryos/version.py") as f:
        exec(f.read(), version)
    return version["__version__"]


setup(
    name='ivoryos',
    version=get_version(),
    packages=find_packages(exclude=['example', 'example.*', 'docs', 'docs.*']),
    include_package_data=True,
    description='an open-source Python package enabling Self-Driving Labs (SDLs) interoperability',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Ivory Zhang',
    author_email='ivoryzhang@chem.ubc.ca',
    license='MIT',
    install_requires=[
        # "ax-platform",
        "bcrypt",
        "Flask-Login",
        "Flask-Session",
        "Flask-SocketIO",
        "Flask-SQLAlchemy",
        "Flask-WTF",
        "SQLAlchemy-Utils",
        # "openai",
        "python-dotenv",
    ],
    url='https://gitlab.com/heingroup/ivoryos'
)
