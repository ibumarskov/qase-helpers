import os


class Config(object):
    def __init__(self):
        self.url = os.environ.get('QASE_TOKEN')
