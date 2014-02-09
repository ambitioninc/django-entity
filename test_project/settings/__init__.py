import os

SETTINGS_PATH = os.path.dirname(__file__)
PROJECT_PATH = os.path.dirname(os.path.dirname(__file__))

ENVIRONMENT_VARIABLE = 'develop'
if 'www' in os.path.abspath(__file__).split('/'):
    ENVIRONMENT_VARIABLE = 'production'
elif "CIRCLECI" in os.environ:
    ENVIRONMENT_VARIABLE = 'circleci'

file_name = 'base_{0}.py'.format(ENVIRONMENT_VARIABLE)
file_path = os.path.join(SETTINGS_PATH, file_name)
execfile(file_path)
