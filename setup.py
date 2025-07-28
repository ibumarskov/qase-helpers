from setuptools import find_packages, setup

with open('README.md') as f:
    long_description = f.read()

setup(
    name='qase-helpers',
    version='0.0.1',
    packages=find_packages(),
    python_requires='>=3.9',
    install_requires=[
        'qase-api-client',
    ],
    entry_points={
        'console_scripts': [
            'qase-helper = qase_helper.cmd.helper:main'
        ]
    },
    # metadata to display on PyPI
    author='Ilya Bumarskov',
    author_email='ibumarskov@gmail.com',
    description='Auxiliary scripts for processing test results for the Qase test management platform.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/ibumarskov/qase-helpers",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Topic :: Software Development :: Quality Assurance',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords='qase junit',
)
