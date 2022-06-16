import os
import sys
import logging

__all__ = ["labradLogFormatter", "_LoggerWriter", "setupLogging"]


labradLogFormatter = logging.Formatter(
    "%(asctime)s [%(name)-15.15s] [%(sender_host)-15.15s] [%(sender_name)-25.25s] [%(levelname)-10.10s]  %(message)s"
)


class _LoggerWriter:
    """
    Redirects stdout to logger.
    """
    encoding = 'utf-8'

    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n':
            self.level(message)

    def flush(self):
        self.level(sys.stderr)


def setupLogging(
        logger_name, sender=None, extraDict=None,
        logHandlers=None, log_level=logging.DEBUG,
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
        syslog          : whether to create syslog handlers.
        syslog_rfc      : the RFC standard for syslog.
        syslog_socket   : the syslog socket to log to if syslog is True.
    """
    from socket import SOCK_STREAM, gethostname
    from logging.handlers import SysLogHandler

    # get default arguments
    if (sender is None) and (extraDict is None):
        raise Exception("Either sender or extraDict must be specified.")

    # create and configure logger
    logging.basicConfig(level=log_level, handlers=None)
    logger = logging.getLogger(logger_name)

    # don't propagate log events to root logger
    logger.propagate = False

    # check if logger already has handlers; only keep loggers with same name
    handlers = {}
    for name, logger_class in logging.Logger.manager.loggerDict.items():
        if isinstance(logger_class, logging.Logger) and (name == logger_name):
            for log_handler in logger_class.handlers:
                handlers[logger_name] = log_handler


    # create custom loghandler so logging labels are specific to each sender
    if extraDict is None:
        extraDict = {
            'sender_host': gethostname(),
            'sender_name': sender.__class__.__name__,
        }

    # turn extraDict into structured_data for rfc5424
    structured_data = {'sender': extraDict.copy()}
    extraDict.update({'structured_data': structured_data})

    # only add handlers if we don't already have some
    if (len(handlers) == 0):
        # create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(labradLogFormatter)
        logger.addHandler(console_handler)

        if syslog:
            # create syslog handler
            if syslog_rfc == '3164':
                syslog_handler = SysLogHandler(address=syslog_socket)
                syslog_handler.setFormatter(labradLogFormatter)
                logger.addHandler(syslog_handler)

            # create rfc5424 handler
            if syslog_rfc == '5424':
                try:
                    from rfc5424logging import Rfc5424SysLogHandler
                    syslog5424_handler = Rfc5424SysLogHandler(
                        address=syslog_socket,
                        socktype=SOCK_STREAM,
                        enterprise_id=88888
                    )
                    logger.addHandler(syslog5424_handler)
                except ImportError:
                    print("Error: RFC5424 syslog handler module is not installed.")
                except Exception as e:
                    print(e)
                    print("Error: unable to create RFC5424 syslog handler.")

    # adapt logger and return
    if syslog_rfc == '5424':
        try:
            from rfc5424logging.adapter import Rfc5424SysLogAdapter
            logger_adapter = Rfc5424SysLogAdapter(logger, extraDict)
            return logger_adapter
        except ImportError:
            print("Error: RFC5424 syslog handler module is not installed.")
        except Exception as e:
            print("Error: unable to create RFC5424 syslog handler.")
    elif syslog_rfc == '3164':
        return logger
