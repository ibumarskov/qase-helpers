import os


class Config(object):
    def __init__(self):
        self.qase_token = os.environ.get('QASE_TOKEN')
