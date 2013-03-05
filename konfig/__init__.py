# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
""" Configuration file reader / writer
"""
import re
import os
from configparser import ConfigParser, ExtendedInterpolation


_IS_NUMBER = re.compile('^-?[0-9].*')
_IS_ENV_VAR = re.compile('\$\{(\w.*)?\}')


class EnvironmentNotFoundError(Exception):
    pass


class ExtendedEnvironmentInterpolation(ExtendedInterpolation):
    def __init__(self):
        self.environment = {k: v.replace('$', '$$')
            for k, v in os.environ.iteritems()
        }

    def before_get(self, parser, section, option, value, defaults):
        defaults = self.environment
        defaults['HERE'] = '$${HERE}'
        if parser.filename:
            defaults['HERE'] = os.path.dirname(parser.filename)
        result = super(ExtendedEnvironmentInterpolation, self).before_get(
            parser, section, option, value, defaults,
        )
        if '\n' in result:
            return [line for line in [self._unserialize(line)
                                    for line in result.split('\n')]
                    if line != '']
        return self._unserialize(result)

    def before_set(self, parser, section, option, value):
        result = super(ExtendedEnvironmentInterpolation, self).before_set(
            parser, section, option, value,
        )
        return self._serialize(result)

    def _serialize(self, value):
        if isinstance(value, bool):
            value = str(value).lower()
        elif isinstance(value, (int, long)):
            value = str(value)
        elif isinstance(value, (list, tuple)):
            value = '\n'.join(['    %s' % line for line in value]).strip()
        else:
            value = str(value)
        return value

    def _unserialize(self, value):
        if not isinstance(value, basestring):
            # already converted
            return value

        value = value.strip()
        if _IS_NUMBER.match(value):
            try:
                return int(value)
            except ValueError:
                pass
        elif value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        elif value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        return value


class Config(ConfigParser):

    def __init__(self, filename):
        # let's read the file
        ConfigParser.__init__(self, **self._configparser_kwargs())
        if isinstance(filename, basestring):
            self.filename = filename
            self.read(filename)
        else:
            self.filename = None
            self.read_file(filename)

    def optionxform(self, option):
        return option

    def _read(self, fp, filename):
        # first pass
        ConfigParser._read(self, fp, filename)

        # let's expand it now if needed
        defaults = self.defaults()

        if 'extends' in defaults:
            extends = defaults['extends']
            if not isinstance(extends, list):
                extends = [extends]
            for file_ in extends:
                self._extend(file_)

    def get_map(self, section=None):
        """returns a dict representing the config set"""
        if section:
            return dict(self.items(section))

        res = {}
        for section in self:
            for option, value in self[section].iteritems():
                option = '%s.%s' % (section, option)
                res[option] = value
        return res

    def mget(self, section, option):
        value = self.get(section, option)
        if not isinstance(value, list):
            value = [value]
        return value

    def _extend(self, filename):
        """Expand the config with another file."""
        if not os.path.isfile(filename):
            raise IOError('No such file: %s' % filename)
        parser = ConfigParser(**self._configparser_kwargs())
        parser.optionxform = lambda option: option
        parser.filename = filename
        parser.read([filename])
        for section in parser:
            if section in self:
                for option in parser[section]:
                    if option not in self[section]:
                        self[section][option] = parser[section][option]
            else:
                self[section] = parser[section]

    def _configparser_kwargs(self):
        return {
            'interpolation': ExtendedEnvironmentInterpolation(),
            'comment_prefixes': ('#',),
        }


class SettingsDict(dict):
    """A dict subclass with some extra helpers for dealing with app settings.

    This class extends the standard dictionary interface with some extra helper
    methods that are handy when dealing with application settings.  It expects
    the keys to be dotted setting names, where each component indicates one
    section in the settings heirarchy.  You get the following extras:

        * setdefaults:  copy any unset settings from another dict
        * getsection:   return a dict of settings for just one subsection

    """

    separator = "."

    def copy(self):
        """D.copy() -> a shallow copy of D.

        This overrides the default dict.copy method to ensure that the
        copy is also an instance of SettingsDict.
        """
        new_items = self.__class__()
        for k, v in self.iteritems():
            new_items[k] = v
        return new_items

    def getsection(self, section):
        """Get a dict for just one sub-section of the config.

        This method extracts all the keys belonging to the name section and
        returns those values in a dict.  The section name is removed from
        each key.  For example::

            >>> c = SettingsDict({"a.one": 1, "a.two": 2, "b.three": 3})
            >>> c.getsection("a")
            {"one": 1, "two", 2}
            >>>
            >>> c.getsection("b")
            {"three": 3}
            >>>
            >>> c.getsection("c")
            {}

        """
        section_items = self.__class__()
        # If the section is "" then get keys without a section.
        if not section:
            for key, value in self.iteritems():
                if self.separator not in key:
                    section_items[key] = value
        # Otherwise, get keys prefixed with that section name.
        else:
            prefix = section + self.separator
            for key, value in self.iteritems():
                if key.startswith(prefix):
                    section_items[key[len(prefix):]] = value
        return section_items

    def setdefaults(self, *args, **kwds):
        """Import unset keys from another dict.

        This method lets you update the dict using defaults from another
        dict and/or using keyword arguments.  It's like the standard update()
        method except that it doesn't overwrite existing keys.
        """
        for arg in args:
            if hasattr(arg, "keys"):
                for k in arg:
                    self.setdefault(k, arg[k])
            else:
                for k, v in arg:
                    self.setdefault(k, v)
        for k, v in kwds.iteritems():
            self.setdefault(k, v)
