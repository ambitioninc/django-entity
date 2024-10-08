#!/usr/bin/env python
import sys

# These lines allow nose tests to work in Python 3.10
import collections.abc
collections.Callable = collections.abc.Callable

# Show warnings about django deprecations - uncomment for version upgrade testing
import warnings
from django.utils.deprecation import RemovedInNextVersionWarning
warnings.filterwarnings('always', category=DeprecationWarning)
warnings.filterwarnings('always', category=PendingDeprecationWarning)
warnings.filterwarnings('always', category=RemovedInNextVersionWarning)

from settings import configure_settings

if __name__ == '__main__':
    configure_settings()

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
