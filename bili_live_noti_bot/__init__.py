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

MY_LOGGERS = ["TinyApplication", "BilibiliLiveNotificationBot"]

for name in MY_LOGGERS:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

if os.getenv("BILILIVENOTIBOT_TEST") != None:
    print("======> Test flag is set <======")

if os.getenv("BILILIVENOTIBOT_DEBUG") != None:
    print("======> Debug flag is set <======")