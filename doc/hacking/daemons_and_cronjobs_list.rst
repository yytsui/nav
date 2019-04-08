ipdevpoll jobs
---------------
python bin/ipdevpolld -j
> 1minstats
> 5minstats
> dns
> inventory
> ip2mac
> snmpcheck
> statuscheck
> topo

To debug, just run
python bin/ipdevpolld -n 10.127.128.119 -J 1minstats

so in conf/ipdevpoll.conf there are
[job_1minstats]
interval = 1m
plugins = statsystem statsensors statmulticast

...etc,

which means in python/nav/ipdevpoll/plugins
statsystem.py statsensors.py statmulticast are triggered to run.
check the 'handle' method is the class



Daemons Process list
----------------------

(p3nav) ➜  nav git:(run) ✗ sudo nav start
Password:
Starting: activeip alertengine dbclean emailreports eventengine ipdevpoll logengine mactrace maintengine navstats netbiostracker pping psuwatch servicemon snmptrapd thresholdmon topology
Failed: smsd





Cron jobs list
---------------

##block __init__##
# NAV updated this crontab at: 2019-04-05 11:28:11
PATH="/Users/yiy/.pyenv/versions/3.6.5/envs/p3nav/bin:/Users/yiy/.nvm/versions/node/v8.12.0/bin:/usr/local/opt/mysql@5.7/bin:/usr/local/Cellar/pyenv-virtualenv/1.1.3/shims:/Users/yiy/.pyenv/shims:/Users/yiy/.local/bin:/usr/local/opt/python/libexec/bin:/usr/local/go/bin:/usr/local/bin:/Users/yiy/tools/cocos2d-x-3.2rc0/tools/cocos2d-console/bin:/Users/yiy/.rbenv/shims:/usr/local/sbin:/usr/local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Users/yiy/tools/git-hg/bin:/Users/yiy/tools/bin:/Users/yiy/.rvm/bin:/Users/yiy/Library/Android/sdk/platform-tools:/Users/yiy/Library/Android/sdk/tools:/Users/yiy/.cabal/bin:/Users/yiy/bin:/usr/local/WordNet-3.0/bin:/Applications/Marmalade.app/Contents/s3e/bin:/Users/yiy/tools/activator-dist-1.3.12/bin:/Users/yiy/vagrant/share/gostuff/bin:/Applications/calibre.app/Contents/console.app/Contents/MacOS:/Users/yiy/.composer/vendor/bin"
MAILTO=root@localhost
##end##
##block activeip##
## info: Collect active ip-adresses for all prefixes
*/30 * * * * collect_active_ip.py
##end##
##block dbclean##
## info: Clean database with navclean
*/5 * * * * navclean -f -q --netbox --websessions
##end##
##block emailreports##
## info: Send email reports for device and link availability
0 5 1 * * emailreports.py month
0 5 * * mon emailreports.py week
0 5 * * * emailreports.py day
##end##
##block logengine##
## info: Regularly check the syslog for network messages and update the logger database

# Regular run
* * * * * logengine.py -q

# Delete old messages once a day
3 3 * * * logengine.py -d

# Delete old ipdevpoll job log entries once every hour
3 * * * * ipdevpolld --clean
##end##
##block mactrace##
## info: Checks NAV's cam log for watched MAC addresses
11,26,41,56 * * * *      macwatch.py
##end##
##block maintengine##
## info: Regularly check the maintenance-queue and send events to eventq
*/5 * * * * maintengine.py
##end##
##block navstats##
## navstats: Collect statistics defined in navstats.conf
*/5 * * * * navstats
##end##
##block netbiostracker##
## info: Regularly fetch netbiosnames from active computers
*/15 * * * * netbiostracker.py
##end##
##block psuwatch##
## info: Monitors the state of redundant PSUs and fans

5 * * * *	powersupplywatch.py
##end##
##block thresholdmon##
## info: Monitors your Graphite metrics for exceeded thresholds

*/5 * * * * thresholdmon
##end##
##block topology##
## info: Detects the topology of your network.

35 * * * *              navtopology --l2 --vlan

# If you want to run the old topology detector, uncomment the following lines:

# 35 * * * *              network-discovery topology
# 38 * * * *              network-discovery vlan
##end##%