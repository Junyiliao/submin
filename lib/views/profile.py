from template import evaluate
from models.user import User
from models.group import Group
from authz.authz import Authz
from authz.htpasswd import HTPasswd
from dispatch.response import Response
from config.config import Config

class Profile(object):
	def handler(self, req, path, ajax=False):
		if ajax:
			return self.ajaxhandler(req, path)

		config = Config()

		authz = Authz(config.get('svn', 'authz_file'))
		htpasswd = HTPasswd(config.get('svn', 'access_file'))

		localvars = {}
		users = []

		authz_users = authz.users()
		username = 'test'
		htpasswd_users = htpasswd.users()
		if username in htpasswd_users:
			email = ''
			if authz_users.has_key(username):
				if authz_users[username].has_key('email'):
					email = authz_users[username]['email']
			user = User(username, email)

		groups = []
		authz_groups = authz.groups()
		authz_groups.sort()
		for group in authz_groups:
			if username in authz.members(group):
				groups.append(group)

		localvars['user'] = user
		localvars['groups'] = groups
		formatted = evaluate('../templates/profile', localvars)
		return Response(formatted)

	def ajaxhandler(self, req, path):
		try:
			email = req.get.get('email')
			config = Config()
			authz = Authz(config.get('svn', 'authz_file'))
			authz.setUserProp('test', 'email', email)
		except Exception, e:
			email = ''

		return Response('ajax email is: ' + email + ' echt waar!')
