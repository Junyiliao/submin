import os
from submin.path.path import Path

class c_initenv():
	'''Initialize a new enviroment
Usage:
    initenv                        - Create environment interactively
    initenv <option> [option ...]  - Create environment from options

Options:
    svn_dir=<path>           - base path for svn repositories (default: svn)
    trac_dir=<path>          - dir for trac environments (default: trac)
    http_base=<url>          - base url (default: /)
    trac_url=<url>           - url to trac (default: trac)
    submin_url=<url>         - url to submin (default: submin)
    svn_url=<url>            - url to subversion repositories (default: svn)

Notes:
    The *_url arguments are all relative to http_base, unless they begin with
    "http://" or with "/".

    Paths are relative to environment directory, unless they begin with "/".'''

	needs_env = False

	def __init__(self, sa, argv):
		self.sa = sa
		self.env = Path(self.sa.env)
		self.argv = argv
		self.defaults = {
			'svn_dir': Path('svn'),
			'trac_dir': Path('trac'),
			'http_base': Path('/'),
			'trac_url': Path('trac'),
			'submin_url': Path('submin'),
			'svn_url': Path('svn'),
			'create_user': 'yes'
		}
		self.init_vars = {
			'conf_dir': Path('conf'),
		}
		self.init_vars.update({
			'authz': self.init_vars['conf_dir'] + Path('authz'),
			'htpasswd': self.init_vars['conf_dir'] + Path('htpasswd'),
		})

	def prompt_user(self, prompt, key):
		defval = self.defaults[key]
		a = raw_input("%s [%s]> " % (prompt, defval))

		if a == '':
			self.set_init_var(key, defval)
			return

		self.set_init_var(key, a)

	def set_init_var(self, key, val):
		defval = self.defaults[key]
		if type(Path('')) == type(defval):
			p = Path(str(val), append_slash=defval.append_slash)
			self.init_vars[key] = p
			return

		self.init_vars[key] = val

	def interactive(self):
		print '''
Please provide a location for the Subversion repositories. For new Subversion
repositories, the default setting is ok. If the path is not absolute, it will
be relative to the submin environment. If you want to use an existing
repository, please provide the full pathname to the Subversion parent
directory (ie. /var/lib/svn).
'''
		self.prompt_user("Path to the repository?", 'svn_dir')

		print '''
Please provide a location for the parent dir of Trac environments. For a new
installation, the default setting is ok. If you don't want to use Trac, the
default setting is also ok. For existing Trac environments, please provide
the full path.
'''
		self.prompt_user("Path to trac environment?", 'trac_dir')

		print '''
The HTTP path tells Submin where the website is located relative to the root.
This is needed for proper working of the website. Submin will be accesible
from <http base>/submin, Subversion will be accessible from <http base>/svn.
If you use Trac, it will be accessible from <http base>/trac.
'''
		self.prompt_user("HTTP base?", 'http_base')

		self.create_env()

	def create_dir(self, directory):
		"""Create a relative or absulute directory, if it doesn't exist already"""
		if not directory.absolute:
			directory = self.env + directory

		if not os.path.exists(str(directory)):
			try:
				os.makedirs(str(directory), mode=0700)
			except OSError, e:
				print 'making dir %s failed, do you have permissions?' % \
						str(directory)
				raise e

	def generate_cgi(self):
		fname = self.env + "cgi-bin" + "submin.cgi"
		fp = open(str(fname), "w+")

		suggestion = '/path/to/submin'
		if os.environ.has_key("PYTHONPATH"):
			suggestion = os.path.abspath(os.environ["PYTHONPATH"].split(":")[0])

		fp.write("""#!/usr/bin/env python

# If you installed submin in a non-standard path, uncomment the two lines below
# and insert your submin path.
#import sys
#sys.path.append("%s")

from submin.dispatch.cgirunner import run
run()
""" % suggestion)
		fp.close()
		os.chmod(str(fname), 0755)

	def create_env(self):
		"""This is called when all info is gathered"""
		for key, value in self.defaults.iteritems():
			if not self.init_vars.has_key(key):
				self.init_vars[key] = value

		try:
			self.create_dir(self.env)
			self.create_dir(self.init_vars['svn_dir'])
			self.create_dir(self.init_vars['conf_dir'])
			self.create_dir(self.init_vars['trac_dir'])
			self.create_dir(Path('auth'))
			self.create_dir(Path('cgi-bin'))
		except OSError:
			return # already printed error message

		self.generate_cgi()
		self.sa.execute(['config', 'defaults'])

		# check http_base
		p = self.init_vars['http_base']
		if str(p) == "":
			self.init_vars['http_base'] = Path("/")

		# write changes to config
		import submin.models.options
		o = submin.models.options.Options()

		options = {
			'base_url_submin': self._get_url('submin_url'),
			'base_url_svn': self._get_url('svn_url'),
			'base_url_trac': self._get_url('trac_url'),
			'auth_type': 'sql',
			'svn_dir': str(self.init_vars['svn_dir']),
			'trac_dir': str(self.init_vars['trac_dir']),
			'svn_authz_file': str(self.init_vars['authz']),
		}
		for (key, value) in options.iteritems():
			o.set_value(key, value)

		# add a user
		from submin.models.user import User
		from submin.models.group import Group
		
		if self.init_vars['create_user'] == "yes":
			# add an admin user
			u = User.add('admin')
			password = u.generate_password()
			u.is_admin = True

			print "\nAdded an admin user with password '%s'\n" % password

		self.sa.execute(['unixperms', 'fix'])
		confdir = self.env + 'conf'
		cgiconf = self.env + 'conf' + 'apache.cgi.conf'
		wsgiconf = self.env + 'conf' + 'apache.wsgi.conf'
		self.sa.execute(['apacheconf', 'create', 'cgi', str(cgiconf)])
		self.sa.execute(['apacheconf', 'create', 'wsgi', str(wsgiconf)])

	def _get_url(self, key):
		p = self.init_vars[key]
		if p.absolute or str(p).startswith("http://"):
			return str(p)

		return str(self.init_vars['http_base'] + p)

	def run(self):
		if os.path.exists(str(self.env)):
			print "Directory already exists, won't overwrite"
			return False

		if len(self.argv) < 1:
			try:
				self.interactive()
			except KeyboardInterrupt:
				print
				return False
			return True

		for arg in self.argv:
			if '=' not in arg:
				self.sa.execute(['help', 'initenv'])
				return False

			(key, val) = arg.split('=', 1)
			if not self.defaults.has_key(key):
				print "\nSorry, I don't understand `%s':\n" % key
				self.sa.execute(['help', 'initenv'])
				return False

			self.set_init_var(key, val)

		self.create_env()
		return True