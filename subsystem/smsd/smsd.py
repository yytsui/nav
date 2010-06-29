#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 UNINETT AS
#
# This file is part of Network Administration Visualized (NAV).
#
# NAV is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.  You should have received a copy of the GNU General Public License
# along with NAV. If not, see <http://www.gnu.org/licenses/>.
#
"""The NAV SMS daemon (smsd)

smsd dispatches SMS messages from the database to users' phones with the help
of plugins using Gammu and a cell on the COM port, or free SMS services on the
web.

Usage: smsd [-h] [-c] [-d sec] [-f factor] [-m maxdelay] [-l limit] [-a action] [-t phone no.]

  -h, --help            Show this help text
  -c, --cancel          Cancel (mark as ignored) all unsent messages
  -d, --delay           Set delay (in seconds) between queue checks
  -f, --factor          Set the factor delay will be multiplied with
  -m, --maxdelay        Maximum delay (in seconds)
  -l, --limit           Set the limit of retries
  -a, --action          The action to perform when reaching limit (0 or 1)
                          0: Messages in queue are marked as ignored and error
                             details are logged and mailed to admin. Deamon
                             resumes running and checking the message queue.
                          1: Error details are logged and mailed to admin. The
                             deamon shuts down.
  -t, --test            Send a test message to <phone no.>

"""

import getopt
import logging
import logging.handlers
import os
import os.path
import pwd
import signal
import socket
import sys
import time

import nav.config
import nav.daemon
import nav.logs
import nav.path
import nav.smsd.navdbqueue
from nav.smsd.dispatcher import DispatcherError, PermanentDispatcherError
from nav.config import getconfig
# Dispatchers are imported later according to config


### PATHS

configfile = os.path.join(nav.path.sysconfdir, 'smsd.conf')
logfile = os.path.join(nav.path.localstatedir, 'log', 'smsd.log')
pidfile = os.path.join(nav.path.localstatedir, 'run', 'smsd.pid')

### MAIN FUNCTION

