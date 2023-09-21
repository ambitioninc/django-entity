# Contributing
Contributions and issues are most welcome! All issues and pull requests are
handled through GitHub on the 
[ambitioninc repository](https://github.com/ambitioninc/django-entity/issues).
Also, please check for any existing issues before filing a new one. If you have
a great idea but it involves big changes, please file a ticket before making a 
pull request! We want to make sure you don't spend your time coding something
that might not fit the scope of the project.

## Development

> Prerequisites:
> - [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running on your system
> - Postgres default host port (5432) is available (likely need to stop any other running postgres servers)

Fork and clone your fork then use the docker compose services for development tasks.

**Lint**
```shell
docker compose run --rm lint
```

**Test**
```shell
docker compose run --rm test
```

**Test (with coverage)**
```shell
docker compose run --rm test-coverage
```

While 100% code coverage does not make a library bug-free, it significantly
reduces the number of easily caught bugs! Please make sure coverage is at 100%
before submitting a pull request!

**Shell**
```shell
docker compose run --rm shell
```

For dependency changes, rebuild before running:
```shell
docker compose build
```

To reset everything, use docker compose down with additional flags for images and volumes:
```shell
docker compose down --volumes --remove-orphans --rmi local
```

## Code Styling
Please arrange imports with the following style

```python
# Standard library imports
import os

# Third party package imports
from mock import patch
from django.conf import settings

# Local package imports
from entity.version import __version__
```

Please follow 
[Google's python style](http://google-styleguide.googlecode.com/svn/trunk/pyguide.html)
guide wherever possible.



## Release Checklist

Before a new release, please go through the following checklist:

* Bump version in entity/version.py
* Git tag the version
* Upload to pypi:
```bash
pip install wheel
python setup.py sdist bdist_wheel upload 
```

## Vulnerability Reporting

For any security issues, please do NOT file an issue or pull request on GitHub!
Please contact [security@ambition.com](mailto:security@ambition.com) with the 
GPG key provided on [Ambition's website](http://ambition.com/security/).
