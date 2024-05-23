from setuptools import setup, find_packages

setup(
    name='sdl-webui',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    description='Design experiment on any Python-based SDLs.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Ivory Zhang',
    author_email='ivoryzhang@chem.ubc.ca',
    license='MIT',
    install_requires=[
        "ax-platform",
        "bcrypt",
        "Flask-Login",
        "Flask-Session",
        "Flask-SocketIO",
        "Flask-SQLAlchemy",
        "mysqlclient==2.1.1",
        "SQLAlchemy-Utils",
    ],
    url='https://gitlab.com/heingroup/web_controller'
)