def main(args):
    # Get command line arguments
    optcancel = False
    optdelay = False
    optfactor = False
    optmaxdelay = False
    optlimit = False
    optaction = False
    opttest = False
    try:
        opts, args = getopt.getopt(args, 'hcd:f:m:l:a:t:',
         ['help', 'cancel', 'delay=', 'test='])
    except getopt.GetoptError, error:
        print >> sys.stderr, "%s\nTry `%s --help' for more information." % (
            error, sys.argv[0])
        sys.exit(1)
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(0)
        if opt in ('-c', '--cancel'):
            optcancel = True
        if opt in ('-d', '--delay'):
            optdelay = int(val)
        if opt in ('-f', '--factor'):
            optfactor = int(val)
        if opt in ('-m', '--maxdelay'):
            optmaxdelay = int(val)
        if opt in ('-l', '--limit'):
            optlimit = int(val)
        if opt in ('-a', '--action'):
            optaction = int(val)
        if opt in ('-t', '--test'):
            opttest = val


    # Set config defaults
    defaults = {
        'username': 'navcron',
        'delay': '30',
        'delayfactor': '1.5',
        'maxdelay': '3600',
        'retrylimit': '0',
        'retrylimitaction': '0',
        'autocancel': '0',
        'loglevel': 'INFO',
        'mailwarnlevel': 'ERROR',
        'mailserver': 'localhost',
        'mailaddr': nav.config.readConfig('nav.conf')['ADMIN_MAIL']
    }

    # Read config file
    config = getconfig(configfile, defaults)

    # Set variables
    global delay, failed
    failed = 0
    delay = int(config['main']['delay'])
    maxdelay = int(config['main']['maxdelay'])
    delayfactor = float(config['main']['delayfactor'])
    retrylimit = int(config['main']['retrylimit'])
    retrylimitaction = int(config['main']['retrylimitaction'])
    retryvars = {
        'maxdelay': maxdelay,
        'delayfactor': delayfactor,
        'retrylimit': retrylimit,
        'retrylimitaction': retrylimitaction
    }


    username = config['main']['username']
    autocancel = config['main']['autocancel']
    loglevel = eval('logging.' + config['main']['loglevel'])
    mailwarnlevel = eval('logging.' + config['main']['mailwarnlevel'])
    mailserver = config['main']['mailserver']
    mailaddr = config['main']['mailaddr']

    # Initialize logger
    global logger
    nav.logs.setLogLevels()
    logger = logging.getLogger('nav.smsd')
    loginitstderr(loglevel)
    if not loginitfile(loglevel, logfile):
        sys.exit('Failed to init file logging.')
    if not loginitsmtp(mailwarnlevel, mailaddr, mailserver):
        sys.exit('Failed to init SMTP logging.')


    # First log message
    logger.info('Starting smsd.')


    # Set custom loop delay
    if optdelay:
        setdelay(optdelay)

    # Ignore unsent messages
    if optcancel:
        queue = nav.smsd.navdbqueue.NAVDBQueue()
        ignCount = queue.cancel()
        logger.info("All %d unsent messages ignored.", ignCount)
        sys.exit(0)

    if optfactor:
        retryvars['delayfactor'] = optfactor
    if optmaxdelay:
        retryvars['maxdelay'] = optmaxdelay
    if optlimit:
        retryvars['retrylimit'] = optlimit
    if optaction:
        retryvars['retrylimitaction'] = optaction

    # Send test message (in other words: test the dispatcher)
    if opttest:
        msg = [(0, "This is a test message from NAV smsd.", 0)]

        try:
            (sms, sent, ignored, smsid) = dh.sendsms(opttest, msg)
        except DispatcherError, error:
            logger.critical("Sending failed. Exiting. (%s)", error)
            sys.exit(1)

        logger.info("SMS sent. Dispatcher returned reference %d.", smsid)
        sys.exit(0)

    # Let the dispatcherhandler take care of our dispatchers
    try:
        dh = nav.smsd.dispatcher.DispatcherHandler(config)
    except PermanentDispatcherError, error:
        logger.critical("Dispatcher configuration failed. Exiting. (%s)", error)
        sys.exit(1)

    # Switch user to navcron (only works if we're root)
    try:
        nav.daemon.switchuser(username)
    except nav.daemon.DaemonError, error:
        logger.error("%s Run as root or %s to enter daemon mode. "
            + "Try `%s --help' for more information.",
            error, username, sys.argv[0])
        sys.exit(1)

    # Check if already running
    try:
        nav.daemon.justme(pidfile)
    except nav.daemon.DaemonError, error:
        logger.error(error)
        sys.exit(1)

    # Daemonize
    try:
        nav.daemon.daemonize(pidfile,
                             stderr=nav.logs.get_logfile_from_logger())
    except nav.daemon.DaemonError, error:
        logger.error(error)
        sys.exit(1)

    # Daemonized; stop logging explicitly to stderr and reopen log files
    loguninitstderr()
    nav.logs.reopen_log_files()
    logger.debug('Daemonization complete; reopened log files.')

    # Reopen log files on SIGHUP
    logger.debug('Adding signal handler for reopening log files on SIGHUP.')
    signal.signal(signal.SIGHUP, signalhandler)
    # Exit on SIGTERM
    signal.signal(signal.SIGTERM, signalhandler)

    # Initialize queue
    # NOTE: If we're initalizing a queue with a DB connection before
    # daemonizing we've experienced that the daemon dies silently upon trying
    # to use the DB connection after becoming a daemon
    queue = nav.smsd.navdbqueue.NAVDBQueue()

    # Automatically cancel unsent messages older than a given interval
    if autocancel != '0':
        ignCount = queue.cancel(autocancel)
        logger.info("%d unsent messages older than '%s' autocanceled.",
            ignCount, autocancel)


    # Loop forever
    while True:
        logger.debug("Starting loop.")

        # Queue: Get users with unsent messages
        users = queue.getusers('N')

        logger.info("Found %d user(s) with unsent messages.", len(users))

        # Loop over cell numbers
        for user in users:
            # Queue: Get unsent messages for a user ordered by severity desc
            msgs = queue.getusermsgs(user, 'N')
            logger.info("Found %d unsent message(s) for %s.", len(msgs), user)

            # Dispatcher: Format and send SMS
            try:
                (sms, sent, ignored, smsid) = dh.sendsms(user, msgs)
            except PermanentDispatcherError, error:
                logger.critical("Sending failed permanently. Exiting. (%s)",
                    error)
                sys.exit(1)
            except DispatcherError, error:
                try:
                    # Dispatching failed. Backing off and retrying.
                    backoff(delay, retryvars, error)
                    break # End this run
                except:
                    logger.exception("")
                    raise
            except Exception, error:
                logger.exception("Unknown exception: %s", error)


            logger.info("SMS sent to %s.", user)

            try:
                setdelay(int(config['main']['delay']))
            except:
                setdelay(int(defaults['delay']))

            failed = 0
            logger.debug("Resetting number of failed runs.")


            for msgid in sent:
                queue.setsentstatus(msgid, 'Y', smsid)
            for msgid in ignored:
                queue.setsentstatus(msgid, 'I', smsid)
            logger.info("%d messages was sent and %d ignored.",
                len(sent), len(ignored))

        # Sleep a bit before the next run
        logger.debug("Sleeping for %d seconds.", delay)
        time.sleep(delay)

        # Devel only
        #break

    # Exit nicely
    sys.exit(0)


### HELPER FUNCTIONS

def backoff(sec, retryvars, error):
    """Delay next loop if dispatching SMS fails."""

    # Function is invoked with the assumtion that there are unsent messages in queue.
    global failed
    maxdelay, delayfactor, retrylimit, retrylimitaction = retryvars['maxdelay'],\
                                                          retryvars['delayfactor'],\
                                                          retryvars['retrylimit'],\
                                                          retryvars['retrylimitaction']
    failed += 1
    logger.debug("Dispatcher failed %d time(s).", failed)

    if sec * delayfactor < maxdelay:
        setdelay(sec * delayfactor)
    else:
        if sec != maxdelay:
            setdelay(maxdelay)

        queue = nav.smsd.navdbqueue.NAVDBQueue()
        msgs = queue.getmsgs('N')

        if failed <= retrylimit:
            backoffaction(retryvars, error)
        elif retrylimit == 0 and delay >= maxdelay:
            if len(msgs) > 0:
                logger.critical("Dispatching SMS fails. %d unsent message(s), the oldest from %s. (%s)",
                        len(msgs), msgs[0]['time'], error)
            else:
                logger.critical("Dispatching SMS fails. (%s)", error)


