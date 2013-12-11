import subprocess
import util
from pprint import pprint

def create_group (group_name, description, region_name):
    util.execute_shell([ 'ec2-create-group',  group_name,
                         '-d', description,
                         '--region', region_name ])

def authorize(auth, group_name, env_name, region):
    has_from = 'from' in auth
    has_to = 'to' in auth
    has_to_env = 'to_env' in auth
    
    # TODO fix error checking while we are debugging to_env
    # if has_from and has_to:
    #    raise Exception("illegal authorization block: using both 'from' and 'to' is not allowed: " + str(auth))
    # if not has_from and not has_to:
    #    raise Exception("illegal authorization block: neither 'from' nor 'to' was specified: " + str(auth))

    if has_from:
        from_addrs = util.to_list(auth['from'])
        for from_addr in from_addrs:
            do_authorize(from_addr, group_name, auth, region)
    elif has_to_env:
        to_env_addrs = util.to_list(auth['to_env'])
        for to_env_addr in to_env_addrs:
            to_unit_group = "env-"+env_name+"-"+to_env_addr
            print "group_name is "+group_name+" and to_unit_group is "+to_unit_group
            do_authorize(group_name, to_unit_group, auth, region)        
    else:
        to_addrs = util.to_list(auth['to'])
        for to_addr in to_addrs:
            print "to addr "+to_addr+" and group name "+group_name
            do_authorize(group_name, to_addr, auth, region)

def do_authorize(from_group, to_group, auth, region):
    protocols = [ 'tcp' ]
    if 'protocols' in auth:
        protocols = util.to_list(auth['protocols'])

    account = str(region['aws_account'])
    region_name = str(region['EC2_REGION']).strip()

    auths = 0
    for protocol in protocols:
        if protocol == 'icmp':
            authorize_icmp(from_group, to_group, auth['icmp_types'], account, region_name)
            auths += 1
        else:
            if 'ports' not in auth:
                raise Exception("no ports specified in auth: "+str(auth))

            ports = util.to_list(auth['ports'])
            for port in ports:
                authorize_normal(from_group, to_group, port, protocol, account, region_name)
                auths += 1

    if auths == 0:
        raise Exception("no authorizations made for auth: "+str(auth))

def authorize_normal (from_addr, to_addr, port, protocol, account, region_name):
    # If it doesn't look like an IP address, then it's a group
    if util.is_cidr(to_addr):
        util.execute_shell([ 'ec2-authorize', from_addr,
                             '--region', region_name,
                             '-P', protocol,
                             '-p', str(port),
                             '-s', to_addr])
    else:
        util.execute_shell([ 'ec2-authorize', from_addr,
                             '--region', region_name,
                             '-P', protocol,
                             '-p', str(port),
                             '-u', account,
                             '-o', to_addr])

def authorize_icmp (from_addr, to_addr, icmp_types, account, region_name):
    util.execute_shell([ 'ec2-authorize', from_addr,
                         '--region', region_name,
                         '-P', 'icmp',
                         '-t', icmp_types,
                         '-u', account,
                         '-o', to_addr])
