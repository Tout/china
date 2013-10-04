china
=====

Manage AWS deployments.

## Common options
Every command accepts the following options:

#### Path to blueprints repository (-b /path/to/blueprints)
This is where the blueprints live. 
If you define the environment variable CHINA\_BLUEPRINT\_DIR then you can omit this option

#### EC2 region (-r ec2-region)
The EC2 region to operate in, valid values are 'east' or 'west'. 
If you define the environment variable CHINA\_EC2\_REGION then you can omit this option

#### Environment (-e env_name)
The EC2 environment to operate in, valid values depend on the region.
For the 'east' region, valid environment names are 'wildwest', 'dev', 'qa', 'stage', 'prod', 'perf', 'inf'
For the 'west' region, valid environment names are 'uw2prod', 'uw2qa'

#### Unit (-u unit_name)
The name of the unit to work with. This must match the name of the unit's directory within the blueprints repo.

#### Do-nothing mode (-n)
Print the commands that would run, but do not execute anything. Dummy values will be shown where necessary.

### china_env_create: Initialize an environment

    china_env_create -e dev -u kicktag

### china_unit_create: Launch an instance and do nothing else

    china_unit_create -e dev -u kicktag

### china_unit_add: Launch an instance and add it to various haproxy/directors that it should be part of

    china_unit_add -e dev -u kicktag

