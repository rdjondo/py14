from setuptools import setup, find_packages

DEPRECATION_NOTE = "Think of renaming this package is moving \nto a more up to data version of Python. \n For example pycpp2a ?"
print(DEPRECATION_NOTE)

setup(name="py14", packages=find_packages())
