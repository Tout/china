__author__ = 'jonathan'

import time
import util
import ec2
import json
import sys
import types
from pprint import pprint, pformat

POST_BOOTSTRAP = 'post_bootstrap'

def iid2privipv4(iid):
    output = util.execute_shell(["iid2privipv4", iid])
    return output[0].strip()

def knife_environment_show(env_name):
    return util.execute_shell(["knife", "environment", "show", "-F", "json", env_name])[0]

def add_to_haproxy(unit, host, iid):
    while True:
        # add it to the chef config
        output = knife_environment_show(unit.env_name)
        if util.is_noop():
            temp = "debug-knife-file.json"
        else:
            data = json.loads(output)

            block = 'haproxy-' + unit.unit_name
            region_context = unit.region_context
            host = util.env_prefix(region_context)+unit.env_name+"-"+unit.unit_name+"-"+iid+"."+ region_context.region_config['unit_domain']
            ip = iid2privipv4(iid)

            # print("looking for override/haproxy/"+block+"/servers/ to add host:"+host)
            data['override_attributes']['haproxy'][block]["servers"].append([host, ip])

            temp = util.write_temp_file(json.dumps(data))

        util.execute_shell(["knife", "environment", "from", "file", temp])

        # verify host is now in output
        output = knife_environment_show(unit.env_name)
        print "looking for host="+host+" in output: "+str(output)
        if util.is_noop():
            return

        if host in output:
            return
        else:
            time.sleep(10)

def generate_deployer_script(unit, deployer_base_uri=None):
    if deployer_base_uri is None:
        deployer_base_uri = unit.region_context.region_config['deployer_base_uri']
    suffix = ""
    if unit.role_name != unit.unit_name:
        suffix = "/" + unit.role_name
    return "#!/bin/bash\ncurl "+deployer_base_uri+"/deployer/$(ec2metadata --instance-id)"+suffix

def run_instance(unit, instance_number):

    config = unit.config

    region_config = unit.region_context.region_config
    region_name = unit.region_context.region

    ami = region_config['ami']
    args = ["ec2-run-instances", ami,
            "--instance-initiated-shutdown-behavior", "terminate",
            "-g", unit.env_group_name,
            "-g", unit.group_name]

    if 'extra_groups' in config:
        for group in util.to_list(config['extra_groups']):
            args.append("-g")
            args.append(group)

    if 'instance_size' in config:
        size = config['instance_size']
    else:
        size = region_config['default_instance_size']

    args += ["-t", size, "-k", region_config['keypair']]

    if 'user_data' in config:
        if unit.role_name not in config['user_data']:
            raise Exception("no user_data found in unit "+unit.unit_name+" for role "+unit.role_name)

        data = config['user_data'][unit.role_name]
        if isinstance(data, types.StringType) and data == 'deployer':
            # super simple case - default deployer action
            data = generate_deployer_script(unit)

        elif isinstance(data, types.DictType) and data.has_key('deployer'):
            deployer = data['deployer']
            if not deployer.startswith('http'):
                raise Exception("custom deployer url is invalid ("+deployer+") in yml: "+unit.yml)
            # custom deployer action
            data = generate_deployer_script(unit, deployer)
        else:
            # whatever kind of shell script you want
            data = str(config['user_data'][unit.role_name]).strip()

        data_file = util.write_temp_file(data, "run_"+unit.unit_name+"_"+unit.role_name+"_userdata_")
        args += [ "-f", data_file ]

    if 'default_availability_zone' in config and region_name in config['default_availability_zone']:
        azone = config['default_availability_zone'][region_name]
        if azone not in region_config['EC2_REGION_AZS']:
            raise Exception("Availability Zone '"+azone+"' is not allowed in region "+region_name+". Valid values: "+str(region_config['EC2_REGION_AZS']))
        args += [ "-z", azone]

    elif 'default_availability_zone' in region_config:
        args += [ "-z", region_config['default_availability_zone'] ]

    output = util.execute_shell(args)
    if util.is_noop():
        iid = "i-debug"
    else:
        iid = util.find_element_on_line_starting_with(output[0], "INSTANCE", 1)
    return iid

