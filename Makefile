.PHONY: docs build test coverage build_rpm

ifndef VTENV_OPTS
VTENV_OPTS = "--no-site-packages"
endif

build:	
	virtualenv $(VTENV_OPTS) .
	bin/python setup.py develop

test:	bin/nosetests
	bin/nosetests -x konfig

coverage: bin/coverage
	bin/nosetests --with-coverage --cover-html --cover-html-dir=html --cover-package=konfig

bin/nosetests: bin/python
	bin/pip install nose

bin/coverage: bin/python
	bin/pip install coverage

bin/tox: bin/python
	bin/pip install tox

tox: bin/tox
	bin/tox
