import logging
import os
"""
    __init__.py: set loggers, and notify test/debug flag?
"""


logging.basicConfig(
    format="[%(levelname)s][%(asctime)s][%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.WARNING
)

special_flag = False
if os.getenv("BILILIVENOTIBOT_TEST") != None:
    print("======> Test flag is set <======")
    special_flag = True

if os.getenv("BILILIVENOTIBOT_DEBUG") != None:
    print("======> Debug flag is set <======")
    special_flag = True

MY_LOGGERS = ["TinyApplication", "BilibiliLiveNotificationBot"]

for name in MY_LOGGERS:
    logger = logging.getLogger(name)
    if special_flag:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

