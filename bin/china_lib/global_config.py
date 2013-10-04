import util

ENV_BLUEPRINT_DIR="CHINA_BLUEPRINT_DIR"
ENV_EC2_REGION="CHINA_EC2_REGION"

VALID_REGIONS={'east': 'us-east-1', 'west': 'us-west-2'}


def config_basic_args(parser):
    # load defaults if they are set
    blueprint_dir = util.env_var(ENV_BLUEPRINT_DIR)
    region = util.env_var(ENV_EC2_REGION)

    parser.add_argument('-b', '--blueprints',
                        help='path to blueprints directory, defaults to ' + ENV_BLUEPRINT_DIR + ' environment variable (current value: ' + str(blueprint_dir) + ')',
                        default=blueprint_dir,
                        required=blueprint_dir is None)

    parser.add_argument('-r', '--region',
                        help='one of: ' + str(list(VALID_REGIONS)) + ', defaults to ' + ENV_EC2_REGION + ' environment variable (current value: ' + str(region) + ')',
                        default=region, required=region is None)

    parser.add_argument('-e', '--environment',
                        help='the environment to operate in',
                        required=True)

def config_common_args(parser, valid_commands, default_command):

    config_basic_args(parser)

    parser.add_argument('-u', '--unit',
                        help='the name of the unit to work with',
                        required=True)

    parser.add_argument('-c', '--command',
                        help='one of: '+str(list(valid_commands.keys())),
                        default=default_command,
                        required=default_command is None)

    parser.add_argument('-n', '--noop',
                        help='do not execute any commands, but show what would be done',
                        action='store_const',
                        const=True,
                        default=False)

def add_role_arg(parser):
    parser.add_argument('-l', '--role',
                        help='the role of the unit (default is the unit name)')
