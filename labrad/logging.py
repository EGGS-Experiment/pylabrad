"""
labrad.logging

Contains functions to set up logging.
"""
import os
import sys
import logging

__all__ = ["labradLogFormatter", "setupLogging"]

# formatting style for labrad logs
labradLogFormatter = logging.Formatter(
    "%(asctime)s [%(name)-15.15s] [%(sender_host)-15.15s] [%(sender_name)-25.25s] [%(levelname)-10.10s]  %(message)s"
)

class _LoggerWriter:
    """
    Redirects stdout to logger.
    Currently only used by labrad.server.
    """
    encoding = 'utf-8'

    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n': self.level(message)

    def flush(self):
        self.level(sys.stderr)

class DummySyslogAdapter(logging.LoggerAdapter):
    """
    Dummy syslog adapter for compatibility.
    To be used when no other valid loggers are found.
    """
    def __init__(self, logger, extra, *args, **kwargs):
        super().__init__(logger, extra or {})

    def process(self, msg=None, kwargs=None):
        # extract relevant values
        hostname, appname, procid, msgid, structured_data = map(
            lambda key_str: kwargs.pop(key_str, None),
            ('hostname', 'appname', 'procid', 'msgid', 'sd',)
        )
        if structured_data is None: structured_data = kwargs.pop('structured_data', None)

        # copy extra logging information into kwargs['extra']
        extra = self.extra.copy()
        extra.update(kwargs.get('extra', {}))
        # programmatically update the "extra" dict
        def _tmp(val, key_str):
            if val: extra[key_str] = val
        list(map(
            _tmp,
            (hostname, appname, procid, msgid, structured_data),
            ('hostname', 'appname', 'procid', 'msgid', 'structured_data',)
        ))
        kwargs['extra'] = extra
        return msg, kwargs

    def info(self, msg=None, *args, **kwargs):
        super().log(logging.INFO, msg, *args, **kwargs)

    # def log(self, level, msg=None, *args, **kwargs):
    #     pass
    # def emergency(self, msg=None, *args, **kwargs):
    #     pass
    # def alert(self, msg=None, *args, **kwargs):
    #     pass
    # def critical(self, msg=None, *args, **kwargs):
    #     pass
    # def error(self, msg=None, *args, **kwargs):
    #     pass
    # def warning(self, msg=None, *args, **kwargs):
    #     pass
    # def notice(self, msg=None, *args, **kwargs):
    #     pass
    # def debug(self, msg=None, *args, **kwargs):
    #     pass


def setupLogging(
        logger_name, sender=None, extraDict=None,
        logHandlers=[], log_level=logging.DEBUG,
        logfile=None,
        syslog=True, syslog_rfc='5424',
        syslog_socket=(os.environ['LABRADHOST'], os.environ['EGGS_LABRAD_SYSLOG_PORT'])
    ):
    """
    Sets up the logger.
    Arguments:
        logger_name     : the name of the logger to set up.
        sender          : the sender.
        extraDict       : the logging dict to send with each log.
        logHandlers     : extra handlers to send the logger.
        log_level       : the default logging level.
        logfile         : the directory to create a logfile in.
        syslog          : whether to create syslog handlers.
        syslog_rfc      : the RFC standard for syslog.
        syslog_socket   : the syslog socket to log to if syslog is True.
    """
    from socket import SOCK_STREAM, gethostname

    # ensure we can create a custom loghandler with labels specific to each sender
    if (sender is None) and (extraDict is None):
        raise Exception("Either sender or extraDict must be specified.")
    elif extraDict is None:
        extraDict = {
            'sender_host': gethostname(),
            'sender_name': sender.__class__.__name__,
        }

    # format extraDict for syslog 5424
    structured_data = {'sender': extraDict.copy()}
    extraDict.update({'structured_data': structured_data})

    # create and configure logger
    logging.basicConfig(level=log_level, handlers=None)
    logger = logging.getLogger(logger_name)
    logger.propagate = False

    # remove any existing loggers, keeping only those related to labrad
    handlers = []
    for name, logger_obj in logging.Logger.manager.loggerDict.items():
        # check log handlers have already been specified
        if isinstance(logger_obj, logging.Logger) and (name == logger_name):
            for log_handler in logger_obj.handlers:
                handlers.append(log_handler)
        # otherwise, turn off any loggers that aren't labrad related
        elif isinstance(logger_obj, logging.Logger) and ('labrad' not in name):
            logger_obj.disabled = True

    # add extra log handlers
    for log_handler in logHandlers:
        try:
            logger.addHandler(log_handler)
        except Exception as e:
            print("Error: unable to add log_handler {}.".format(log_handler))
            print(e)

    # only add core handlers if don't already exist to prevent duplication of log messages
    if len(handlers) == 0:
        # create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(labradLogFormatter)
        logger.addHandler(console_handler)

        # create logfile
        if logfile is not None:
            from logging.handlers import FileHandler
            logfile_handler = FileHandler(logfile)
            logfile_handler.setFormatter(labradLogFormatter)
            logger.addHandler(logfile_handler)

        # set up syslog handlers
        if syslog:
            if syslog_rfc == '3164':
                from logging.handlers import SysLogHandler
                syslog3164_handler = SysLogHandler(address=syslog_socket)
                syslog3164_handler.setFormatter(labradLogFormatter)
                logger.addHandler(syslog3164_handler)

            elif syslog_rfc == '5424':
                try:
                    from rfc5424logging import Rfc5424SysLogHandler
                    syslog5424_handler = Rfc5424SysLogHandler(
                        address=syslog_socket,
                        socktype=SOCK_STREAM,
                        enterprise_id=88888
                    )
                    logger.addHandler(syslog5424_handler)
                except ImportError:
                    print("Error: RFC5424 syslog handler module not installed.")
                except Exception as e:
                    print("Error: unable to create RFC5424 syslog handler.")

    # adapt logger (i.e. add extraDict to logger) and return
    if syslog and (syslog_rfc == '5424'):
        try:
            from rfc5424logging.adapter import Rfc5424SysLogAdapter
            logger_adapter = Rfc5424SysLogAdapter(logger, extraDict)
            return logger_adapter
        except Exception as e:
            print("Error: unable to create RFC5424 syslog adapter.")
            logger_adapter = DummySyslogAdapter(logger, extraDict)
            return logger_adapter
    else:
        return logging.LoggerAdapter(logger, extraDict)