def bootstrap(unit, host, iid):
    node_name = unit.group_name + "-" + iid
    region_config = unit.region_context.region_config
    # print ">>>>>bootstrap: region_context.region_config="+str(region_config)
    knife_args = ["knife", "bootstrap", host,
                  "--run-list", "role["+unit.role_name+"]",
                  "--node-name", node_name,
                  "--ssh-user", "ubuntu",
                  "-i", util.subst_homedir(region_config['KEY_DIR']) +"/"+region_config['keypair']+".pem",
                  "--sudo", "--no-host-key-verify",
                  "--environment", unit.env_name]
    util.execute_shell(knife_args)

    util.execute_shell(["ec2-create-tags", iid, "--tag", "Name=" + node_name])
    util.execute_shell(["create-cname", node_name+".unit", host+".", "86400"])

    if POST_BOOTSTRAP in unit.config:
        add_to_haproxy(unit, host, iid)
        for type in ['sg', 'asg', 'tag']:
            key = 'refresh_' + type + '_hosts'
            if key in unit.config[POST_BOOTSTRAP]:
                for group in util.to_list(unit.config[POST_BOOTSTRAP][key]):
                    util.execute_shell(["ssh-"+type+"-hosts", group, "sudo", "chef-client"])

def add_instance(unit, instance_number, iid):
    host = None
    while host is None:
        host = str(util.execute_shell(["iid2hn", iid])[0]).strip()
        if util.is_noop():
            host = 'debug.host.example.com'

        # print "iid2hn returned "+host
        if host != "pending" and len(host) > 5 and len(host) < 100:
            break
        time.sleep(5)

    # "waiting for $HOST ssh to come up"
    while True:
        rval = util.execute_shell_returncode(["nc", "-z", host, "22"])
        if rval != 0:
            time.sleep(5)
        else:
            # "$HOST ready for use"
            break

    bootstrap(unit, host, iid)

class ChinaUnit:
    def __init__(self, ctx, unit_name, role_name=None, num_instances=1):
        self.region_context = ctx
        self.unit_name = unit_name
        if role_name is None:
            self.role_name = unit_name
        else:
            self.role_name = role_name
        self.num_instances = int(num_instances)

        self.env_name = ctx.specific_environment['name']
        self.env_group_name = util.env_prefix(ctx) + self.env_name
        self.group_name = self.env_group_name + "-" + unit_name

        self.context = dict(ctx.region_config.items() + ctx.default_environment.items() + ctx.specific_environment.items())
        self.context['unit_name'] = unit_name
        self.context['env_name'] = self.env_name
        self.context['env_group_name'] = self.env_group_name
        self.yml = ctx.blueprints_dir + "/units/" + unit_name + "/unit.yml"
        self.config = util.load_yaml(self.yml, self.context)
        # print "loaded "+unit_name+" yml: "+pformat(self.config)
        if 'override_region_context' in self.config:
            for key, value in self.config['override_region_context'].iteritems():
                self.region_context.region_config[key] = value
        # print("config====")
        # pprint(self.config)

    def create_ec2_group(self):
        ec2.create_group(self.group_name, "Environment "+self.env_name+" Unit "+self.unit_name)

    def instantiate(self):
        for i in range(1, self.num_instances+1):
            run_instance(self, i)

    def add(self):
        for i in range(1, self.num_instances+1):
            iid = run_instance(self, i)
            add_instance(self, i, iid)

def instantiate_units(ctx, unit_name, role_name, num_instances):
    unit = ChinaUnit(ctx, unit_name, role_name, num_instances)
    unit.instantiate()

def add_units(ctx, unit_name, role_name, num_instances):
    unit = ChinaUnit(ctx, unit_name, role_name, num_instances)
    unit.add()
