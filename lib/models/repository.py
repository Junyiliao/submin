class Repository:
	class DoesNotExist(Exception):
		pass

	def __init__(self, config, name):
		self.name = name
		self.config = config

#		if self.name not in config.authz.groups():
#			raise Repository.DoesNotExist

		self.paths = self.config.authz.paths(self.name)
		self.paths.sort()

	def __str__(self):
		return self.name