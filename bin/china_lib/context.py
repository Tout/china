import os
from global_config import *
import util

SUPPORTED_ENVS = 'supported_envs'

class ChinaContextError:
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return "ChinaContextError: "+self.message

class ChinaContext:
    def __init__(self, blueprints_dir, command, valid_commands):
        self.blueprints_dir = blueprints_dir
        self.valid_commands = valid_commands
        if command not in self.valid_commands:
            raise ChinaContextError("invalid command: " + command + ", valid commands are: " + str(self.valid_commands.keys()))
        self.command = command

    def __repr__(self):
        return "ChinaContext{"+self.command+", "+self.region+", "+self.environment+"}"

    def set_region(self, region):
        if region not in VALID_REGIONS:
            raise ChinaContextError("invalid region: " + args.region + ", valid regions are: " + str(VALID_REGIONS.keys()))
        self.region = region
        self.region_fullname = VALID_REGIONS[region]

        # Load the region configuration, using the system environment for variable substitution
        self.default_region_config = util.load_yaml(self.blueprints_dir + "/regions/region.default.yml", os.environ)
        self.region_config_file = self.blueprints_dir + "/regions/region." + self.region_fullname + ".yml"
        self.specific_region_config = util.load_yaml(self.region_config_file, os.environ)

        # Merge the specific region config onto the defaults, then let os.environ override anything
        self.region_config = dict(self.default_region_config.items() + self.specific_region_config.items() + os.environ.items())

        # Now that we've loaded the region config, check if the environment is supported there
        if SUPPORTED_ENVS not in self.region_config:
            raise ChinaContextError("region '" + self.region + "' has no supported_envs!")

    def set_environment(self, env):
        if env not in self.region_config[SUPPORTED_ENVS]:
            raise ChinaContextError("environment '"+env+"' is not supported in region '" + self.region + "', check supported_envs in region config: "+self.region_config_file)

        self.environment = env

        # Load the environment configuration, using the region configuration for variable substitution
        self.default_environment = util.load_yaml(self.blueprints_dir + "/envs/env.default.yml", self.region_config)
        env_yml = self.blueprints_dir + "/envs/env." + env + ".yml"

        self.specific_environment = {}
        if os.path.isfile(env_yml):
            self.specific_environment = util.load_yaml(env_yml, self.region_config)
        self.specific_environment['name'] = env
