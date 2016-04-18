from setuptools import setup

setup(  
    name='ck2_parser',
    version='0.1',
    description='Utilities to parse CK2 save files',
    url='https://github.com/jamilnavarro/ck2_parser',
    author='Jamil Navarro',
    author_email='jamilnavarro@gmail.com',
    license='GPL',
    packages=['ck2_parser'],
    entry_points = { 
        'console_scripts' : ['ck2_file_parser=ck2_parser.command_line:main']
    },
    zip_safe=False
)
