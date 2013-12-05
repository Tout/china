__author__ = 'jonathan, jba'

import os
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
            iid2privipv4(iid)
        else:
            data = json.loads(output)

            block = 'haproxy-' + unit.unit_name
            region_context = unit.region_context
            host = util.env_prefix(region_context)+unit.env_name+"-"+unit.unit_name+"-"+iid+"."+ region_context.region_config['unit_domain']
            ip = iid2privipv4(iid)

            # print("looking for override/haproxy/"+block+"/servers/ to add host:"+host)
            data['override_attributes']['haproxy'][block]["servers"].append([host, ip])

            temp = util.write_temp_file(json.dumps(data), suffix=".json")

        util.execute_shell(["knife", "environment", "from", "file", temp])

        # verify host is now in output
        output = knife_environment_show(unit.env_name)
        print >> sys.stderr, "looking for host="+host+" in output: "+str(output)
        if util.is_noop():
            return

        if host in output:
            return
        else:
            time.sleep(10)

def generate_deployer_script(unit, deployer_base_uri=None):
    if deployer_base_uri is None:
        region_config = unit.region_context.region_config
        if 'deployer_base_uri' not in region_config:
            raise Exception("no 'deployer_base_uri' defined for region: "+unit.region)
        deployer_base_uri = region_config['deployer_base_uri']
    suffix = ""
    if unit.role_name != unit.unit_name:
        suffix = "/" + unit.role_name
    return "#!/bin/bash\ncurl "+deployer_base_uri+"/deployer/$(ec2metadata --instance-id)"+suffix

def run_instance(unit, instance_number):

    config = unit.config

    region_config = unit.region_context.region_config
    region_name = unit.region_context.region

    args = ["ec2-run-instances", unit.get_ami(),
            "--instance-initiated-shutdown-behavior", "terminate",
            "--region", region_config['EC2_REGION'],
            "-g", unit.env_group_name,
            "-g", unit.group_name]

    if 'extra_groups' in config:
        for group in util.to_list(config['extra_groups']):
            args.append("-g")
            args.append(group)

    args += [ "-t", unit.get_instance_size(), "-k", unit.get_keypair() ]

    data = unit.get_user_data()
    if data is not None:
        data_file = util.write_temp_file("run_"+unit.unit_name+"_"+unit.role_name+"_userdata_", suffix=".json")
        args += [ "-f", data_file ]

    azone = unit.get_availability_zone()
    if azone is not None:
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
    while True:
        host = str(util.execute_shell(["iid2hn", iid])[0]).strip()
	print host
        if util.is_noop():
            host = 'debug.host.example.com'

        # print "iid2hn returned "+host
        if host != "pending" and len(host) > 10 and len(host) < 100:
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
        # print "raw context is "+pformat(self.context)
        self.context['unit_name'] = unit_name
        self.context['env_name'] = self.env_name
        self.context['env_group_name'] = self.env_group_name
        self.unit_yml_dir = ctx.blueprints_dir + "/units/" + unit_name
        self.yml = self.unit_yml_dir + "/unit.yml"
        self.config = util.load_yaml(self.yml, self.context)
        print "loaded "+unit_name+" yml: "+pformat(self.config)
        if 'override_region_context' in self.config:
            for key, value in self.config['override_region_context'].iteritems():
                self.region_context.region_config[key] = value
        print("config====")
        pprint(self.config)

    def get_ami(self):
        region_config = self.region_context.region_config
        if 'ami' in self.config:
            return self.config['ami']
        elif 'default_ami' in region_config:
            return region_config['default_ami']
        else:
            raise Exception("no 'ami' specified in unit "+self.unit_name+" and no 'default_ami' specified in region "+self.region)

    def get_instance_size(self):
        region_config = self.region_context.region_config
        if 'instance_size' in self.config:
            return self.config['instance_size']
        elif 'default_instance_size' in region_config:
            return region_config['default_instance_size']
        else:
            raise Exception("no 'instance_size' specified in unit "+self.unit_name+" and no 'default_instance_size' specified in region "+self.region)

    def get_availability_zone(self):
        region = self.region_context.region
        region_config = self.region_context.region_config
        azone = None
        if 'availability_zone' in self.config and region in self.config['availability_zone']:
            azone = self.config['availability_zone'][region]
        elif 'default_availability_zone' in region_config:
            azone = region_config['default_availability_zone']

        if azone is not None and azone not in region_config['EC2_REGION_AZS']:
            raise Exception("Availability Zone '"+azone+"' is not allowed in region "+region+". Valid values: "+str(region_config['EC2_REGION_AZS']))

        return azone

    def get_user_data(self):
        if 'user_data' not in self.config:
            return None

        if self.role_name not in self.config['user_data']:
            raise Exception("no user_data found in unit "+self.unit_name+" for role "+self.role_name)

        data = self.config['user_data'][self.role_name]
        if isinstance(data, types.StringType) and data == 'deployer':
            # super simple case - default deployer action
            return generate_deployer_script(self)

        elif isinstance(data, types.DictType) and data.has_key('deployer'):
            deployer = data['deployer']
            if not deployer.startswith('http'):
                raise Exception("custom deployer url is invalid ("+deployer+") in yml: "+self.yml)
                # custom deployer action
            return generate_deployer_script(self, deployer)
        else:
            # whatever kind of shell script you want
            return str(self.config['user_data'][self.role_name]).strip()

    def get_keypair(self):
        return self.region_context.region_config['keypair']

    def get_asg_parameter(self, arg, default_value):
        if 'auto_scale' in self.config:
            for env in [ self.env_name, 'default' ]:
                if env in self.config['auto_scale'] and arg in self.config['auto_scale'][env]:
                    return str(self.config['auto_scale'][env][arg])
        return default_value

    def get_asg_max(self):
        return self.get_asg_parameter('max', 1)

    def get_asg_min(self):
        return self.get_asg_parameter('min', 1)

    def get_asg_desired(self):
        return self.get_asg_parameter('desired', 1)

    def create_ec2_group(self):
        region_name = self.region_context.region_config['EC2_REGION']
        ec2.create_group(self.group_name, "Environment "+self.env_name+" Unit "+self.unit_name, region_name)

    def instantiate(self):
        for i in range(1, self.num_instances+1):
            run_instance(self, i)

    def add(self):
        for i in range(1, self.num_instances+1):
            iid = run_instance(self, i)
            add_instance(self, i, iid)

