from submin.path.path import Path
import os
import re

class c_apacheconf():
	'''Commands to change apache config
Usage:
    apacheconf create all [<template>] - create cgi config, save to multiple files
                                         using <template>

(deprecated, do not use)
    apacheconf create                  - create config interactively
    apacheconf create wsgi <output>    - create wsgi config, save to <output>
    apacheconf create cgi <output>     - create cgi config, save to <output>

    With the 'all' method, separate files are created and the different sections
    (submin itself, svn, trac) are created as different files as well. This is
    now the recommended way of creating apache configs. The template will be
    used to create each filename. For example: '/etc/apache2/conf.d/XYZ.conf'
    The following files will be created in '/etc/apache2/conf.d/':
     - XYZ-webui-cgi.conf
     - XYZ-webui-wsgi.conf
     - XYZ-svn.conf
     - XYZ-trac-cgi.conf
     - XYZ-trac-modpython.conf

    By default <template> is '<submin env>/conf/apache.conf'.

    Now the files can be included in separate <VirtualHost> blocks. For each
    component, there can be multiple options, for example there is a CGI webui
    and a WSGI webui. Include only one of these: CGI is most common, but
    slowest. For more performance, choose WSGI if available'''

	def __init__(self, sa, argv):
		self.sa = sa
		self.argv = argv

	def _get_value_from_user(self, prompt, default):
		defval = self.defaults[default]
		a = raw_input("%s [%s]> " % (prompt, defval))

		if a == '':
			self.init_vars[default] = defval
			return

		p = Path(a)
		if type(p) == type(defval):
			self.init_vars[default] = p
			return

		self.init_vars[default] = a

	def interactive(self):
		print '''
Choosing CGI or WSGI is a trade-off between speed and compatibility. CGI is
enabled for most Apache installations, but slower than WSGI. If you have WSGI
enabled (mod_wsgi), you should choose WSGI.
'''
		self._get_value_from_user("wsgi or cgi?", 'type')

		print '''
The Apache config file will be created, all we need now is a filename. THIS
FILE WILL BE OVERWRITTEN WITHOUT ANY WARNING! The default option is good in
most installations. Just include this file in your main apache config. The
recommended way is to include it in a VirtualHost.
'''
		self._get_value_from_user("Output file? (will be overwritten!!)",
			'output')

		self._apache_conf_create()

	def subcmd_create(self, argv):
		from submin.models import options
		if len(argv) == 0:
			try:
				self.interactive()
			except KeyboardInterrupt:
				print
			return

		minargs = -1 # invalid command
		if argv[0] in ('wsgi', 'cgi'):
			minargs = 2
		if argv[0] in ('all'):
			minargs = 1

		if minargs > -1 and len(argv) >= minargs:
			for key, value in self.defaults.iteritems():
				self.init_vars[key] = value

			self.init_vars['type'] = argv[0]
			if len(argv) > 1: # not always true with 'all'
				self.init_vars['output'] = argv[1]
			else: #  argv[0] must be 'all'
				self.init_vars['output'] = options.env_path() + 'conf' + 'apache.conf'

			self._apache_conf_create()
			return

		self.sa.execute(['help', 'apacheconf'])
		return

	def _apache_conf_create(self):
		from time import strftime
		self.init_vars['REQ_FILENAME'] = '%{REQUEST_FILENAME}'; # hack :)
		self.init_vars['datetime_generated'] = strftime("%Y-%m-%d %H:%M:%S")
		header = '''# Generated on: %(datetime_generated)s
# This config file was automatically created with submin2-admin. If you use
# this command again, it will overwrite all changes to this file. The
# recommanded way to regenerate this file is to change the config with
# submin2-admin and run:
#
#   submin2-admin %(submin env)s apacheconf create %(type)s %(output)s
# 
#
# To make this config active, you have to include it in your apache
# config. The recommended way is to include it in one of your virtual hosts:
#
# <Virtualhost *:80>
#     <other configuration>
#
#     Include <path to this file>
# </VirtualHost>
#
''' % self.init_vars

		output_type = self.init_vars['type']
		if self.auth_type == "sql":
			if output_type != "all":
				header += self._apache_conf_auth_sql_head()
			else:
				header_webui = header
				header_svn = header + self._apache_conf_auth_sql_head("svn")
				header_trac = header + self._apache_conf_auth_sql_head("trac")

		if output_type in ('cgi', 'all'):
			submin_cgi = self._apache_conf_cgi(self.init_vars)
		if output_type in ('wsgi', 'all'):
			submin_wsgi = self._apache_conf_wsgi(self.init_vars)

		submin_svn = self._apache_conf_svn(self.init_vars)
		submin_trac_modpy = self._apache_conf_trac_modpy(self.init_vars)
		submin_trac_cgi = self._apache_conf_trac_cgi(self.init_vars)

		if self.auth_type == "sql":
			footer = self._apache_conf_auth_sql_foot(self.init_vars)

		if output_type == 'all':
			template = str(self.init_vars['output'])
			if template.endswith('.conf'):
				template = template[:-len('.conf')]

			fname_submin_cgi = template + '-webui-cgi.conf'
			fname_submin_wsgi = template + '-webui-wsgi.conf'
			fname_svn = template + '-svn.conf'
			fname_trac_modpy = template + '-trac-modpython.conf'
			fname_trac_cgi = template + '-trac-cgi.conf'
			file(fname_submin_cgi, 'w').write(header_webui + submin_cgi)
			file(fname_submin_wsgi, 'w').write(header_webui + submin_wsgi)
			file(fname_svn, 'w').write(header_svn + submin_svn + footer)
			file(fname_trac_modpy, 'w').write(header_trac + submin_trac_modpy + footer)
			file(fname_trac_cgi, 'w').write(header_trac + submin_trac_cgi + footer)
			print 'Apache files created:\n', "\n".join([fname_submin_cgi,
				fname_submin_wsgi, fname_svn, fname_trac_modpy, fname_trac_cgi])
		else:
			submin_type = submin_cgi if output_type == 'cgi' else submin_wsgi
			contents = header + submin_type + submin_svn + submin_trac + footer
			try:
				os.makedirs(os.path.dirname(self.init_vars['output']))
			except IOError:
				# Assume 'directory exists', else, exception will follow
				pass

			file(str(self.init_vars['output']), 'w').write(contents)

			print '''Apache file created: %(output)s''' % self.init_vars

		print '''
   Please include the relevent files in your apache config. If you have
   selected to generate all files (recommended), do not include all files,
   but only select one version (e.g. svn and webui-cgi but not webui-wsgi).

   Also make sure that you have the appropriate modules installed and enabled.
   Depending on your choices, these may include: mod_dav_svn, mod_authz_svn,
   mod_authn_dbd, mod_dbd, mod_wsgi, mod_cgi, mod_cgid and mod_python'''

	def _apache_conf_cgi(self, vars):
		import os
		if os.environ.has_key('PYTHONPATH'):
			vars['setenv_pythonpath'] = 'SetEnv PYTHONPATH %s' % os.environ['PYTHONPATH']
		else:
			vars['setenv_pythonpath'] = ''

		if vars['submin base url'] == "/":
			# Doesn't make sense to have an Alias if the base url is "/"
			vars['origin'] = 'DocumentRoot "%(www dir)s"' % vars
		else:
			# The alias is really picky about trailing slashes. Our experience
			# finds that no trailing slashes works best for both src and dst.
			# This is because without a trailing slash, the following will also
			# work as expected: http://localhost/submin
			submin_base_url = str(vars['submin base url']).rstrip('/')
			www_dir = str(vars['www dir']).rstrip('/')
			vars['origin'] = 'Alias "%s" "%s"' % (submin_base_url, www_dir)

		# We are including the cgi stuff twice, once for cgi and once for cgid.
		# if we could assume apache 2.3+, we could have used SetEnv and If and
		# only include it once. Since we assume <2.3, we have to include it
		# twice (or make another file and include that twice)
		cgi_directives = '''
        # first define scriptalias, otherwise the Alias will override all
        ScriptAlias "%(submin base url)ssubmin.cgi" "%(cgi-bin dir)s/submin.cgi"
        %(origin)s
        <Directory "%(cgi-bin dir)s">
            Order allow,deny
            Allow from all

            Options ExecCGI FollowSymLinks
            AddHandler cgi-script py cgi pl

            SetEnv SUBMIN_ENV %(submin env)s
            %(setenv_pythonpath)s
        </Directory>
        <Directory "%(www dir)s">
            Order allow,deny
            Allow from all
            Options FollowSymLinks

            RewriteEngine on
            RewriteBase %(submin base url)s

            RewriteCond %(REQ_FILENAME)s !-f
            RewriteRule ^(.+)$ submin.cgi/$1

            RewriteRule ^$ submin.cgi/
        </Directory>
 ''' % vars

		vars['cgi directives'] = cgi_directives

		apache_conf_cgi = '''
    # WARNING!
    # Please note that the following section is included twice: if you change
    # something, do not forget to make the same change below. Or better, do
    # not change anything, since this file is generated anyway!
	# (it is included twice so it works with both prefork and worker/event)
    <IfModule mod_cgi.c>
%(cgi directives)s
    </IfModule>
    <IfModule mod_cgid.c>
%(cgi directives)s
    </IfModule>
    # only show the error page if both cgi and cgid are not loaded
    <IfModule !mod_cgi.c>
        <IfModule !mod_cgid.c>
            AliasMatch "^%(submin base url)s" %(www dir)s/nocgi.html
            <Location "%(submin base url)s">
                Order allow,deny
                Allow from all
            </Location>
        </IfModule>
    </IfModule>
''' % vars
		return apache_conf_cgi

	def _apache_conf_wsgi(self, vars):
		apache_conf_wsgi = '''
    <IfModule mod_wsgi.c>
        WSGIScriptAlias "%(submin base url)s" %(www dir)s/submin.wsgi
        AliasMatch ^%(submin base url)scss/(.*) %(www dir)s/css/$1
        AliasMatch ^%(submin base url)simg/(.*) %(www dir)s/img/$1
        AliasMatch ^%(submin base url)sjs/(.*) %(www dir)s/js/$1

        <Location "%(submin base url)s">
            Order allow,deny
            Allow from all
            SetEnv SUBMIN_ENV "%(submin env)s"
        </Location>
    </IfModule>
    <IfModule !mod_wsgi.c>
        AliasMatch "^%(submin base url)s" %(www dir)s/nowsgi.html
        <Location "%(submin base url)s">
            Order allow,deny
            Allow from all
        </Location>
    </IfModule>
''' % vars
		return apache_conf_wsgi

	def _apache_conf_svn(self, vars):
		if self.auth_type == "sql":
			auth_conf = self._apache_conf_auth_sql(vars)
		elif self.auth_type == "htaccess":
			auth_conf = self._apache_conf_auth_sql(vars)

		vars['apache_conf_auth'] = auth_conf

		apache_conf_svn = '''
    <IfModule mod_dav_svn.c>
        <Location %(svn base url)s>
            DAV svn
            SVNParentPath %(svn dir)s

            AuthType Basic
            AuthName "Subversion repository"

%(apache_conf_auth)s

            # Authorization
            AuthzSVNAccessFile %(authz file)s

            Satisfy Any
            Require valid-user
        </Location>
    </IfModule>
''' % vars
		return apache_conf_svn

	def _apache_conf_auth_sql_head(self, component="all"):
		"""Generate SQL auth section, including a fallback in case the module
		wasn't loaded. Only the component that is selected is created, choosing
		from 'webui', 'svn', 'trac' and 'all'. The 'all' options creates all
		components"""
		conf = '''
<IfModule !mod_authn_dbd.c>
    # Nothing should work, so show a page describing this'''

		if component in ("trac", "all"):
			conf += '''
    AliasMatch "^%(trac base url)s" %(www dir)s/nomodauthndbd.html
    <Location "%(trac base url)s">
        Order allow,deny
        Allow from all
    </Location>''' % self.init_vars
		if component in ("svn", "all"):
			conf += '''
    AliasMatch "^%(svn base url)s" %(www dir)s/nomodauthndbd.html
    <Location "%(svn base url)s">
        Order allow,deny
        Allow from all
    </Location>''' % self.init_vars
		if component in ("webui", "all"):
			conf += '''
    AliasMatch "^%(submin base url)s" %(www dir)s/nomodauthndbd.html
    <Location "%(submin base url)s">
        Order allow,deny
        Allow from all
    </Location>''' % self.init_vars

		conf += '''
</IfModule>
<IfModule mod_authn_dbd.c>
    DBDriver sqlite3
    DBDParams "%(submin env)s/conf/submin.db"
''' % self.init_vars
		return conf

	def _apache_conf_auth_sql_foot(self, vars):
		conf = '''
</IfModule>
''' % vars
		return conf

	def _apache_conf_auth_sql(self, vars):
		conf = '''
            # Authentication
            AuthBasicProvider dbd
            AuthDBDUserPWQuery "SELECT password FROM users WHERE name=%%s"
''' % vars
		return conf

	def _apache_conf_auth_htaccess(self, vars):
		conf = '''
            # Authentication
            AuthUserFile %(access file)s
''' % vars
		return conf

	def _apache_conf_trac_modpy(self, vars):
		if self.auth_type == "sql":
			auth_conf = self._apache_conf_auth_sql(vars)
		elif self.auth_type == "htaccess":
			auth_conf = self._apache_conf_auth_sql(vars)

		vars['apache_conf_auth'] = auth_conf

		apache_conf_trac = '''
    # Only load if mod_python is available
    <IfModule mod_python.c>
        <Location "%(trac base url)s">
           SetHandler mod_python
           PythonInterpreter main_interpreter
           PythonHandler trac.web.modpython_frontend
           PythonOption TracEnvParentDir "%(trac dir)s"
           PythonOption TracUriRoot "%(trac base url)s"
        </Location>

        <LocationMatch "%(trac base url)s/[^/]+/login">
           AuthType Basic
           AuthName "Trac"

%(apache_conf_auth)s

           Require valid-user
        </LocationMatch>
        AliasMatch "%(trac base url)s[^/]+/chrome/site" %(trac dir)s/$1/htdocs
        <Directory %(trac dir)s/*/htdocs>
          Order allow,deny
          Allow from all
        </Directory>
    </IfModule>
    <IfModule !mod_python.c>
        AliasMatch "^%(trac base url)s" %(www dir)s/nomodpython.html
        <Location "%(trac base url)s">
            Order allow,deny
            Allow from all
        </Location>
    </IfModule>
''' % vars
		return apache_conf_trac

	def _apache_conf_trac_cgi(self, vars):
		if self.auth_type == "sql":
			auth_conf = self._apache_conf_auth_sql(vars)
		elif self.auth_type == "htaccess":
			auth_conf = self._apache_conf_auth_sql(vars)

		# nts = No Trailing Slash
		trac_base_url_nts = str(vars['trac base url']).rstrip('/')
		vars['trac base url nts'] = trac_base_url_nts

		# We are including the cgi stuff twice, once for cgi and once for cgid.
		# if we could assume apache 2.3+, we could have used SetEnv and If and
		# only include it once. Since we assume <2.3, we have to include it
		# twice (or make another file and include that twice)
		cgi_directives = '''
        ScriptAlias %(trac base url nts)s %(cgi-bin dir)s/trac.cgi
        <Location "%(trac base url nts)s">
          SetEnv TRAC_ENV_PARENT_DIR "%(trac dir)s"
        </Location>

        <LocationMatch "%(trac base url nts)s/[^/]+/login">
           AuthType Basic
           AuthName "Trac"

%(apache_conf_auth)s

           Require valid-user
        </LocationMatch>
        AliasMatch "%(trac base url nts)s/[^/]+/chrome/site" %(trac dir)s/$1/htdocs
        <Directory %(trac dir)s/*/htdocs>
          Order allow,deny
          Allow from all
        </Directory>
 ''' % vars
		vars['cgi directives'] = cgi_directives

		apache_conf_trac = '''
    # WARNING!
    # Please note that the following section is included twice: if you change
    # something, do not forget to make the same change below. Or better, do
    # not change anything, since this file is generated anyway!
	# (it is included twice so it works with both prefork and worker/event)
    <IfModule mod_cgi.c>
%(cgi directives)s
    </IfModule>
    <IfModule mod_cgid.c>
%(cgi directives)s
    </IfModule>
    # only show the error page if both cgi and cgid are not loaded
    <IfModule !mod_cgi.c>
        <IfModule !mod_cgid.c>
            AliasMatch "^%(submin base url)s" %(www dir)s/nocgi.html
            <Location "%(submin base url)s">
                Order allow,deny
                Allow from all
            </Location>
        </IfModule>
    </IfModule>
''' % vars
		return apache_conf_trac

	def urlpath(self, url):
		"""Strip scheme and hostname from url, leaving only the path. Also
		fix slashes (need leading, trailing, no doubles)"""
		# remove schema + hostname
		url = re.sub('^[^:]*://[^/]+', '/', url)

		# strip trailing slash
		url = url.rstrip('/')
		# add leading slash
		if url == "" or url[0] != '/':
			url = '/' + url

		url = re.sub('/+', '/', url)

		if not url.endswith('/'):
			url += '/'

		return url

	def run(self):
		os.environ['SUBMIN_ENV'] = self.sa.env
		from submin.models import options

		if len(self.argv) < 1:
			self.sa.execute(['help', 'apacheconf'])
			return

		self.defaults = {
			'type': 'wsgi',
			'output': options.env_path() + 'conf' + 'apache.conf'
		}
		self.init_vars = {
			'submin env': self.sa.env,
			'www dir': self.sa.basedir_www,
			'cgi-bin dir': os.path.join(self.sa.env, 'cgi-bin'),
			'submin base url': self.urlpath(options.value('base_url_submin')),
			'svn base url': self.urlpath(options.value('base_url_svn')),
			'trac base url': self.urlpath(options.value('base_url_trac')),
			'svn dir': options.env_path('svn_dir'),
			'trac dir': options.env_path('trac_dir'),
			'authz file': options.env_path('svn_authz_file'),
		}
		self.auth_type = options.value('auth_type')

		# variables depending on auth type
		if self.auth_type == "sql":
			pass
		elif options.value('auth_type') == "htaccess":
			self.init_vars.update({
				'access file': options.value('auth_access_file'),
			})

		try:
			subcmd = getattr(self, 'subcmd_%s' % self.argv[0])
		except AttributeError:
			self.sa.execute(['help', 'apacheconf'])
			return

		subcmd(self.argv[1:])