def backoffaction(retryvars, error):
    """Perform an action if maximum number of failed attempts has been reached."""

    global failed
    retrylimitaction = retryvars['retrylimitaction']
    queue = nav.smsd.navdbqueue.NAVDBQueue()
    msgs = queue.getmsgs('N')

    if retrylimitaction == 0:
        # Queued messages are marked as ignored, logs a critical error with
        # message details, then resumes run.

        failed = 0
        numbmsg = queue.cancel()
        msgdetails = "Dispatching SMS fails. %d message(s) were ignored:\n" % numbmsg
        for index, msg in enumerate(msgs):
            msgdetails += "%d: \"%s\" -> %s\n" % (index+1,
                    msg["msg"], msg["name"])

        logger.critical("%s\nTraceback:\n%s", msgdetails, error)

    elif retrylimitaction == 1:
        # Logs the number of unsent messages and time of the oldest in queue
        # before shutting down daemon.
        logger.critical("Dispatching SMS fails. %d unsent message(s), the oldest from %s. Shutting down daemon. (%s)",
                    len(msgs), msgs[0]["time"], error)
        sys.exit(0)

    else:
        logger.warning("No retry limit action is set or the option is not valid.")

def signalhandler(signum, _):
    """
    Signal handler to close and reopen log file(s) on HUP
    and exit on KILL.
    """

    if signum == signal.SIGHUP:
        global logger
        logger.info("SIGHUP received; reopening log files.")
        nav.logs.reopen_log_files()
        nav.daemon.redirect_std_fds(
            stderr=nav.daemon.get_logfile_from_logger())
        logger.info("Log files reopened.")
    elif signum == signal.SIGTERM:
        logger.warn('SIGTERM received: Shutting down.')
        sys.exit(0)

def loginitfile(loglevel, filename):
    """Initalize the logging handler for logfile."""

    try:
        filehandler = logging.FileHandler(filename, 'a')
        fileformat = '[%(asctime)s] [%(levelname)s] [pid=%(process)d %(name)s] %(message)s'
        fileformatter = logging.Formatter(fileformat)
        filehandler.setFormatter(fileformatter)
        filehandler.setLevel(loglevel)
        logger = logging.getLogger()
        logger.addHandler(filehandler)
        return True
    except IOError, error:
        print >> sys.stderr, \
            "Failed creating file loghandler. Daemon mode disabled. (%s)" \
            % error
        return False

def loginitstderr(loglevel):
    """Initalize the logging handler for stderr."""

    try:
        stderrhandler = logging.StreamHandler(sys.stderr)
        stderrformat = '[%(levelname)s] [pid=%(process)d %(name)s] %(message)s'
        stderrformatter = logging.Formatter(stderrformat)
        stderrhandler.setFormatter(stderrformatter)
        stderrhandler.setLevel(loglevel)
        logger = logging.getLogger()
        logger.addHandler(stderrhandler)
        return True
    except IOError, error:
        print >> sys.stderr, \
            "Failed creating stderr loghandler. Daemon mode disabled. (%s)" \
            % error
        return False

def loguninitstderr():
    """Remove the stderr StreamHandler from the root logger."""
    for hdlr in logging.root.handlers:
        if isinstance(hdlr, logging.StreamHandler) and hdlr.stream is sys.stderr:
            logging.root.removeHandler(hdlr)
            return True

def loginitsmtp(loglevel, mailaddr, mailserver):
    """Initalize the logging handler for SMTP."""

    try:
        # localuser will be root if smsd was started as root, since
        # switchuser() is first called at a later time
        localuser = pwd.getpwuid(os.getuid())[0]
        hostname = socket.gethostname()
        fromaddr = localuser + '@' + hostname

        mailhandler = logging.handlers.SMTPHandler(mailserver, fromaddr,
            mailaddr, 'NAV smsd warning from ' + hostname)
        mailformat = '[%(asctime)s] [%(levelname)s] [pid=%(process)d %(name)s] %(message)s'
        mailformatter = logging.Formatter(mailformat)
        mailhandler.setFormatter(mailformatter)
        mailhandler.setLevel(loglevel)
        logger = logging.getLogger()
        logger.addHandler(mailhandler)
        return True
    except Exception, error:
        print >> sys.stderr, \
            "Failed creating SMTP loghandler. Daemon mode disabled. (%s)" \
            % error
        return False

def usage():
    """Print a usage screen to stderr."""

    print >> sys.stderr, __doc__

def setdelay(sec):
    """Set delay (in seconds) between queue checks."""

    global delay, logger

    delay = sec
    logger.info("Setting delay to %d seconds.", delay)

### BEGIN
if __name__ == '__main__':
    main(sys.argv[1:])

