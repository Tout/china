import os
import yaml
import pystache
import re
import types
import subprocess
import tempfile

def env_prefix (ctx):
    return ctx.region_config['env_ensign'] + "-"

def env_var (name):
    try:
        return os.environ[name]
    except:
        return None

def load_yaml (yml, context):
    with open(yml, 'r') as stream:
        specs = pystache.render(stream.read(), context)
        specs = yaml.load(specs)
    return specs

def subst_homedir(dir):
    if "~/" in dir:
        return dir.replace("~/", os.environ['HOME']+"/")
    return dir

def is_empty(x):
    return x is None or len(str(x).strip()) == 0

def remove_empty_string_from_list(list):
    return [x for x in list if not is_empty(x)]

def to_list (arg):
    if isinstance(arg, types.ListType):
        return arg
    return remove_empty_string_from_list(re.split("[ ,]", str(arg)))


IP_CIDR_RE = re.compile(r"(?<!\d\.)(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(/\d{1,2}(?!\d|(?:\.\d)))?")

def is_cidr (arg):
    return IP_CIDR_RE.match(arg) is not None

def is_noop():
    return env_var('CHINA_DEBUG') is not None

def execute_shell_internal(args):
    env = {}

    test_log = env_var('CHINA_TEST_LOG')
    if test_log is not None:
        # args.insert(0, 'CHINA_TEST_LOG='+test_log)
        env['CHINA_TEST_LOG'] = test_log

    ec2_stubs = env_var('EC2_STUBS')
    if ec2_stubs is not None:
        args[0] = ec2_stubs + "/" + args[0]

    active_unit = env_var('ACTIVE_UNIT')
    if active_unit is not None:
        env['ACTIVE_UNIT'] = active_unit

    cmd = ''
    for arg in args:
        if len(cmd) > 0:
            cmd += " "
        if ' ' in arg:
            cmd += "'"+arg+"'"
        else:
            cmd += arg
    print cmd

    if is_noop():
        return None

    # manually check the PATH, not sure why this is needed
    for path in os.environ['PATH'].split(':'):
        if os.path.exists(path+"/"+args[0]):
            args[0] = path + "/" + args[0]

    # print "execute_shell (args="+str(args)+") with env="+str(env)
    child = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    return child

def execute_shell(args):
    child = execute_shell_internal(args)
    if child is None:
        return ["", ""]
    output = child.communicate()
    # print "execute_shell got output="+str(output)
    return output

def execute_shell_returncode(args):
    child = execute_shell_internal(args)
    if child is None:
        return 0
    child.communicate()
    return child.returncode

def write_temp_file(data, prefix=None):
    if prefix is None:
        prefix = "temp_"
    temp = tempfile.NamedTemporaryFile(delete=False, prefix=prefix)
    temp.write(data)
    temp.close()
    return temp.name

def write_file(data, path):
    with open(path, "w") as file:
        file.write(data)

def find_element_on_line_starting_with(output, start, word_index):
    for line in output.split("\n"):
        if line.startswith(start):
            return line.split()[word_index]
    raise Exception("no line starting with " + start + " not found in output: "+output)


