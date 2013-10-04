#!/usr/bin/python

import sys
import os
import unit
import util
import ec2
import s3
from pprint import pprint, pformat

def setup_environment(ctx, unit_name):
    # Create the EC2 group
    env_name = ctx.specific_environment['name']
    group_name = util.env_prefix(ctx) + env_name
    ec2.create_group(group_name, 'Environment ' + env_name)

    for env in [ ctx.default_environment, ctx.specific_environment ]:
        if 'authorizations' in env:
            for auth in env['authorizations']:
                ec2.authorize(auth, group_name, ctx.region_config)

    setup_unit_environment(ctx, unit_name)

def setup_unit_environment(ctx, unit_name):
    active_unit = unit.ChinaUnit(ctx, unit_name)
    active_unit.create_ec2_group()
    if 'authorizations' in active_unit.config:
        authorizations = active_unit.config['authorizations']

        # default and env-specific grants
        for env in ['default', active_unit.env_name]:
            if env in authorizations:
                for auth in authorizations[env]:
                    ec2.authorize(auth, active_unit.group_name, ctx.region_config)


def create(ctx):

    # create S3 buckets
    prefix = ctx.region_config['s3_bucket_prefix'] + "-" + ctx.specific_environment['name'] + "."
    for bucket in ctx.region_config['buckets']:
        s3.create_bucket(prefix+bucket)

